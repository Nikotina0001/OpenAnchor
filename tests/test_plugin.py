"""Host contract tests; real desktop loading is recorded separately."""
import importlib
import json
import sys
from types import SimpleNamespace
from pathlib import Path
import pytest
from openanchor.geometry import prism
from shapely.geometry import box


@pytest.fixture
def host(monkeypatch, tmp_path):
    mesh = prism(box(100,100,120,120),0,10)
    import numpy as np
    raw = SimpleNamespace(vertices=lambda:mesh.vertices,triangles=lambda:mesh.faces)
    volume = SimpleNamespace(id=lambda:456,is_model_part=lambda:True, mesh=lambda:raw, matrix=lambda:np.eye(4),
        extruder_id=lambda:1,
        config_keys=lambda:[],config_value=lambda k:None,
        is_mm_painted=lambda:False,is_seam_painted=lambda:False,is_fdm_support_painted=lambda:False,is_fuzzy_skin_painted=lambda:False)
    instance=SimpleNamespace(printable=True,matrix=lambda:np.eye(4))
    obj=SimpleNamespace(id=lambda:123,name='Calibration',instances=lambda:[instance],volumes=lambda:[volume],
        has_custom_layering=lambda:False,config_value=lambda k:None,config_keys=lambda:[])
    config={'printable_area':'0x0,256x0,256x256,0x256','initial_layer_print_height':'0.2','layer_height':'0.2'}
    filament=SimpleNamespace(config_value=lambda k:None)
    bundle=SimpleNamespace(current_filament_preset_names=lambda:['PP','PLA'],current_filament_presets=lambda:[filament,filament],full_config_value=lambda k:config.get(k))
    messages=[]
    class Pages:
        def post_message(self,data): messages.append(data)
    orca=SimpleNamespace(pages=SimpleNamespace(PagesPluginCapabilityBase=Pages),host=SimpleNamespace(
        plugin=SimpleNamespace(storage=lambda:str(tmp_path)),model=lambda:SimpleNamespace(objects=lambda:[obj]),preset_bundle=lambda:bundle))
    def export_profile(path):
        from zipfile import ZipFile
        with ZipFile(path,'w') as archive:
            archive.writestr('Metadata/project_settings.config',json.dumps({'filament_settings_id':['PP','PLA']}))
    orca.host.plater=lambda:SimpleNamespace(export_3mf_copy=export_profile)
    monkeypatch.setitem(sys.modules,'orca',orca)
    sys.modules.pop('openanchor.plugin',None)
    module=importlib.import_module('openanchor.plugin')
    yield module.OpenAnchorPage(),messages,tmp_path,obj,volume
    sys.modules.pop('openanchor.plugin',None)


def test_page_refresh_generate_update_and_disable(host):
    page,messages,directory,obj,volume=host
    assert 'OpenAnchor' in page.get_ui()
    page.on_message({'action':'refresh'})
    assert messages[-1]['objects'][0]['id']=='123'
    request={'action':'generate','object_id':'123','instance':0,'hardware_confirmed':True,'settings':{}}
    page.on_message(request)
    assert 'output' in messages[-1], messages[-1]
    output=Path(messages[-1]['output']); assert output.exists()
    request['settings']={'flange_height':1.2}; page.on_message(request)
    assert messages[-1]['report']['effective_flange_height_mm']==1.2
    assert Path(messages[-1]['output'])==output
    request['settings']={'enabled':False}; page.on_message(request)
    assert messages[-1]['report']['enabled'] is False
    assert json.loads((directory/'settings.json').read_text())['enabled'] is False


def test_stale_objects_and_paint_rejected(host):
    page,messages,directory,obj,volume=host
    req={'action':'generate','object_id':'stale','instance':0,'hardware_confirmed':True}
    page.on_message(req); assert 'refresh' in messages[-1]['error']
    req['object_id']='123'; volume.is_mm_painted=lambda:True
    page.on_message(req); assert 'painting' in messages[-1]['error']
    volume.is_mm_painted=lambda:False; obj.has_custom_layering=lambda:True
    page.on_message(req); assert 'layer-boundary' in messages[-1]['error']


