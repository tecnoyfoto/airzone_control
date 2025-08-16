from __future__ import annotations

DOMAIN = "airzone_control"
DEFAULT_PORT = 3000
# No default host: cada usuario debe introducir la IP real del controlador Airzone.
DEFAULT_HOST = ""

# User options
CONF_HOST = "host"
CONF_PORT = "port"
CONF_SCAN_INTERVAL = "scan_interval"

# Intervalo de sondeo por defecto (segundos). Cambiable en Opciones.
DEFAULT_SCAN_INTERVAL = 5

# Códigos numéricos de la Local API -> etiquetas
# 0/1=Stop, 2=Cooling, 3=Heating, 4=Fan, 5=Dry, 7=Auto
MODE_LABELS: dict[int, str] = {
    0: "Stop",
    1: "Stop",
    2: "Cooling",
    3: "Heating",
    4: "Fan",
    5: "Dry",
    7: "Auto",
}

MODE_CODES: dict[str, int] = {v: k for k, v in MODE_LABELS.items()}
