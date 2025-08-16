from __future__ import annotations
"""
Traducción de códigos `mode` de la Local API de Airzone a HVACMode de Home Assistant
y cálculo de los *modos permitidos* por zona de forma 100% dinámica a partir de la API.

Tabla canónica (Local API):
    1: STOP/OFF  (algunos firmwares aceptan 0 como OFF)
    2: COOL
    3: HEAT
    4: FAN
    5: DRY
    7: AUTO
"""

from typing import Iterable, List, Set
from homeassistant.components.climate.const import HVACMode

# --- Mapeos canónicos ---
API_TO_HVAC_MODE: dict[int, HVACMode] = {
    0: HVACMode.OFF,
    1: HVACMode.OFF,
    2: HVACMode.COOL,
    3: HVACMode.HEAT,
    4: HVACMode.FAN_ONLY,
    5: HVACMode.DRY,
    7: HVACMode.AUTO,
}

# OFF se maneja con on=0, no se mapea aquí.
HVAC_TO_API_MODE: dict[HVACMode, int] = {
    HVACMode.COOL: 2,
    HVACMode.HEAT: 3,
    HVACMode.FAN_ONLY: 4,
    HVACMode.DRY: 5,
    HVACMode.AUTO: 7,
}

# ---------- utilidades internas ----------

def _translate_modes_list(codes: list) -> List[HVACMode]:
    """Convierte una lista de códigos numéricos en HVACMode, manteniendo orden
    y sin duplicados. OFF siempre se añade al principio.
    """
    out: List[HVACMode] = [HVACMode.OFF]
    for c in codes:
        try:
            hvac = API_TO_HVAC_MODE.get(int(c))
            if hvac and hvac not in out:
                out.append(hvac)
        except Exception:
            continue
    return out

def _has_any_heat_keys(z: dict) -> bool:
    return any(k in z for k in ("heatsetpoint", "heatmintemp", "heatmaxtemp", "heat_demand"))

def _has_any_cool_keys(z: dict) -> bool:
    return any(k in z for k in ("coolsetpoint", "coolmintemp", "coolmaxtemp", "cold_demand"))

# ---------- API pública para las plataformas ----------

def allowed_hvac_modes_for_zone(zone: dict) -> List[HVACMode]:
    """Lista de modos HVAC permitidos para la *zona* de forma estrictamente dinámica.

    Prioridad de fuentes (todas provienen de la API):
      1) `modes` de ZONA  -> se usan tal cual (traducidos).
      2) `sys_modes`      -> inyectados por el coordinator a partir del payload de SISTEMA.
      3) Fallback conservador sin inventar modos:
         - OFF siempre.
         - Si hay `mode` actual → añadimos solo ese (si no es OFF).
         - En ausencia de lo anterior:
             * Si la zona expone únicamente CLAVES de calor -> HEAT.
             * Si la zona expone únicamente CLAVES de frío -> COOL.
         - No añadimos AUTO ni FAN si la API no los enumera en `modes`.
    """
    # 1) La propia zona nos dice sus modos
    zm = zone.get("modes")
    if isinstance(zm, list) and zm:
        return _translate_modes_list(zm)

    # 2) El sistema nos dice los modos y el coordinator los inyecta
    sm = zone.get("sys_modes")
    if isinstance(sm, list) and sm:
        return _translate_modes_list(sm)

    # 3) Fallback ultra-conservador
    allowed: List[HVACMode] = [HVACMode.OFF]

    # Si hay un `mode` numérico actual y es válido, añadimos solo ese
    try:
        current = zone.get("mode", None)
        if current is not None:
            hvac = API_TO_HVAC_MODE.get(int(current))
            if hvac and hvac is not HVACMode.OFF and hvac not in allowed:
                allowed.append(hvac)
            return allowed
    except Exception:
        pass

    # Si no sabemos el `mode`, miramos qué claves existen. Pero evitamos añadir
    # calor y frío a la vez si el equipo expone setpoints "de cortesía".
    has_heat = _has_any_heat_keys(zone)
    has_cool = _has_any_cool_keys(zone)

    if has_heat and not has_cool and HVACMode.HEAT not in allowed:
        allowed.append(HVACMode.HEAT)
    elif has_cool and not has_heat and HVACMode.COOL not in allowed:
        allowed.append(HVACMode.COOL)
    # Si hay ambos, no añadimos nada: sin `modes` de API preferimos no asumir.
    # (El usuario seguirá pudiendo ver el modo actual si arriba lo devolvió `mode`.)

    return allowed


def translate_current_mode(zone: dict, allowed: Iterable[HVACMode]) -> HVACMode:
    """Traduce zone['mode'] al HVACMode dentro de *allowed* con reglas seguras:
       - on==0 → OFF
       - si el código actual es válido y está en allowed → ese
       - si solo hay una capacidad (heat/cool) en allowed → ese
       - si hay demanda fría/caliente y el modo está permitido → priorizar demanda
       - si nada cuadra → OFF
    """
    allowed_set: Set[HVACMode] = set(allowed)

    # OFF si la zona reporta on:0
    try:
        if int(zone.get("on", 1)) == 0:
            return HVACMode.OFF
    except Exception:
        pass

    # Mapear el código numérico si es válido y permitido
    try:
        code = zone.get("mode", None)
        if code is not None:
            hvac = API_TO_HVAC_MODE.get(int(code), None)
            if hvac in allowed_set:
                return hvac
    except Exception:
        pass

    # Clamp por capacidad única
    if HVACMode.HEAT in allowed_set and HVACMode.COOL not in allowed_set:
        return HVACMode.HEAT
    if HVACMode.COOL in allowed_set and HVACMode.HEAT not in allowed_set:
        return HVACMode.COOL

    # Demandas
    try:
        if int(zone.get("heat_demand", 0)) and HVACMode.HEAT in allowed_set:
            return HVACMode.HEAT
        if int(zone.get("cold_demand", 0)) and HVACMode.COOL in allowed_set:
            return HVACMode.COOL
    except Exception:
        pass

    return HVACMode.OFF