def install_bridge(host, monkeypatch):
    page,messages,directory,obj,volume=host
    plater=sys.modules['orca'].host.plater()
    plater.instance_plate=lambda object_id,instance:{'index':0,'origin':[0,0,0]}
    calls=[]
    original=[volume]
    def apply(request):
        calls.append(request)
        assert Path(next((directory/'backups').iterdir())).exists()
        generated=[str(1000+len(calls)*2),str(1001+len(calls)*2)]
        record={key:request[key] for key in ('object_id','source_volume_id')}
        record.update(generated_volume_ids=generated,original_extruder=request.get('original_extruder'),
                      original_brim=request.get('original_brim','outer_only'))
        from copy import copy
        parts=[copy(volume),copy(volume)]
        for part,part_id in zip(parts,generated):
            part.id=lambda value=part_id:value
        obj.volumes=lambda:original+parts
        return record
    def restore(request):
        calls.append(request)
        obj.volumes=lambda:original
    plater.apply_anchor=apply
    plater.restore_anchor=restore
    monkeypatch.setattr(sys.modules['orca'].host,'plater',lambda:plater)
    return calls,plater


def test_stock_host_does_not_offer_native_edit(host):
    page,messages,directory,obj,volume=host
    page.on_message({'action':'refresh'})
    assert messages[-1]['bridge_available'] is False
    page.on_message({'action':'apply','object_id':'123','instance':0,'hardware_confirmed':True})
    assert 'requires the OpenAnchor edition' in messages[-1]['error']
    assert len(obj.volumes())==1
    assert not (directory/'backups').exists()


def test_apply_update_restore_preserves_source_and_original_settings(host, monkeypatch):
    page,messages,directory,obj,volume=host
    calls,plater=install_bridge(host,monkeypatch)
    request={'action':'apply','object_id':'123','instance':0,'hardware_confirmed':True,'settings':{}}
    page.on_message(request)
    assert messages[-1].get('applied'),messages[-1]
    first=messages[-1]['record']
    assert "Wall loops to 100" in messages[-1]['warning']
    assert messages[-1]['report']['settings']['gap'] == 0
    backup=messages[-1]['backup']
    assert Path(backup).is_file()
    assert calls[0]['generated_volume_ids']==[]
    assert calls[0]['source_volume_id']=='456'
    assert len(calls[0]['flange']['vertices'])>0
    assert obj.volumes()[0] is volume
    first_parts=list(obj.volumes())
    request['settings']={'flange_height':1.2}
    page.on_message(request)
    assert messages[-1].get('applied'),messages[-1]
    assert calls[1]['generated_volume_ids']==first['generated_volume_ids']
    assert calls[1]['original_brim']=='outer_only'
    assert messages[-1]['backup']==backup
    assert messages[-1]['report']['effective_flange_height_mm']==1.2
    assert len(list((directory/'backups').iterdir()))==1
    page.on_message({'action':'refresh'})
    assert messages[-1]['objects'][0]['managed'] is True
    # Native Undo changes the live IDs back to the previous apply.
    obj.volumes=lambda:first_parts
    page.on_message({'action':'restore','object_id':'123','instance':0})
    assert messages[-1].get('restored'),messages[-1]
    assert calls[-1]['generated_volume_ids']==first['generated_volume_ids']
    assert obj.volumes()==[volume]
    page.on_message({'action':'refresh'})
    assert messages[-1]['objects'][0]['managed'] is False
    assert len(json.loads((directory/'anchors.json').read_text())['123'])==2


def test_native_failure_does_not_record_ownership(host,monkeypatch):
    page,messages,directory,obj,volume=host
    calls,plater=install_bridge(host,monkeypatch)
    def fail(request):
        raise ValueError('Native validation rejected the mesh')
    plater.apply_anchor=fail
    page.on_message({'action':'apply','object_id':'123','instance':0,'hardware_confirmed':True})
    assert 'Native validation rejected' in messages[-1]['error']
    assert not (directory/'anchors.json').exists()
    assert obj.volumes()==[volume]


