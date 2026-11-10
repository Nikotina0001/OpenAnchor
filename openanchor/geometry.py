"""External-only anchor geometry in world coordinates, independent of Orca/UI."""
from dataclasses import dataclass
import hashlib
import numpy as np
import trimesh
import manifold3d
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
from .settings import Settings, align_heights
from .beams import beam_footprint

EPS = 1e-6


def polygons(shape):
    return [shape] if isinstance(shape, Polygon) else list(shape.geoms)


def validate_mesh(mesh):
    if not isinstance(mesh, trimesh.Trimesh) or not len(mesh.faces):
        raise ValueError("Input must be a nonempty triangle mesh")
    if not np.isfinite(mesh.vertices).all() or not np.isfinite(mesh.area_faces).all():
        raise ValueError("Mesh contains non-finite coordinates")
    if np.any(mesh.area_faces <= 1e-12):
        raise ValueError("Mesh contains degenerate triangles")
    if not mesh.is_volume:
        raise ValueError("Mesh must be watertight, consistently wound and have positive volume")


def transformed(mesh, matrix):
    matrix = np.asarray(matrix, dtype=float)
    if matrix.shape != (4, 4) or not np.isfinite(matrix).all() or not np.allclose(matrix[3], [0, 0, 0, 1]) or abs(np.linalg.det(matrix[:3, :3])) < 1e-12:
        raise ValueError("Transform must be a finite invertible affine 4×4 matrix")
    result = mesh.copy()
    result.apply_transform(matrix)
    validate_mesh(result)
    return result


def contact_footprint(mesh):
    """Use actual coplanar bed triangles, never a bounding box or silhouette."""
    if abs(mesh.bounds[0, 2]) > EPS:
        raise ValueError("Model must already touch Z=0; OpenAnchor will not reposition it")
    bottom = mesh.triangles[np.all(np.abs(mesh.triangles[:, :, 2]) <= EPS, axis=1)]
    shape = unary_union([Polygon(t[:, :2]) for t in bottom])
    if shape.is_empty or shape.area <= EPS or not shape.is_valid or not isinstance(shape, (Polygon, MultiPolygon)):
        raise ValueError("No valid area of planar bed contact; point/line contact is unsupported")
    return shape


def lower_outline(mesh, height):
    """Project triangles clipped at the clamp top, including sloped lower walls."""
    pieces = []
    for triangle in mesh.triangles:
        clipped = []
        for a, b in zip(triangle, np.roll(triangle, -1, axis=0)):
            if a[2] <= height:
                clipped.append(a[:2])
            if (a[2] <= height) != (b[2] <= height):
                clipped.append((a + (b - a) * ((height - a[2]) / (b[2] - a[2])))[:2])
        if len(clipped) >= 3:
            polygon = Polygon(clipped)
            if polygon.area > 1e-12:
                pieces.append(polygon)
    return unary_union(pieces)


def prism(shape, bottom, top):
    if shape.is_empty or not shape.is_valid or shape.area <= EPS or top - bottom <= EPS:
        raise ValueError("Offset collapsed or produced invalid/zero-area geometry")
    pieces = []
    for p in polygons(shape):
        piece = trimesh.creation.extrude_polygon(p, top - bottom, engine="earcut")
        piece.apply_translation([0, 0, bottom])
        pieces.append(piece)
    result = trimesh.util.concatenate(pieces)
    if np.any(result.area_faces <= 1e-12):
        # Earcut can emit collinear cap triangles where slots meet a rotated contour.
        contours = []
        for p in polygons(shape):
            contours.extend([np.asarray(p.exterior.coords)[:-1],
                             *(np.asarray(ring.coords)[:-1] for ring in p.interiors)])
        section = manifold3d.CrossSection(contours, manifold3d.FillRule.EvenOdd)
        output = section.extrude(top - bottom).translate([0, 0, bottom]).to_mesh64()
        result = trimesh.Trimesh(vertices=output.vert_properties, faces=output.tri_verts, process=False)
    validate_mesh(result)
    return result


def intersection_volume(a, b):
    return abs((solid(a) ^ solid(b)).volume())


