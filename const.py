from homeassistant.const import CONF_HOST, CONF_PORT

DOMAIN = "airzone_control"
DEFAULT_PORT = 3000

# Mapeo numérico de la API -> Etiquetas de modo global
MODE_GLOBAL_MAP = {
    0: "Stop",
    1: "Vent",   # Ejemplo
    2: "Heat",
    3: "Cool"
}
