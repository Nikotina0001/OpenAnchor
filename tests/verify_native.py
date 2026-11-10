"""Optional isolated Orca CLI integration check. Never send this synthetic G-code to a printer."""
import argparse
import json
from pathlib import Path
import re
import subprocess
from zipfile import ZipFile, ZIP_DEFLATED


def run(executable, *args):
    result = subprocess.run([str(executable), *map(str, args)], capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f"Orca exited {result.returncode}: {result.stdout[-1500:]} {result.stderr[-1500:]}")
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--orca',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    work=root/'.audit'/'native-verification'; work.mkdir(parents=True,exist_ok=True)
    profile=work/'defaults.json'
    run(args.orca,'--datadir',work,'--export-settings',profile)
    settings=json.loads(profile.read_text())
    # Synthetic two-tool profile, for toolpath validation only, without a machine start routine.
    settings={k: v*2 if isinstance(v,list) and len(v)==1 else v for k,v in settings.items()}
    settings.update({'filament_settings_id':['OpenAnchor main test','OpenAnchor anchor test'],
        'filament_colour':['#9565E8','#353B43'],'filament_type':['PLA','PLA'],
        'filament_diameter':['1.75','1.75'],'filament_density':['1.24','1.24'],
        'layer_change_gcode':'G92 E0','enable_prime_tower':'0',
        'nozzle_diameter':['0.4','0.4'],'single_extruder_multi_material':'0',
        'machine_start_gcode':'G90\nG21\nM83','machine_end_gcode':'',
        'printable_area':['0x0','256x0','256x256','0x256'],'printable_height':'256',
        'flush_volumes_matrix':['0','140','140','0']*2,'flush_volumes_vector':['140']*4,
        'inherits_group':['']*4,'filament_map':['1','2'],'filament_map_2':['1','2'],
        'brim_type':'no_brim','skirt_loops':'0'})
    target=work/'test-assembly.3mf'
    with ZipFile(root/'examples'/'openanchor-demo.3mf') as source, ZipFile(target,'w',ZIP_DEFLATED) as output:
        for name in source.namelist():
            output.writestr(name,json.dumps(settings).encode() if name=='Metadata/project_settings.config' else source.read(name))
    run(args.orca,'--datadir',work,'--slice','0','--outputdir',work,target)
    gcode=(work/'plate_1.gcode').read_text()
    tools=set(re.findall(r'^T(\d+)\s*$',gcode,re.M))
    assert {'0','1'} <= tools, f'Both native tool assignments required, got {tools}'
    assert '; total layer number: 50' in gcode
    report={'orca':str(args.orca),'two_tools':sorted(tools),'native_slice':'passed','layers':50,
            'note':'Synthetic two-extruder validation fixture; not a physical printer profile. No physical results.'}
    (root/'docs').mkdir(exist_ok=True)
    (root/'docs'/'native-verification.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
