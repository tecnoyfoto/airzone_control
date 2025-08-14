# fake_airzone_stdlib.py
# Simulador mínimo de la Airzone Local API v1 usando SOLO librerías estándar.
# Endpoints: /api/v1/webserver, /api/v1/version, /api/v1/hvac (GET/POST/PUT)

from __future__ import annotations
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import json
import argparse
import re

CONFIG = {
    "mac": "AA:BB:CC:DD:EE:01",
    "name": "Airzone Mock 1",
    "zones": 3,
    "modes": [1, 2, 3, 4],  # modos de ejemplo
    "host": "0.0.0.0",
    "port": 3000,
}

def make_zone(zid: int, system_id: int, modes: list[int], base_name: str) -> dict:
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
        "modes": modes,      # p.ej. [1,2,3,4] o [4,3,7]
        "mode": modes[0],    # modo actual
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

def parse_modes(modes_str: str) -> list[int]:
    return [int(x) for x in re.split(r"[,\s]+", modes_str) if x]

class Handler(BaseHTTPRequestHandler):
    server_version = "FakeAirzone/1.0"

    def log_message(self, fmt, *args):
        # imprime menos ruido en consola
        print("[%s] %s" % (self.address_string(), fmt % args))

    def _send_json(self, obj: dict, code: int = 200):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _not_found(self):
        self._send_json({"error": "not found"}, 404)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/favicon.ico":
            return self._not_found()

        if path == "/api/v1/webserver":
            payload = {
                "mac": CONFIG["mac"],
                "name": CONFIG["name"],
                "ws_type": "ws_az",
                "ws_firmware": "3.44",
                "interface": "eth",
                "cloud_connected": "0",
            }
            return self._send_json(payload)

        if path == "/api/v1/version":
            return self._send_json({"schema": "1.77"})

        if path == "/api/v1/hvac":
            qs = parse_qs(parsed.query or "")
            systemid = int(qs.get("systemid", ["1"])[0])
            zoneid = int(qs.get("zoneid", ["0"])[0])

            if zoneid == 0:  # broadcast zonas
                data = [make_zone(z, 1, CONFIG["modes"], CONFIG["name"]) for z in range(1, CONFIG["zones"] + 1)]
                return self._send_json({"data": data})

            # zona concreta
            return self._send_json({"data": [make_zone(zoneid, systemid, CONFIG["modes"], CONFIG["name"])]})

        return self._not_found()

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b""
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/v1/webserver":
            # Aceptamos POST igual que GET (algunas implementaciones usan POST)
            return self.do_GET()

        if parsed.path == "/api/v1/hvac":
            body = self._read_json_body()
            systemid = int(body.get("systemID", 1))
            zoneid = int(body.get("zoneID", 0))

            if zoneid == 0:
                data = [make_zone(z, 1, CONFIG["modes"], CONFIG["name"]) for z in range(1, CONFIG["zones"] + 1)]
                return self._send_json({"data": data})

            return self._send_json({"data": [make_zone(zoneid, systemid, CONFIG["modes"], CONFIG["name"])]})

        if parsed.path == "/api/v1/version":
            return self._send_json({"schema": "1.77"})

        return self._not_found()

    def do_PUT(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/v1/hvac":
            return self._not_found()

        body = self._read_json_body()
        systemid = int(body.get("systemID", 1))
        zoneid = int(body.get("zoneID", 0))
        changed = {k: v for k, v in body.items() if k not in ("systemID", "zoneID")}
        return self._send_json({"data": {"systemID": systemid, "zoneID": zoneid, **changed}})

def main():
    parser = argparse.ArgumentParser(description="Fake Airzone Local API (stdlib only)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--mac", default=CONFIG["mac"])
    parser.add_argument("--name", default=CONFIG["name"])
    parser.add_argument("--zones", type=int, default=CONFIG["zones"])
    parser.add_argument("--modes", default="1,2,3,4", help="Lista de modos numéricos, p.ej. '4,3,7'")
    args = parser.parse_args()

    CONFIG.update({
        "host": args.host,
        "port": args.port,
        "mac": args.mac,
        "name": args.name,
        "zones": args.zones,
        "modes": parse_modes(args.modes),
    })

    httpd = HTTPServer((CONFIG["host"], CONFIG["port"]), Handler)
    print(f"Fake Airzone escuchando en http://{CONFIG['host']}:{CONFIG['port']}  "
          f"MAC={CONFIG['mac']}  Zonas={CONFIG['zones']}  Modes={CONFIG['modes']}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

if __name__ == "__main__":
    main()
