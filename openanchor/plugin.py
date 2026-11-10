"""Real OrcaSlicer Pages capability. Host reads stay in the UI callback."""
import json
from uuid import uuid4
from zipfile import ZipFile
from pathlib import Path
import numpy as np
import trimesh
from shapely.geometry import Polygon
from shapely.affinity import translate
import orca
from .settings import Settings, layer_boundaries, FLANGE_WALL_LOOPS
from .geometry import generate, transformed
from .assembly_io import write_3mf
from .materials import screen_material


def number(value):
    if isinstance(value, (list, tuple)):
        value = value[0]
    return float(str(value).strip('"').split(',')[0])


def points(value):
    if isinstance(value, str):
        return [[float(c) for c in p.split('x')] for p in value.split(',') if p]
    return value


def snapshot_volume(volume, instance, *, allow_paint=False):
    if not volume.is_model_part():
        raise ValueError("Modifiers and negative volumes are unsupported")
    if not allow_paint and any(check() for check in (volume.is_mm_painted, volume.is_seam_painted, volume.is_fdm_support_painted, volume.is_fuzzy_skin_painted)):
        raise ValueError("Painted objects are unsupported: geometry-only export would lose their painting")
    raw = volume.mesh()
    mesh = trimesh.Trimesh(vertices=np.array(raw.vertices(), copy=True), faces=np.array(raw.triangles(), copy=True), process=False)
    return transformed(mesh, np.array(instance.matrix()) @ np.array(volume.matrix()))


def snapshot_mesh(obj, instance, source_id=None):
    volumes = obj.volumes()
    if source_id is None:
        if len(volumes) != 1:
            raise ValueError("Select a single-part model or an assembly managed by OpenAnchor")
        volume = volumes[0]
    else:
        volume = next((v for v in volumes if str(v.id()) == source_id), None)
        if volume is None:
            raise ValueError("Original model changed; refresh the object list")
    return snapshot_volume(volume, instance)


