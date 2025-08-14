from __future__ import annotations

DOMAIN = "airzone_control"
DEFAULT_PORT = 3000
DEFAULT_HOST = "192.168.86.77"  # Albert's webserver IP

# User options
CONF_HOST = "host"
CONF_PORT = "port"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 10  # seconds

# Friendly labels for diagnostics / logs
MODE_LABELS: dict[int, str] = {
    0: "Stop",
    1: "Vent",
    2: "Heat",
    3: "Cool",
    4: "Auto",
    5: "Dry",
}

MODE_CODES: dict[str, int] = {v: k for k, v in MODE_LABELS.items()}
