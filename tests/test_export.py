import json
from zipfile import ZipFile
import xml.etree.ElementTree as ET
import numpy as np
from shapely.geometry import box
from openanchor.assembly_io import write_3mf, load_mesh
from openanchor.geometry import generate, prism
from openanchor.settings import Settings, layer_boundaries
from openanchor.materials import screen_material
from openanchor.cli import main


def test_assembly_roundtrip(tmp_path):
    assembly = generate(prism(box(50,50,70,70),0,10), Settings(), layer_boundaries(.2,.2,3), box(0,0,256,256))
    path = tmp_path/'assembly.3mf'; write_3mf(path, assembly, object_config={'brim_type':'outer_only'}, model_config={'wall_loops':'3'})
    first = path.read_bytes(); write_3mf(path, assembly, object_config={'brim_type':'outer_only'}, model_config={'wall_loops':'3'})
    assert first == path.read_bytes()
    with ZipFile(path) as archive:
        cfg = ET.fromstring(archive.read('Metadata/model_settings.config'))
        assert [v.get('value') for v in cfg.findall(".//object/metadata[@key='brim_type']")] == ['no_brim']
        assert [p.find("metadata[@key='extruder']").get('value') for p in cfg.findall('.//part')] == ['1','1','2']
        parts = cfg.findall('.//part')
        assert parts[1].find("metadata[@key='wall_loops']").get('value') == '100'
        assert parts[0].find("metadata[@key='wall_loops']").get('value') == '3'
        assert parts[2].find("metadata[@key='wall_loops']") is None
        assert assembly.report['settings']['gap'] == 0
        report = json.loads(archive.read('Metadata/openanchor.json'))
        assert len(json.loads(archive.read('Metadata/project_settings.config'))['filament_settings_id']) == 2
        assert report['effective_flange_height_mm'] == .8
        model = ET.fromstring(archive.read('3D/3dmodel.model')); ns = {'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
        assert len(model.findall('.//m:component',ns)) == 3
        vertices = model.findall('.//m:object[@id="1"]/m:mesh/m:vertices/m:vertex',ns)
        assert np.array_equal([[float(v.get(c)) for c in ['x','y','z']] for v in vertices], assembly.model.vertices)


def test_cli_and_materials(tmp_path, capsys):
    path=tmp_path/'part.stl'; prism(box(50,50,70,70),0,10).export(path)
    assert load_mesh(path).is_volume
    config={'filament_slots':2,'multimaterial_confirmed':True,'initial_layer_height_mm':.3,'layer_height_mm':.2,'bed_polygon_mm':[[0,0],[256,0],[256,256],[0,256]]}
    cfg=tmp_path/'config.json'; cfg.write_text(json.dumps(config))
    assert main([str(path),'--config',str(cfg),'--output',str(tmp_path/'a.3mf')]) == 0
    config['variable_layers']=True; cfg.write_text(json.dumps(config))
    assert main([str(path),'--config',str(cfg),'--output',str(tmp_path/'b.3mf')]) == 2
    assert 'resolved' in capsys.readouterr().err
    risks=screen_material('PLA',bed_temperature=90)
    assert any(m['level']=='estimated risk' for m in risks)
    risks=screen_material('custom',nozzle_range=[200,250],nozzle_temperature=300)
    assert any(m['level']=='known incompatibility' for m in risks)
