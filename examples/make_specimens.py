"""Create reproducible flat-contact specimens and four geometry controls."""
from pathlib import Path
from shapely.geometry import box
from openanchor.geometry import prism, generate, Assembly
from openanchor.settings import Settings, layer_boundaries
from openanchor.assembly_io import write_3mf, export_stls


def main():
    directory = Path(__file__).resolve().parent
    model = prism(box(90, 110, 150, 130), 0, 10)
    model.export(directory / "calibration-bar.stl")
    settings = Settings()
    assembly = generate(model, settings, layer_boundaries(.2,.2,3), box(0,0,256,256))
    write_3mf(directory / "openanchor-demo.3mf", assembly)
    export_stls(directory / "aligned-stls", assembly)
    original = Assembly(model, None, None, {"enabled": False, "control": "no brim"})
    write_3mf(directory / "control-no-brim.3mf", original)
    # Controls keep the part fixed. Conventional brim has only main-material ring.
    ring = prism(box(90,110,150,130).buffer(5, join_style='mitre').difference(box(90,110,150,130)),0,.2)
    # Export controls as STLs to avoid mislabelling them as OpenAnchor assemblies.
    ring.export(directory / "control-conventional-brim.stl")
    ring.export(directory / "control-second-material-no-interlock.stl")
    print(directory / "openanchor-demo.3mf")


if __name__ == '__main__':
    main()
