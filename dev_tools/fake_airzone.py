# fake_airzone.py
# Simulador mínimo de la Airzone Local API v1 para pruebas multi-instalación.
# Expone /api/v1/webserver y /api/v1/hvac (GET/POST/PUT) con datos coherentes.

from __future__ import annotations
import argparse, re
from flask import Flask, request, jsonify

app = Flask(__name__)

def make_zone(zid: int, system_id: int, modes: list[int], base_name: str):
    return {
        "systemID": system_id,
        "zoneID": zid,
        "name": f"{base_name} Z{zid:02d}",
        "on": 1,
        "double_sp": 0,
        "coolsetpoint": 26,
        "coolmaxtemp": 32,
        "coolmintemp": 15,
        "heatsetpoint": 22,
        "heatmaxtemp": 32,
        "heatmintemp": 15,
        "maxTemp": 32,
        "minTemp": 15,
        "setpoint": 24,
        "roomTemp": 23,
        "sleep": 0,
        "temp_step": 1,
        "modes": modes,     # p.ej. [1,2,3,4] o [4,3,7]
        "mode": modes[0],   # modo actual
        "speed_values": [0, 1, 2],
        "speeds": 2,
        "speed_type": 0,
        "speed": 1,
        "units": 0,
        "errors": [],
        "air_demand": 0,
        "cold_demand": 0,
        "heat_demand": 0,
        "open_window": 0,
    }

@app.route("/api/v1/webserver", methods=["GET", "POST"])
def webserver():
    # La doc oficial usa POST, pero aceptamos GET para comodidad. :contentReference[oaicite:1]{index=1}
    return jsonify({
        "mac": args.mac,
        "name": args.name,
        "ws_type": "ws_az",
        "ws_firmware": "3.44",
        "interface": "eth",
        "cloud_connected": "0"
    })

@app.route("/api/v1/version", methods=["GET", "POST"])
def version():
    return jsonify({"schema": "1.77"})

@app.route("/api/v1/hvac", methods=["GET", "POST", "PUT"])
def hvac():
    # Aceptamos GET (query systemid/zoneid) y POST (JSON systemID/zoneID), como en la doc. :contentReference[oaicite:2]{index=2}
    if request.method == "GET":
        systemid = int(request.args.get("systemid", "1"))
        zoneid = int(request.args.get("zoneid", "0"))
        payload = {}
    else:
        try:
            payload = request.get_json(force=True) or {}
        except Exception:
            payload = {}
        systemid = int(payload.get("systemID", 1))
        zoneid = int(payload.get("zoneID", 0))

    if request.method in ("GET", "POST"):
        # Broadcast o petición de zonas: devolvemos una lista de zonas
        if systemid in (0, 1) and zoneid == 0:
            data = [make_zone(z, 1, args.modes, args.name) for z in range(1, args.zones + 1)]
            return jsonify({"data": data})

        # Zona concreta
        if zoneid > 0:
            return jsonify({"data": [make_zone(zoneid, systemid, args.modes, args.name)]})

        # Solo sistema: respuesta mínima de ejemplo
        return jsonify({"data": {
            "systemID": systemid,
            "manufacturer": "Mock Manufacturer",
            "system_type": 2,
            "errors": [{}]
        }})

    # PUT: eco simulando eco de la API (devuelve lo que has cambiado). :contentReference[oaicite:3]{index=3}
    changed = {k: v for k, v in (payload or {}).items() if k not in ("systemID", "zoneID")}
    return jsonify({"data": {"systemID": systemid, "zoneID": zoneid, **changed}})

def parse_modes(modes_str: str) -> list[int]:
    return [int(x) for x in re.split(r"[,\s]+", modes_str) if x]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fake Airzone Local API server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--mac", default="AA:BB:CC:DD:EE:01")
    parser.add_argument("--name", default="Airzone Mock 1")
    parser.add_argument("--zones", type=int, default=3)
    parser.add_argument("--modes", default="1,2,3,4", help="Lista de modos numéricos, p.ej. '4,3,7'")
    args = parser.parse_args()
    args.modes = parse_modes(args.modes)
    app.run(host=args.host, port=args.port, debug=False)
