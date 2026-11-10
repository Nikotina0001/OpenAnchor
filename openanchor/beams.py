"""Contour-normal bed-to-cap ribs, with explicit corner bisectors."""
import math

from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import nearest_points, unary_union


def beam_footprint(outline, wall, cap, settings, *, fit_tolerance=1e-4):
    """Return the planar ribs and accepted placement/corner counts."""
    guard = outline.buffer(settings.beam_model_gap + 2 * fit_tolerance, join_style="mitre")
    outer = outline.buffer(settings.flange_width + settings.gap + settings.anchor_width, join_style="mitre")
    # Placement simplification removes tessellation noise; clearance uses the exact outline.
    contours = outline.simplify(min(settings.line_width / 4, settings.beam_width / 8), preserve_topology=True)
    contours = [contours] if isinstance(contours, Polygon) else list(contours.geoms)
    reach = math.hypot(outline.bounds[2] - outline.bounds[0], outline.bounds[3] - outline.bounds[1])
    reach += 10 * (settings.flange_width + settings.gap + settings.anchor_width)
    ribs = []
    count = corners = 0
    for polygon in contours:
        ring = orient(polygon, sign=1).exterior
        coords = list(ring.coords)[:-1]
        corner_samples = []
        distance = 0.0
        for index, point in enumerate(coords):
            previous, following = coords[index - 1], coords[(index + 1) % len(coords)]
            incoming = (point[0] - previous[0], point[1] - previous[1])
            outgoing = (following[0] - point[0], following[1] - point[1])
            left, right = math.hypot(*incoming), math.hypot(*outgoing)
            if left > 1e-8 and right > 1e-8:
                dot = (incoming[0] * outgoing[0] + incoming[1] * outgoing[1]) / (left * right)
                if dot < math.cos(math.pi / 4):
                    tangent = (incoming[0] / left + outgoing[0] / right,
                               incoming[1] / left + outgoing[1] / right)
                    corner_samples.append((distance, point, tangent, True))
            distance += right
        sample_count = max(1, math.ceil(ring.length / settings.beam_spacing))
        if sample_count + len(corner_samples) + count > 512:
            raise ValueError("Too many support beams; increase beam spacing or simplify the model")
        samples = list(corner_samples)
        for index in range(sample_count):
            distance = index * ring.length / sample_count
            if any(min(abs(distance - d), ring.length - abs(distance - d)) <
                   max(settings.beam_width * 2, settings.beam_spacing / 4) for d, *_ in corner_samples):
                continue
            delta = min(settings.line_width / 4, ring.length / 100)
            before = ring.interpolate((distance - delta) % ring.length)
            after = ring.interpolate((distance + delta) % ring.length)
            point = ring.interpolate(distance)
            samples.append((distance, (point.x, point.y), (after.x - before.x, after.y - before.y), False))
        for _, point, tangent, corner in samples:
            length = math.hypot(*tangent)
            if length <= 1e-8:
                continue
            normal = (tangent[1] / length, -tangent[0] / length)
            ray = LineString([point, (point[0] + normal[0] * reach, point[1] + normal[1] * reach)])
            clear = ray.difference(guard)
            segments = [clear] if isinstance(clear, LineString) else list(clear.geoms)
            segments = [segment for segment in segments if isinstance(segment, LineString) and segment.length > 1e-8]
            if not segments:
                continue
            # Never bypass another model branch to reach a distant anchor wall.
            local = min(segments, key=lambda segment: Point(point).distance(segment))
            hit = local.intersection(wall)
            if hit.is_empty:
                continue
            wall_distance = Point(point).distance(nearest_points(Point(point), hit)[1])
            start_distance, stop_distance = sorted(ray.project(Point(coord)) for coord in (local.coords[0], local.coords[-1]))
            start = ray.interpolate(start_distance)
            end = ray.interpolate(min(wall_distance + settings.beam_width, stop_distance))
            rib = LineString([start, end]).buffer(settings.beam_width / 2, cap_style="flat")
            rib = rib.difference(guard).intersection(outer)
            pieces = [rib] if isinstance(rib, Polygon) else list(rib.geoms)
            attached = [piece for piece in pieces if piece.area > 1e-6 and
                        piece.intersection(wall).area > 1e-6 and piece.intersection(cap).area > 1e-6]
            if attached:
                ribs.extend(attached)
                count += 1
                corners += int(corner)
    if not ribs:
        raise ValueError("No supported beam layout fits this contour; adjust dimensions or use the normal anchor")
    return unary_union(ribs), count, corners
