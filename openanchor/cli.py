"""Command-line generator; all world placement and printer bounds are explicit."""
import argparse
import json
from pathlib import Path
import sys
from zipfile import ZipFile
from shapely.geometry import Polygon
from .settings import Settings, layer_boundaries
from .geometry import generate, transformed
from .assembly_io import load_mesh, write_3mf, export_stls
from .materials import screen_material


def main(argv=None):
    parser = argparse.ArgumentParser(description="OpenAnchor experimental aligned multi-material 3MF export")
    parser.add_argument("input", type=Path, help="Bed-positioned STL/OBJ, millimetres, Z=0 contact")
    parser.add_argument("--config", type=Path, required=True, help="Geometry, bed, layer and material JSON configuration")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stls", type=Path, help="Also export aligned component STLs")
    args = parser.parse_args(argv)
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        if args.output.resolve() in {args.input.resolve(), args.config.resolve()}:
            raise ValueError("Output must not overwrite the input or configuration")
        if args.stls and any((args.stls / name).resolve() in {args.input.resolve(), args.config.resolve()} for name in ("model.stl", "flange.stl", "anchor.stl", "report.json")):
            raise ValueError("STL export must not overwrite the input or configuration")
        if config.get("multimaterial_confirmed") is not True:
            raise ValueError("Confirm multi-material hardware/profile in configuration before export")
        mesh = load_mesh(args.input)
        if "transform" in config:
            mesh = transformed(mesh, config["transform"])
        settings = Settings(**config.get("settings", {}))
        boundaries = config.get("layer_boundaries_mm")
        schedule_source = "explicit layer boundaries"
        if boundaries is None:
            if config.get("variable_layers", False):
                raise ValueError("Variable layers require explicit resolved layer_boundaries_mm")
            boundaries = layer_boundaries(config["initial_layer_height_mm"], config["layer_height_mm"], settings.flange_height + settings.cap_thickness + 1)
            schedule_source = "explicit constant-height fallback; must match the imported slicer process"
        assembly = generate(mesh, settings, boundaries, Polygon(config["bed_polygon_mm"]),
                            slots=config["filament_slots"], excluded=[Polygon(p) for p in config.get("excluded_polygons_mm", [])])
        assembly.report["layer_schedule_source"] = schedule_source
        assembly.report["material_screening"] = screen_material(**config.get("material", {"anchor_name": "User-defined"}))
        profile = None
        if config.get("slicer_project"):
            project = Path(config["slicer_project"])
            if not project.is_absolute():
                project = args.config.parent / project
            if args.output.resolve() == project.resolve():
                raise ValueError("Output must not overwrite the supplied slicer project")
            with ZipFile(project) as archive:
                profile = json.loads(archive.read("Metadata/project_settings.config"))
        write_3mf(args.output, assembly, project_settings=profile)
        if args.stls:
            export_stls(args.stls, assembly)
        print(json.dumps({"output": str(args.output.resolve()), "report": assembly.report}, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"OpenAnchor: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
