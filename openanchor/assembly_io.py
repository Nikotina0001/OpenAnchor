"""Aligned 3MF/STL output, without modifying source files or slicer projects."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo
import json
import os
import tempfile
import xml.etree.ElementTree as ET
import trimesh
from .geometry import Assembly, validate_mesh
from .settings import FLANGE_WALL_LOOPS

CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
ET.register_namespace("", CORE)


def load_mesh(path):
    path = Path(path)
    if path.suffix.lower() not in {".stl", ".obj"}:
        raise ValueError("Standalone input supports STL/OBJ; use the plugin for transformed assemblies")
    loaded = trimesh.load(path, force="scene", process=False)
    mesh = loaded.to_mesh()
    # STL stores unshared vertices; weld exact coordinates, without repairing topology.
    mesh.merge_vertices()
    validate_mesh(mesh)
    return mesh


def _xml(element):
    return ET.tostring(element, encoding="utf-8", xml_declaration=True)


def write_3mf(path, assembly: Assembly, *, project_settings=None, object_config=None, model_config=None):
    path = Path(path)
    if path.suffix.lower() != ".3mf":
        raise ValueError("Assembly export requires a .3mf filename")
    original_slot = assembly.report.get("original_slot", assembly.report.get("settings", {}).get("main_slot", 1))
    meshes = [("Original model", assembly.model, original_slot)]
    if assembly.flange is not None:
        s = assembly.report["settings"]
        meshes = [("Original model", assembly.model, s["main_slot"]),
                  ("OpenAnchor flange", assembly.flange, s["main_slot"]),
                  ("OpenAnchor anchor + clamp", assembly.anchor, s["anchor_slot"])]
    model = ET.Element(f"{{{CORE}}}model", unit="millimeter", attrib={"xml:lang": "en-US"})
    ET.SubElement(model, f"{{{CORE}}}metadata", name="Application").text = "OrcaSlicer-2.5.0"
    ET.SubElement(model, f"{{{CORE}}}metadata", name="BambuStudio:3mfVersion").text = "1"
    resources = ET.SubElement(model, f"{{{CORE}}}resources")
    parent_id = len(meshes) + 1
    config = ET.Element("config")
    obj_config = ET.SubElement(config, "object", id=str(parent_id))
    ET.SubElement(obj_config, "metadata", key="name", value="OpenAnchor assembly")
    ET.SubElement(obj_config, "metadata", key="extruder", value=str(meshes[0][2]))
    for key, value in (object_config or {}).items():
        if key not in {"name", "extruder"} and not (key == "brim_type" and assembly.flange is not None):
            ET.SubElement(obj_config, "metadata", key=key, value=str(value))
    if assembly.flange is not None:
        ET.SubElement(obj_config, "metadata", key="brim_type", value="no_brim")
    for index, (name, mesh, slot) in enumerate(meshes, 1):
        validate_mesh(mesh)
        obj = ET.SubElement(resources, f"{{{CORE}}}object", id=str(index), type="model", name=name)
        geometry = ET.SubElement(obj, f"{{{CORE}}}mesh")
        vertices = ET.SubElement(geometry, f"{{{CORE}}}vertices")
        for point in mesh.vertices:
            ET.SubElement(vertices, f"{{{CORE}}}vertex", **dict(zip(("x", "y", "z"), (format(float(v), '.17g') for v in point))))
        triangles = ET.SubElement(geometry, f"{{{CORE}}}triangles")
        for face in mesh.faces:
            ET.SubElement(triangles, f"{{{CORE}}}triangle", **dict(zip(("v1", "v2", "v3"), map(str, face))))
        part = ET.SubElement(obj_config, "part", id=str(index), subtype="normal_part")
        ET.SubElement(part, "metadata", key="name", value=name)
        ET.SubElement(part, "metadata", key="extruder", value=str(slot))
        if name == "OpenAnchor flange":
            ET.SubElement(part, "metadata", key="wall_loops", value=str(FLANGE_WALL_LOOPS))
        if index == 1:
            for key, value in (model_config or {}).items():
                if key not in {"name", "extruder"}:
                    ET.SubElement(part, "metadata", key=key, value=str(value))
    parent = ET.SubElement(resources, f"{{{CORE}}}object", id=str(parent_id), type="model", name="OpenAnchor assembly")
    components = ET.SubElement(parent, f"{{{CORE}}}components")
    for index in range(1, parent_id):
        ET.SubElement(components, f"{{{CORE}}}component", objectid=str(index))
    build = ET.SubElement(model, f"{{{CORE}}}build")
    ET.SubElement(build, f"{{{CORE}}}item", objectid=str(parent_id))
    entries = {
        "[Content_Types].xml": b'<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/><Default Extension="config" ContentType="application/xml"/><Default Extension="json" ContentType="application/json"/></Types>',
        "_rels/.rels": b'<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>',
        "3D/3dmodel.model": _xml(model),
        "Metadata/model_settings.config": _xml(config),
        "Metadata/openanchor.json": json.dumps(assembly.report, indent=2, allow_nan=False).encode(),
    }
    # Orca clamps volume extruders to the embedded filament-settings list on import.
    count = max(slot for _, _, slot in meshes)
    names = assembly.report.get("filament_names", [])
    identities = {
        "filament_settings_id": [names[i] if i < len(names) else f"OpenAnchor slot {i + 1} - configure before printing" for i in range(count)],
        "filament_colour": ["#9565E8" if i == 0 else "#353B43" for i in range(count)],
    }
    if project_settings is not None:
        if not isinstance(project_settings, dict) or len(project_settings.get("filament_settings_id", [])) < count:
            raise ValueError("Supplied slicer profile has too few filament slots")
        identities = project_settings
    entries["Metadata/project_settings.config"] = json.dumps(identities, allow_nan=False).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, staging = tempfile.mkstemp(prefix=".openanchor-", suffix=".3mf", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
                for name, data in entries.items():
                    info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                    info.compress_type = ZIP_DEFLATED
                    archive.writestr(info, data)
        os.replace(staging, path)
    except BaseException:
        Path(staging).unlink(missing_ok=True)
        raise


def export_stls(directory, assembly):
    directory = Path(directory)
    if assembly.flange is None and any((directory / name).exists() for name in ("flange.stl", "anchor.stl")):
        raise ValueError("Choose a new STL directory for disabled output; existing anchor files would be stale")
    directory.mkdir(parents=True, exist_ok=True)
    for name, mesh in (("model", assembly.model), ("flange", assembly.flange), ("anchor", assembly.anchor)):
        if mesh is not None:
            mesh.export(directory / f"{name}.stl")
    (directory / "report.json").write_text(json.dumps(assembly.report, indent=2, allow_nan=False), encoding="utf-8")
