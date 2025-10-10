from __future__ import annotations

from typing import List, Optional

# -------------------------------------------------------------------
# Detecta idioma del sistema de HA i normalitza a 'es', 'en' o 'ca'
# -------------------------------------------------------------------

def _lang(hass) -> str:
    try:
        lang = (getattr(hass.config, "language", None) or "").lower()
    except Exception:
        lang = ""
    if lang.startswith("ca"):
        return "ca"
    if lang.startswith("en"):
        return "en"
    # per defecte castellà
    return "es"


# -------------------------------------------------------------------
# Etiquetes bàsiques
# -------------------------------------------------------------------

def label(hass, key: str) -> str:
    L = _lang(hass)
    base = {
        "es": {
            "on": "Encendido",
            "off": "Apagado",
            "auto": "Automático",
            "yes": "Sí",
            "no": "No",
            "unknown": "Desconocido",
            "low": "Baja",
            "medium": "Media",
            "high": "Alta",
            "very_low": "Muy baja",
            "very_high": "Muy alta",
            "manual": "Manual",
        },
        "en": {
            "on": "On",
            "off": "Off",
            "auto": "Auto",
            "yes": "Yes",
            "no": "No",
            "unknown": "Unknown",
            "low": "Low",
            "medium": "Medium",
            "high": "High",
            "very_low": "Very low",
            "very_high": "Very high",
            "manual": "Manual",
        },
        "ca": {
            "on": "Encès",
            "off": "Apagat",
            "auto": "Automàtic",
            "yes": "Sí",
            "no": "No",
            "unknown": "Desconegut",
            "low": "Baixa",
            "medium": "Mitjana",
            "high": "Alta",
            "very_low": "Molt baixa",
            "very_high": "Molt alta",
            "manual": "Manual",
        },
    }
    return base.get(L, base["es"]).get(key, key)


# -------------------------------------------------------------------
# Noms de modes Airzone per codi (2,3,4,5,7)
# 2=cool, 3=heat, 4=fan/ventilació, 5=dry, 7=stop (gestionat com "off")
# -------------------------------------------------------------------

def mode_name(hass, code: Optional[int]) -> Optional[str]:
    if code is None:
        return None
    L = _lang(hass)
    names = {
        "es": {
            2: "Frío",
            3: "Calor",
            4: "Ventilación",
            5: "Deshumidificación",
            7: "Apagado",
        },
        "en": {
            2: "Cool",
            3: "Heat",
            4: "Ventilation",
            5: "Dry",
            7: "Off",
        },
        "ca": {
            2: "Refrigeració",
            3: "Calefacció",
            4: "Ventilació",
            5: "Deshumidificació",
            7: "Apagat",
        },
    }
    return names.get(L, names["es"]).get(int(code))


# -------------------------------------------------------------------
# Etiquetes de velocitat (Auto, 1..N).
# Si només hi ha 3 nivells → Baixa/Mitjana/Alta
# Amb 4 nivells → Baixa/Mitjana/Alta/Molt alta
# Sinó → "Nivell X" (CA), "Nivel X" (ES), "Level X" (EN)
# -------------------------------------------------------------------

def speed_label(hass, value: int, max_level: Optional[int], values: List[int]) -> str:
    L = _lang(hass)
    if value == 0:
        return label(hass, "auto")

    # Identifica nombre de nivells reals (excloent l'Auto)
    lvls = sorted([v for v in values if v != 0])
    count = len(lvls) if lvls else (max_level or 0)

    # map curt per 3-4 nivells
    if count in (3, 4):
        idx = value  # 1..N
        maps = {
            "es": {1: "Baja", 2: "Media", 3: "Alta", 4: "Muy alta"},
            "en": {1: "Low", 2: "Medium", 3: "High", 4: "Very high"},
            "ca": {1: "Baixa", 2: "Mitjana", 3: "Alta", 4: "Molt alta"},
        }
        name = maps.get(L, maps["es"]).get(idx)
        if name:
            return name

    # fallback genèric
    if L == "ca":
        return f"Nivell {value}"
    if L == "en":
        return f"Level {value}"
    return f"Nivel {value}"


# -------------------------------------------------------------------
# IAQ: mode de ventilació (0 off, 1 manual, 2 auto)
# -------------------------------------------------------------------

def iaq_vent_label(hass, code: int) -> str:
    if int(code) == 0:
        return label(hass, "off")
    if int(code) == 1:
        return label(hass, "manual")
    return label(hass, "auto")