def test_unowned_multipart_and_multi_instances_rejected(host,monkeypatch):
    page,messages,directory,obj,volume=host
    calls,plater=install_bridge(host,monkeypatch)
    request={'action':'apply','object_id':'123','instance':0,'hardware_confirmed':True}
    instance=obj.instances()[0]
    obj.instances=lambda:[instance,instance]
    page.on_message(request)
    assert 'one instance' in messages[-1]['error']
    obj.instances=lambda:[instance]
    from copy import copy
    extra=copy(volume);extra.id=lambda:999
    obj.volumes=lambda:[volume,extra]
    page.on_message(request)
    assert 'single-part' in messages[-1]['error']
    assert calls==[]


def test_backup_failure_prevents_mutation(host,monkeypatch):
    page,messages,directory,obj,volume=host
    calls,plater=install_bridge(host,monkeypatch)
    plater.export_3mf_copy=lambda path:None
    page.on_message({'action':'apply','object_id':'123','instance':0,'hardware_confirmed':True})
    assert 'backup was not written' in messages[-1]['error']
    assert calls==[]


def test_stale_generated_ids_are_never_replaced(host,monkeypatch):
    page,messages,directory,obj,volume=host
    calls,plater=install_bridge(host,monkeypatch)
    request={'action':'apply','object_id':'123','instance':0,'hardware_confirmed':True}
    page.on_message(request)
    obj.volumes()[1].id=lambda:99999
    page.on_message(request)
    assert 'single-part' in messages[-1]['error']
    page.on_message({'action':'restore','object_id':'123','instance':0})
    assert 'No matching' in messages[-1]['error']
    assert len(calls)==1


def test_ownership_survives_page_reload_and_other_object_is_untouched(host,monkeypatch):
    page,messages,directory,obj,volume=host
    calls,plater=install_bridge(host,monkeypatch)
    from copy import copy
    import numpy as np
    other=copy(obj);other.id=lambda:789
    other_volume=copy(volume);other_volume.id=lambda:999
    other_instance=copy(obj.instances()[0])
    matrix=np.eye(4);matrix[0,3]=80
    other_instance.matrix=lambda:matrix
    other.volumes=lambda:[other_volume]
    other.instances=lambda:[other_instance]
    sys.modules['orca'].host.model=lambda:SimpleNamespace(objects=lambda:[obj,other])
    page.on_message({'action':'apply','object_id':'123','instance':0,'hardware_confirmed':True})
    assert messages[-1].get('applied'),messages[-1]
    reloaded=type(page)()
    reloaded.on_message({'action':'refresh'})
    assert [item['managed'] for item in messages[-1]['objects']]==[True,False]
    reloaded.on_message({'action':'restore','object_id':'123','instance':0})
    assert messages[-1].get('restored'),messages[-1]
    assert other.volumes()==[other_volume]
    assert np.array_equal(other.instances()[0].matrix(),matrix)


def test_persistence_failure_reports_success_and_retains_session_restore(host,monkeypatch):
    page,messages,directory,obj,volume=host
    calls,plater=install_bridge(host,monkeypatch)
    original=Path.write_text
    def fail_record(path,*args,**kwargs):
        if path.name=='anchors.tmp':
            raise OSError('disk full')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'write_text',fail_record)
    page.on_message({'action':'apply','object_id':'123','instance':0,'hardware_confirmed':True})
    assert messages[-1].get('applied'),messages[-1]
    assert 'could not be saved' in messages[-1]['warning']
    page.on_message({'action':'restore','object_id':'123','instance':0})
    assert messages[-1].get('restored'),messages[-1]