class OpenAnchorPage(orca.pages.PagesPluginCapabilityBase):
    def get_name(self):
        return "OpenAnchor"

    def get_ui(self):
        return Path(__file__).with_name("page.html").read_text(encoding="utf-8")

    def storage(self):
        return Path(orca.host.plugin.storage())

    def bridge_available(self):
        plater = orca.host.plater()
        return all(callable(getattr(plater, name, None)) for name in ("apply_anchor", "restore_anchor", "instance_plate"))

    def records(self):
        if not hasattr(self, "_records"):
            path = self.storage() / "anchors.json"
            self._records = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            if not isinstance(self._records, dict):
                raise ValueError("OpenAnchor ownership records are invalid; project was not changed")
        return self._records

    def managed_record(self, obj):
        records = self.records().get(str(obj.id()), [])
        current = {str(v.id()) for v in obj.volumes()}
        for record in reversed(records):
            expected = {record["source_volume_id"], *record["generated_volume_ids"]}
            if current == expected and len(current) == 3:
                return record
        return None

    def save_record(self, record):
        # Keep earlier IDs so native Undo/Redo can recover ownership without guessing by name.
        self.records().setdefault(record["object_id"], []).append(record)
        path = self.storage() / "anchors.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.records(), indent=2), encoding="utf-8")
        temporary.replace(path)

    def selected(self, data):
        obj = next((obj for obj in orca.host.model().objects() if str(obj.id()) == str(data.get("object_id"))), None)
        if obj is None:
            raise ValueError("Object changed or was removed; refresh the object list")
        index = data.get("instance")
        if type(index) is not int or not 0 <= index < len(obj.instances()):
            raise ValueError("Invalid object instance; refresh the object list")
        if not obj.instances()[index].printable:
            raise ValueError("Selected instance is not printable")
        return obj, index

    def on_message(self, data):
        try:
            if not isinstance(data, dict):
                raise ValueError("Invalid OpenAnchor request")
            action = data.get("action")
            if action == "refresh":
                self.refresh()
            elif action == "generate":
                self.generate(data)
            elif action == "apply":
                self.apply(data)
            elif action == "restore":
                self.restore(data)
            elif action == "check":
                self.check(data)
            else:
                raise ValueError("Unknown OpenAnchor action")
        except Exception as exc:
            self.post_message({"error": f"OpenAnchor could not complete this action: {exc}"})

    def check(self, data):
        try:
            settings, *_, result = self.prepare(data)
            if not settings.enabled:
                raise ValueError("Enable OpenAnchor geometry before checking its dimensions")
        except ValueError as exc:
            current = data.get("settings", {})
            candidate = Settings(main_slot=current.get("main_slot", 1),
                                 anchor_slot=current.get("anchor_slot", 2),
                                 advanced_anchor=current.get("advanced_anchor", False)).to_dict()
            for dimensions in ({}, {"flange_width": 2.0, "anchor_width": 3.0, "overlap": 1.0}):
                proposed = dict(candidate, **dimensions)
                try:
                    *_, result = self.prepare(dict(data, settings=proposed))
                except ValueError:
                    continue
                self.post_message({"error": str(exc), "suggestion": proposed,
                                   "report": result.report})
                return
            self.post_message({"error": f"{exc}. No verified setting suggestion found. Check the model, bed position, materials and layer schedule."})
            return
        self.post_message({"checked": True, "report": result.report})

    def refresh(self):
        objects = []
        for obj in orca.host.model().objects():
            managed = self.managed_record(obj) is not None
            for index, instance in enumerate(obj.instances()):
                if instance.printable:
                    objects.append({"id": str(obj.id()), "instance": index,
                                    "label": f"{obj.name} / instance {index + 1}", "managed": managed})
        presets = orca.host.preset_bundle().current_filament_preset_names()
        saved = {}
        path = self.storage() / "settings.json"
        if path.exists():
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                saved = {}
        self.post_message({"objects": objects, "filaments": list(presets), "settings": saved,
                           "bridge_available": self.bridge_available()})

    def prepare(self, data):
        if data.get("hardware_confirmed") is not True:
            raise ValueError("Confirm a physically compatible multi-material printer/profile first")
        settings = Settings(**data.get("settings", {}))
        bundle = orca.host.preset_bundle()
        names = bundle.current_filament_preset_names()
        settings.validate(len(names))
        model = orca.host.model()
        obj, index = self.selected(data)
        instance = obj.instances()[index]
        record = self.managed_record(obj)
        source_id = record["source_volume_id"] if record else None
        mesh = snapshot_mesh(obj, instance, source_id)
        volume = next((v for v in obj.volumes() if str(v.id()) == source_id), None) if record else obj.volumes()[0]
        full = bundle.full_config_value
        bed = Polygon(points(full("printable_area")))
        exclusion_points = points(full("bed_exclude_area") or [])
        excluded = []
        # Orca uses fewer than three points for an empty region, otherwise one polygon.
        if len(exclusion_points) >= 3:
            region = Polygon(exclusion_points)
            if not region.is_valid or region.area <= 0:
                raise ValueError("Cannot interpret this printer's exclusion region")
            excluded = [region]
        plate_context = getattr(orca.host.plater(), "instance_plate", None)
        plate = None
        if callable(plate_context):
            plate = plate_context(str(obj.id()), index)
            origin = plate["origin"]
            if len(origin) != 3 or not np.isfinite(origin).all() or abs(origin[2]) > 1e-6:
                raise ValueError("Unsupported plate origin; project was not changed")
            bed = translate(bed, xoff=origin[0], yoff=origin[1])
            excluded = [translate(region, xoff=origin[0], yoff=origin[1]) for region in excluded]
        # The live UI model does not expose a resolved slicing layer graph.
        schedule = data.get("layer_boundaries_mm")
        source = "user-supplied resolved schedule"
        if not schedule:
            if obj.has_custom_layering():
                raise ValueError("Adaptive/variable layers require the resolved layer-boundary JSON list")
            initial = number(full("initial_layer_print_height"))
            regular = number(obj.config_value("layer_height") or full("layer_height"))
            schedule = layer_boundaries(initial, regular, settings.flange_height + settings.cap_thickness + 1)
            source = "constant-height preset fallback; verify process settings in Preview"
        obstacles = []
        for other in model.objects():
            for j, other_instance in enumerate(other.instances()):
                if other.id() == obj.id() and j == index or not other_instance.printable:
                    continue
                if plate is not None and plate_context(str(other.id()), j)["index"] != plate["index"]:
                    continue
                for other_volume in other.volumes():
                    obstacles.append(snapshot_volume(other_volume, other_instance, allow_paint=True))
        result = generate(mesh, settings, schedule, bed, slots=len(names), excluded=excluded, obstacles=obstacles)
        filament = bundle.current_filament_presets()[settings.anchor_slot - 1]
        def thermal(key):
            value = filament.config_value(key) if filament is not None else None
            return number(value) if value is not None else None
        bed_key = {"Textured PEI Plate": "textured_plate_temp", "High Temp Plate": "hot_plate_temp", "Cool Plate": "cool_plate_temp", "Engineering Plate": "eng_plate_temp"}.get(str(full("curr_bed_type")))
        result.report["layer_schedule_source"] = source
        result.report["material_screening"] = screen_material(names[settings.anchor_slot - 1], bed_temperature=thermal(bed_key) if bed_key else None, nozzle_temperature=thermal("nozzle_temperature"))
        result.report["source_object_id"] = str(obj.id())
        result.report["original_slot"] = max(1, volume.extruder_id())
        result.report["source_instance"] = index
        result.report["filament_names"] = list(names)
        result.report["source_plate_origin_mm"] = list(plate["origin"]) if plate is not None else [0, 0, 0]
        result.report["limitations"] = ["Wipe tower and toolhead swept volumes must be checked in native Preview."]
        return settings, obj, index, volume, record, result

    def save_settings(self, settings):
        (self.storage() / "settings.json").write_text(json.dumps(settings.to_dict(), indent=2), encoding="utf-8")

    def generate(self, data):
        settings, obj, index, volume, record, result = self.prepare(data)
        result.report["flange_wall_loops"] = FLANGE_WALL_LOOPS
        result.report["limitations"].append("Assembly export: supports and painted models are not exported.")
        # A standalone assembly uses its plate's local coordinates, without the virtual workspace offset.
        for part in (result.model, result.flange, result.anchor):
            if part is not None:
                part.apply_translation(-np.asarray(result.report["source_plate_origin_mm"]))
        result.report["export_coordinate_frame"] = "source plate local"
        output = self.storage() / "exports" / f"object-{obj.id()}-instance-{index}.3mf"
        # Native export copies resolved process/printer/filament profiles without editing the project.
        snapshot = self.storage() / "profile-snapshot.3mf"
        try:
            orca.host.plater().export_3mf_copy(str(snapshot))
            with ZipFile(snapshot) as archive:
                profile = json.loads(archive.read("Metadata/project_settings.config"))
            write_3mf(output, result, project_settings=profile,
                      object_config={key: obj.config_value(key) for key in obj.config_keys()},
                      model_config={key: volume.config_value(key) for key in volume.config_keys()})
        finally:
            snapshot.unlink(missing_ok=True)
        self.save_settings(settings)
        self.post_message({"output": str(output), "report": result.report})

    def apply(self, data):
        if not self.bridge_available():
            raise ValueError("Direct plate editing requires the OpenAnchor edition of OrcaSlicer; assembly export is available")
        obj, index = self.selected(data)
        if len(obj.instances()) != 1:
            raise ValueError("Direct plate editing requires an object with one instance; make the instance a separate object first")
        if data.get("settings", {}).get("enabled") is False:
            return self.restore(data)
        settings, obj, index, volume, record, result = self.prepare(data)
        def payload(mesh):
            return {"vertices": mesh.vertices.tolist(), "triangles": mesh.faces.tolist()}
        request = dict(record) if record else {"object_id": str(obj.id()), "source_volume_id": str(volume.id()), "generated_volume_ids": []}
        request.update(instance=index, flange=payload(result.flange), anchor=payload(result.anchor),
                       main_slot=settings.main_slot, anchor_slot=settings.anchor_slot)
        backup = None
        if record is None:
            directory = self.storage() / "backups"
            directory.mkdir(parents=True, exist_ok=True)
            backup = directory / f"before-anchor-{uuid4().hex}.3mf"
            orca.host.plater().export_3mf_copy(str(backup))
            if not backup.is_file() or backup.stat().st_size == 0:
                raise ValueError("The project backup was not written; plate was not changed")
        # No obj/volume handle may be read after the bridge replaces its model object.
        updated = dict(orca.host.plater().apply_anchor(request))
        updated["backup"] = str(backup) if backup else record.get("backup")
        warning = f"Set the OpenAnchor flange part's Wall loops to {FLANGE_WALL_LOOPS} in OrcaSlicer. This plate bridge cannot set per-part wall loops; Export 3MF includes that override automatically."
        try:
            self.save_record(updated)
            self.save_settings(settings)
        except OSError:
            warning += " Anchor applied, but its settings could not be saved. Keep this session open and use Restore original or Undo before closing."
        self.post_message({"applied": True, "record": updated, "report": result.report,
                           "backup": updated["backup"], "warning": warning})

    def restore(self, data):
        if not self.bridge_available():
            raise ValueError("Direct plate editing requires the OpenAnchor edition of OrcaSlicer")
        obj, index = self.selected(data)
        if len(obj.instances()) != 1:
            raise ValueError("Restore requires an object with one instance")
        record = self.managed_record(obj)
        if record is None:
            raise ValueError("No matching OpenAnchor geometry to restore; refresh the object list")
        request = dict(record, instance=index)
        orca.host.plater().restore_anchor(request)
        self.post_message({"restored": True, "object_id": record["object_id"]})
