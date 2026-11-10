"""Screen user-supplied thermal data without claiming validated material pairs."""
import math


def screen_material(anchor_name, bed_temperature=None, softening_temperature=None, nozzle_range=None, nozzle_temperature=None, chamber_temperature=None):
    values = [bed_temperature, softening_temperature, nozzle_temperature, chamber_temperature]
    if any(v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)) for v in values):
        raise ValueError("Thermal data must be finite temperatures in °C")
    messages = []
    environment = [v for v in (bed_temperature, chamber_temperature) if v is not None]
    if softening_temperature is not None and environment and max(environment) >= softening_temperature:
        messages.append({"level": "estimated risk", "message": "Bed/chamber reaches the supplied anchor softening temperature; creep may defeat retention."})
    elif "PLA" in anchor_name.upper() and environment and max(environment) >= 50:
        messages.append({"level": "estimated risk", "message": "PLA may soften near this bed/chamber temperature; verify the exact filament's thermal data."})
    if softening_temperature is None or bed_temperature is None:
        messages.append({"level": "unknown", "message": "Insufficient thermal data to establish anchor stiffness or bed adhesion."})
    if nozzle_range is not None:
        if len(nozzle_range) != 2 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in nozzle_range) or nozzle_range[0] > nozzle_range[1]:
            raise ValueError("Nozzle range must contain ordered finite °C limits")
        if nozzle_temperature is not None and not nozzle_range[0] <= nozzle_temperature <= nozzle_range[1]:
            messages.append({"level": "known incompatibility", "message": "Configured nozzle temperature is outside the supplied filament processing range."})
    messages.append({"level": "unknown", "message": "Material pair has no OpenAnchor physical validation; check purge, nozzle and chamber compatibility."})
    return messages