def test_later_plate_uses_world_bed_and_exclusions(host,monkeypatch):
    page,messages,directory,obj,volume=host
    calls,plater=install_bridge(host,monkeypatch)
    import numpy as np
    matrix=np.eye(4);matrix[:2,3]=[400,-300]
    obj.instances()[0].matrix=lambda:matrix
    plater.instance_plate=lambda object_id,instance:{'index':1,'origin':[400,-300,0]}
    request={'action':'apply','object_id':'123','instance':0,'hardware_confirmed':True}
    page.on_message(request)
    assert messages[-1].get('applied'),messages[-1]
    assert np.min(np.array(calls[0]['flange']['vertices'])[:,0])>=400
    page.on_message({'action':'restore','object_id':'123','instance':0})
    page.on_message(dict(request,action='generate'))
    assert 'output' in messages[-1],messages[-1]
    from zipfile import ZipFile
    import xml.etree.ElementTree as ET
    with ZipFile(messages[-1]['output']) as archive:
        model=ET.fromstring(archive.read('3D/3dmodel.model'))
    ns={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
    vertices=model.findall('.//m:object[@id="1"]/m:mesh/m:vertices/m:vertex',ns)
    assert min(float(v.get('x')) for v in vertices)==100
    assert min(float(v.get('y')) for v in vertices)==100
    bundle=sys.modules['orca'].host.preset_bundle()
    previous=bundle.full_config_value
    bundle.full_config_value=lambda key:'125x90,135x90,135x130,125x130' if key=='bed_exclude_area' else previous(key)
    page.on_message(request)
    assert 'excluded region' in messages[-1]['error'].lower(),messages[-1]
    assert len(calls)==2  # Apply and restore only; the excluded-area attempt made no edit.


def test_other_plate_modifiers_do_not_block_selected_plate(host,monkeypatch):
    page,messages,directory,obj,volume=host
    calls,plater=install_bridge(host,monkeypatch)
    from copy import copy
    other=copy(obj);other.id=lambda:789
    modifier=copy(volume);modifier.id=lambda:999;modifier.is_model_part=lambda:False
    other.volumes=lambda:[modifier]
    sys.modules['orca'].host.model=lambda:SimpleNamespace(objects=lambda:[obj,other])
    plater.instance_plate=lambda object_id,instance:{'index':0 if object_id=='123' else 1,'origin':[0,0,0]}
    page.on_message({'action':'apply','object_id':'123','instance':0,'hardware_confirmed':True})
    assert messages[-1].get('applied'),messages[-1]
    assert len(calls)==1
    assert other.volumes()==[modifier]


@pytest.mark.parametrize('region',['0x0','0x0,0x0'])
@pytest.mark.parametrize('action',['generate','apply'])
def test_short_native_exclusion_sentinel_means_no_region(host,monkeypatch,region,action):
    page,messages,directory,obj,volume=host
    calls,plater=install_bridge(host,monkeypatch)
    bundle=sys.modules['orca'].host.preset_bundle()
    previous=bundle.full_config_value
    bundle.full_config_value=lambda key:region if key=='bed_exclude_area' else previous(key)
    page.on_message({'action':action,'object_id':'123','instance':0,'hardware_confirmed':True})
    assert ('output' in messages[-1] if action=='generate' else messages[-1].get('applied')),messages[-1]
    assert len(calls)==(1 if action=='apply' else 0)


@pytest.mark.parametrize('region',[
    '125x90,140x110,125x130',
    '125x90,135x90,140x110,135x130,125x130',
])
@pytest.mark.parametrize('action',['generate','apply'])
def test_arbitrary_native_exclusion_polygon_blocks_anchor(host,monkeypatch,region,action):
    page,messages,directory,obj,volume=host
    calls,plater=install_bridge(host,monkeypatch)
    bundle=sys.modules['orca'].host.preset_bundle()
    previous=bundle.full_config_value
    bundle.full_config_value=lambda key:region if key=='bed_exclude_area' else previous(key)
    page.on_message({'action':action,'object_id':'123','instance':0,'hardware_confirmed':True})
    assert 'excluded region' in messages[-1]['error'].lower(),messages[-1]
    assert calls==[]
    assert obj.volumes()==[volume]


@pytest.mark.parametrize('action',['generate','apply'])
def test_self_intersecting_native_exclusion_polygon_is_rejected(host,monkeypatch,action):
    page,messages,directory,obj,volume=host
    calls,plater=install_bridge(host,monkeypatch)
    bundle=sys.modules['orca'].host.preset_bundle()
    previous=bundle.full_config_value
    bundle.full_config_value=lambda key:'125x90,140x130,125x130,140x90' if key=='bed_exclude_area' else previous(key)
    page.on_message({'action':action,'object_id':'123','instance':0,'hardware_confirmed':True})
    assert 'exclu' in messages[-1]['error'].lower(),messages[-1]
    assert calls==[]
    assert obj.volumes()==[volume]


def test_check_valid_dimensions_does_not_edit_or_save(host,monkeypatch):
    page,messages,directory,obj,volume=host
    calls,_=install_bridge(host,monkeypatch)
    page.on_message({'action':'check','object_id':'123','instance':0,'hardware_confirmed':True})
    assert messages[-1].get('checked'),messages[-1]
    assert messages[-1]['report']['effective_flange_height_mm']==0.8
    assert calls==[] and obj.volumes()==[volume]
    assert list(directory.iterdir())==[]


def test_invalid_dimensions_suggest_geometry_checked_defaults(host):
    page,messages,directory,obj,volume=host
    request={'action':'check','object_id':'123','instance':0,'hardware_confirmed':True,
             'settings':{'overlap':5,'main_slot':2,'anchor_slot':1}}
    page.on_message(request)
    suggestion=messages[-1]['suggestion']
    assert suggestion['overlap']==2 and suggestion['gap']==0
    assert (suggestion['main_slot'],suggestion['anchor_slot'])==(2,1)
    page.on_message(dict(request,settings=suggestion))
    assert messages[-1].get('checked'),messages[-1]
    assert list(directory.iterdir())==[]


def test_near_bed_edge_suggests_compact_geometry_only_after_check(host):
    page,messages,directory,obj,volume=host
    import numpy as np
    matrix=np.eye(4);matrix[0,3]=-90
    obj.instances()[0].matrix=lambda:matrix
    page.on_message({'action':'check','object_id':'123','instance':0,'hardware_confirmed':True})
    assert messages[-1]['suggestion']['flange_width']==2
    assert messages[-1]['suggestion']['anchor_width']==3
    assert 'bed' in messages[-1]['error']
    assert list(directory.iterdir())==[]


@pytest.mark.parametrize('problem',['hardware','bed','slots','schedule'])
def test_check_never_offers_unverified_suggestion(host,problem):
    page,messages,directory,obj,volume=host
    request={'action':'check','object_id':'123','instance':0,'hardware_confirmed':True}
    if problem=='hardware':request['hardware_confirmed']=False
    if problem=='slots':request['settings']={'main_slot':1,'anchor_slot':1}
    if problem=='schedule':request['layer_boundaries_mm']=[0.2,0.2]
    if problem=='bed':
        import numpy as np
        matrix=np.eye(4);matrix[0,3]=-200
        obj.instances()[0].matrix=lambda:matrix
    page.on_message(request)
    assert 'error' in messages[-1] and 'suggestion' not in messages[-1]
    assert 'No verified' in messages[-1]['error']
    assert list(directory.iterdir())==[]


def test_advanced_apply_export_and_restore_use_existing_bridge(host,monkeypatch):
    page,messages,directory,obj,volume=host
    calls,_=install_bridge(host,monkeypatch)
    request={'action':'apply','object_id':'123','instance':0,'hardware_confirmed':True,
             'settings':{'advanced_anchor':True,'beam_width':0.8,'beam_spacing':10,'beam_model_gap':0.6}}
    page.on_message(request)
    assert messages[-1].get('applied'),messages[-1]
    assert messages[-1]['report']['beam_count']>=8
    assert len(obj.volumes())==3 and len(calls)==1
    assert json.loads((directory/'settings.json').read_text())['advanced_anchor'] is True
    page.on_message(dict(request,action='generate'))
    assert 'output' in messages[-1],messages[-1]
    assert messages[-1]['report']['settings']['advanced_anchor'] is True
    page.on_message({'action':'restore','object_id':'123','instance':0})
    assert messages[-1].get('restored') and obj.volumes()==[volume]


def test_checked_suggestion_preserves_advanced_mode(host):
    page,messages,directory,obj,volume=host
    page.on_message({'action':'check','object_id':'123','instance':0,'hardware_confirmed':True,
                     'settings':{'advanced_anchor':True,'beam_width':0.4}})
    assert messages[-1]['suggestion']['advanced_anchor'] is True
    assert messages[-1]['suggestion']['beam_width']==0.8
    assert messages[-1]['report']['beam_count']>0
    assert list(directory.iterdir())==[]