def solid(mesh):
    result = manifold3d.Manifold(manifold3d.Mesh64(
        vert_properties=np.array(mesh.vertices, dtype=np.float64, order="C", copy=True),
        tri_verts=np.array(mesh.faces, dtype=np.uint64, order="C", copy=True)))
    if result.status() != manifold3d.Error.NoError:
        raise ValueError(f"Invalid solid topology: {result.status()}")
    return result


def native_precision(mesh):
    """Resolve collinear faces after conversion to the native bridge's float vertices."""
    rounded = trimesh.Trimesh(mesh.vertices.astype(np.float32), mesh.faces, process=False)
    output = solid(rounded).to_mesh64()
    result = trimesh.Trimesh(vertices=output.vert_properties, faces=output.tri_verts, process=False)
    validate_mesh(result)
    return result


@dataclass
class Assembly:
    model: trimesh.Trimesh
    flange: trimesh.Trimesh | None
    anchor: trimesh.Trimesh | None
    report: dict


def generate(mesh, settings: Settings, boundaries, bed, *, slots=2, excluded=(), obstacles=()):
    validate_mesh(mesh)
    fingerprint = hashlib.sha256(mesh.vertices.astype('<f8').tobytes() + mesh.faces.astype('<i8').tobytes()).hexdigest()
    if not settings.enabled:
        return Assembly(mesh.copy(), None, None, {"enabled": False, "source_sha256": fingerprint, "settings": settings.to_dict()})
    settings.validate(slots)
    if bed.is_empty or not bed.is_valid or not isinstance(bed, (Polygon, MultiPolygon)):
        raise ValueError("A valid printable bed polygon is required")
    h, top = align_heights(settings, boundaries)
    footprint = contact_footprint(mesh)
    # Filled exterior rings keep the flange outside the original bed-contact holes.
    base_exterior = unary_union([Polygon(p.exterior) for p in polygons(footprint)])
    outline = lower_outline(mesh, top)
    exterior = unary_union([Polygon(p.exterior) for p in polygons(outline)])
    outer_flange = exterior.buffer(settings.flange_width, join_style="mitre")
    flange_inner = base_exterior
    if settings.flange_object_gap > 0:
        # Clear the full lower wall envelope; slopes may have a larger gap near the bed.
        flange_outline = lower_outline(mesh, h)
        flange_inner = unary_union([Polygon(p.exterior) for p in polygons(flange_outline)])
        flange_inner = flange_inner.buffer(settings.flange_object_gap, join_style="mitre")
    flange_xy = outer_flange.difference(flange_inner)
    anchor_outer = exterior.buffer(settings.flange_width + settings.gap + settings.anchor_width, join_style="mitre")
    anchor_xy = anchor_outer.difference(exterior.buffer(settings.flange_width + settings.gap, join_style="mitre"))
    cap_xy = anchor_outer.difference(exterior.buffer(settings.flange_width - settings.overlap, join_style="mitre"))
    beam_xy = Polygon()
    beam_count = corner_count = 0
    slot_gap = settings.gap
    fit_tolerance = None
    if settings.advanced_anchor:
        magnitude = max(1.0, *(abs(value) for value in anchor_outer.bounds))
        fit_tolerance = max(1e-4, 8 * float(np.spacing(np.float32(magnitude))))
        if settings.flange_object_gap < fit_tolerance:
            flange_outline = lower_outline(mesh, h)
            flange_inner = unary_union([Polygon(p.exterior) for p in polygons(flange_outline)])
            flange_xy = outer_flange.difference(flange_inner.buffer(fit_tolerance, join_style="mitre"))
        anchor_xy = anchor_outer.difference(exterior.buffer(settings.flange_width + max(settings.gap, fit_tolerance),
                                                            join_style="mitre"))
        beam_xy, beam_count, corner_count = beam_footprint(exterior, anchor_xy, cap_xy, settings,
                                                        fit_tolerance=fit_tolerance)
        # A microscopic fit allowance prevents float conversion from overlapping rib/slot faces.
        slot_gap = max(settings.gap, fit_tolerance)
        slots = beam_xy.buffer(slot_gap, join_style="mitre")
        flange_xy = flange_xy.difference(slots)
        if flange_xy.is_empty or flange_xy.area <= EPS or cap_xy.intersection(flange_xy).area <= EPS:
            raise ValueError("Beam slots leave insufficient flange below the cap; reduce beam width or increase spacing")
    envelope = unary_union([footprint, flange_xy, anchor_xy, cap_xy, beam_xy])
    # Check the entire component too, including overhanging geometry.
    model_xy = unary_union([Polygon(t[:, :2]) for t in mesh.triangles if Polygon(t[:, :2]).area > EPS])
    envelope = envelope.union(model_xy)
    if not bed.buffer(EPS).covers(envelope):
        raise ValueError("Model or generated anchor extends beyond the printable bed")
    for region in excluded:
        if not region.is_valid or envelope.intersects(region):
            raise ValueError("Model/anchor intersects an excluded region or reserved wipe-tower area")
    flange = prism(flange_xy, 0, h)
    # Follow the original wall instead of occupying its outward slope.
    if intersection_volume(mesh, flange) > EPS:
        output = (solid(flange) - solid(mesh)).to_mesh64()
        flange = trimesh.Trimesh(vertices=output.vert_properties, faces=output.tri_verts, process=False)
        validate_mesh(flange)
        if any(abs(part.bounding_box()[2]) > EPS for part in solid(flange).decompose()):
            raise ValueError("An adapted flange island has no independent bed footprint")
    if settings.advanced_anchor:
        flange = native_precision(flange)
    wall = prism(anchor_xy.union(beam_xy), 0, h)
    cap = prism(cap_xy, h, top)
    joined = solid(wall) + solid(cap)
    output = joined.to_mesh64()
    anchor = trimesh.Trimesh(vertices=output.vert_properties, faces=output.tri_verts, process=False)
    if settings.advanced_anchor:
        anchor = native_precision(anchor)
    validate_mesh(anchor)
    if intersection_volume(mesh, flange) > EPS or intersection_volume(mesh, anchor) > EPS or intersection_volume(flange, anchor) > EPS:
        raise ValueError("Generated geometry intersects the model or another material")
    # Conservative clearance test covers every model section throughout the cap band.
    guarded_cap = prism(cap_xy.buffer(settings.clearance - EPS), h, top)
    if intersection_volume(mesh, guarded_cap) > EPS:
        raise ValueError("Upper clamp violates main-part clearance")
    if intersection_volume(prism(footprint, 0, h), anchor) > EPS:
        raise ValueError("Anchor occupies volume underneath the model")
    if abs(anchor.bounds[0, 2]) > EPS:
        raise ValueError("Floating anchor has no bed contact")
    # Each disconnected anchor component must independently reach the bed.
    if any(abs(part.bounding_box()[2]) > EPS for part in joined.decompose()):
        raise ValueError("An anchor island has no independent bed footprint")
    for obstacle in obstacles:
        validate_mesh(obstacle)
        if intersection_volume(flange, obstacle) > EPS or intersection_volume(anchor, obstacle) > EPS:
            raise ValueError("Anchor intersects another object/instance")
    warnings = ["Experimental geometry: adhesion, removal force and thermal creep require physical testing.",
                "Cap underside is deposited onto the main flange; verify its first capture layer in Preview.",
                "Toolhead swept-volume collisions are not evaluated; use native slicer collision checks."]
    if settings.flange_object_gap > 0:
        warnings.append("The flange-to-object gap separates the flange from the model and may reduce retention; test adhesion before relying on the clamp.")
    if settings.gap > settings.line_width:
        raise ValueError("Gap exceeds one line width; unsupported capture overhang")
    if h < 2 * boundaries[0]:
        warnings.append("Flange is thinner than two initial layers; retention may be weak.")
    return Assembly(mesh.copy(), flange, anchor, {
        "enabled": True, "source_sha256": fingerprint, "settings": settings.to_dict(),
        "requested_flange_height_mm": settings.flange_height, "effective_flange_height_mm": h,
        "effective_cap_thickness_mm": top - h, "anchor_height_mm": top,
        "outline_source": "model geometry from bed to clamp top",
        "beam_count": beam_count, "corner_beam_count": corner_count,
        "beam_slot_gap_mm": slot_gap if settings.advanced_anchor else None,
        "native_fit_tolerance_mm": fit_tolerance,
        "layer_boundaries_mm": list(boundaries), "warnings": warnings,
        "geometry_checks": "watertight; positive volume; no material intersections; bed and exclusions checked",
    })
