"""Validated millimetre geometry settings and explicit layer plans."""
from dataclasses import dataclass, asdict
import math

FLANGE_WALL_LOOPS = 100

@dataclass(frozen=True)
class Settings:
    flange_width: float = 5.0
    flange_height: float = 0.8
    flange_object_gap: float = 0.1
    anchor_width: float = 10.0
    gap: float = 0.0
    overlap: float = 2.0
    cap_thickness: float = 0.4
    clearance: float = 0.2
    line_width: float = 0.4
    main_slot: int = 1
    anchor_slot: int = 2
    enabled: bool = True
    advanced_anchor: bool = False
    beam_width: float = 0.8
    beam_spacing: float = 10.0
    beam_model_gap: float = 0.6

    def validate(self, slots):
        limits = {"flange_width": (0.4, 50), "flange_height": (0.05, 10),
                  "anchor_width": (0.4, 50), "gap": (0, 2), "flange_object_gap": (0, 2), "overlap": (0.1, 20),
                  "cap_thickness": (0.05, 5), "clearance": (0.05, 10),
                  "line_width": (0.1, 2), "beam_width": (0.2, 5),
                  "beam_spacing": (2, 100), "beam_model_gap": (0.05, 10)}
        for key, (low, high) in limits.items():
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{key}: expected {low}–{high} mm")
        if type(self.enabled) is not bool:
            raise ValueError("enabled must be a boolean")
        if type(self.advanced_anchor) is not bool:
            raise ValueError("advanced_anchor must be a boolean")
        if self.advanced_anchor:
            if self.beam_width + 1e-9 < 2 * self.line_width:
                raise ValueError("Beam width needs at least two design line widths")
            if self.beam_spacing + 1e-9 < self.beam_width + 2 * self.gap + self.line_width:
                raise ValueError("Increase beam spacing to leave printable flange between slots")
            if self.beam_model_gap + 1e-9 < self.flange_object_gap + self.gap + self.line_width:
                raise ValueError("Increase beam-to-model clearance to leave a printable flange strip beyond the slots")
        if type(slots) is not int or slots < 2:
            raise ValueError("At least two configured filament slots are required")
        if any(type(v) is not int or not 1 <= v <= slots for v in (self.main_slot, self.anchor_slot)):
            raise ValueError("Filament slots must be loaded, 1-based slot numbers")
        if self.main_slot == self.anchor_slot:
            raise ValueError("Main and anchor filament slots must differ")
        if self.overlap > self.flange_width - self.clearance:
            raise ValueError("Overlap leaves less than the required model clearance")
        if self.flange_object_gap + self.overlap + self.clearance > self.flange_width:
            raise ValueError("Reduce the flange-to-object gap or overlap, or increase flange width to retain clamp support")
        if self.anchor_width < 2 * self.line_width or self.overlap < self.line_width:
            raise ValueError("Anchor needs two line widths; overlap needs at least one")

    def to_dict(self):
        return asdict(self)


def layer_boundaries(initial, regular, height):
    """Explicit constant-height fallback, never substitutes for an actual schedule."""
    if any(not math.isfinite(v) or v <= 0 for v in (initial, regular, height)):
        raise ValueError("Layer heights and total height must be positive and finite")
    if min(initial, regular) < 0.01 or height / regular > 100000:
        raise ValueError("Layer plan exceeds supported resolution or layer count")
    count = max(0, math.ceil((height - initial) / regular))
    return [round(initial + i * regular, 9) for i in range(count + 1)]


def align_heights(settings, boundaries):
    if not boundaries or len(boundaries) > 100000:
        raise ValueError("A nonempty layer schedule is required")
    if any(isinstance(z, bool) or not isinstance(z, (int, float)) or not math.isfinite(z) or z <= 0 for z in boundaries):
        raise ValueError("Layer boundaries must be positive finite millimetres")
    if any(a >= b for a, b in zip(boundaries, boundaries[1:])):
        raise ValueError("Layer boundaries must be strictly increasing")
    # Ties select the higher boundary; a cap must occupy at least one full layer.
    h = min(boundaries, key=lambda z: (abs(z - settings.flange_height), -z))
    above = [z for z in boundaries if z > h + 1e-8]
    if not above or h + settings.cap_thickness > boundaries[-1] + 1e-8:
        raise ValueError("Layer schedule must extend beyond flange plus cap")
    top = min(above, key=lambda z: (abs(z - h - settings.cap_thickness), -z))
    return h, top
