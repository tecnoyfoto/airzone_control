from __future__ import annotations
"""
Mapping between Airzone Local API numeric mode codes and Home Assistant HVACMode.

Rationale:
- Some Airzone firmwares expose `modes` and `mode` as numeric codes.
- We observed inconsistencies across prior versions of this integration, so we unify
  the mapping here and every platform must import this module.
- We also provide helpers to derive *allowed* hvac modes from a zone payload,
  clamping out COOL/HEAT if the zone clearly lacks that capability (e.g. a caldera
  only has heatsetpoint and no coolsetpoint).
"""
from homeassistant.components.climate.const import HVACMode

# Canonical translation used by official examples and 3rd party libs:
# 0=Stop/Off, 1=Vent (Fan only), 2=Heat, 3=Cool, 4=Auto, 5=Dry
API_TO_HVAC_MODE: dict[int, HVACMode] = {
    0: HVACMode.OFF,
    1: HVACMode.FAN_ONLY,
    2: HVACMode.HEAT,
    3: HVACMode.COOL,
    4: HVACMode.AUTO,
    5: HVACMode.DRY,
}

HVAC_TO_API_MODE: dict[HVACMode, int] = {
    HVACMode.OFF: 0,
    HVACMode.FAN_ONLY: 1,
    HVACMode.HEAT: 2,
    HVACMode.COOL: 3,
    HVACMode.AUTO: 4,
    HVACMode.DRY: 5,
}

def has_heat_capability(zone: dict) -> bool:
    return any(k in zone for k in ("heatsetpoint", "heatmaxtemp", "heatmintemp"))

def has_cool_capability(zone: dict) -> bool:
    return any(k in zone for k in ("coolsetpoint", "coolmaxtemp", "coolmintemp"))

def allowed_hvac_modes_for_zone(zone: dict) -> list[HVACMode]:
    """Return the hvac modes the zone *should* expose in HA.

    Priority:
    1) If the API provides an explicit `modes` list, translate it.
    2) Clamp by capabilities: drop COOL if no cool keys in payload; drop HEAT if no heat keys.
    3) Always include OFF.
    4) If nothing left (edge case), default to [OFF, HEAT] for water-based systems.
    """
    explicit = zone.get("modes")
    result: list[HVACMode] = []
    seen: set[HVACMode] = set()

    if isinstance(explicit, list) and explicit:
        for code in explicit:
            ha = API_TO_HVAC_MODE.get(code)
            if ha and ha not in seen:
                seen.add(ha)
                result.append(ha)

    # Clamp by capability hints
    heat_ok = has_heat_capability(zone)
    cool_ok = has_cool_capability(zone)
    if result:
        if not heat_ok and HVACMode.HEAT in result:
            result = [m for m in result if m != HVACMode.HEAT]
            seen.discard(HVACMode.HEAT)
        if not cool_ok and HVACMode.COOL in result:
            result = [m for m in result if m != HVACMode.COOL]
            seen.discard(HVACMode.COOL)

    # If no explicit list, infer
    if not result:
        if heat_ok and cool_ok:
            result = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL]
        elif heat_ok:
            result = [HVACMode.OFF, HVACMode.HEAT]
        elif cool_ok:
            result = [HVACMode.OFF, HVACMode.COOL]
        else:
            # Very bare payloads: be conservative (most common in caldera setups)
            result = [HVACMode.OFF, HVACMode.HEAT]

    if HVACMode.OFF not in result:
        result.insert(0, HVACMode.OFF)
    return result

def translate_current_mode(zone: dict, allowed: list[HVACMode]) -> HVACMode:
    """Translate `zone['mode']` to HVACMode, clamping to *allowed* list.

    If the zone is off (`on` == 0), return HVACMode.OFF regardless of `mode`.
    If the current code maps to a mode not in `allowed`, pick HEAT (if allowed)
    for heating-only systems; otherwise fall back to OFF.
    """
    try:
        if int(zone.get("on", 1)) == 0:
            return HVACMode.OFF
    except Exception:
        pass

    code = zone.get("mode")
    hvac = API_TO_HVAC_MODE.get(code, None)
    if hvac in allowed:
        return hvac
    # Clamp
    if HVACMode.HEAT in allowed and HVACMode.COOL not in allowed:
        return HVACMode.HEAT
    if HVACMode.COOL in allowed and HVACMode.HEAT not in allowed:
        return HVACMode.COOL
    return HVACMode.OFF
