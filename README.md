[Leer en español](README.es.md)

# Airzone Control for Home Assistant

Airzone Control is an **unofficial** Home Assistant custom integration for Airzone installations.

It supports two connection modes:

- **Local API**: the recommended path for day-to-day HVAC control through an Airzone Webserver or Aidoo device on your LAN.
- **Cloud API**: optional **read-only** support for devices that are only available through Airzone Cloud, such as cloud energy meters and Wi-Fi IAQ sensors.

The integration is designed for installations with multiple zones, IAQ sensors, and, when needed, several Airzone devices in the same Home Assistant instance.

## Current Status

Version `1.9.0` improves reliability, configuration and entity availability for both Local API and Cloud API:

- Cloud entities are read-only.
- Cloud write actions are disabled.
- Local API can be discovered automatically through Zeroconf or configured manually by IP.
- Cloud entries can request credential renewal from Home Assistant.
- TLS verification is enabled by default and can be adjusted for compatible local devices.
- Integration driver registration is optional and disabled by default.
- Each entity's availability reflects the state of the source providing its data.
- The default Cloud polling interval is `30` seconds.

Recommended mixed setup:

- Use **Local API** for thermostats and locally attached IAQ sensors.
- Add a **Cloud API** entry only for cloud-only devices.
- Use the Cloud profile **Complement Local API** and select the exact Cloud devices to expose.

## Highlights

- Local zone thermostats.
- Master thermostat per system.
- Optional group thermostats.
- Dynamic sensors, selects, switches and buttons depending on what your hardware exposes.
- IAQ sensors: CO2, TVOC, PM2.5, PM10, pressure, score/index and text quality where available.
- Webserver diagnostics: firmware, Wi-Fi quality, RSSI, channel and connectivity where available.
- Cloud energy meters.
- Cloud Wi-Fi IAQ sensors.
- Multiple config entries, so Local API and Cloud API can coexist without unique ID collisions.
- Support diagnostics with transport and source-status information.

## Requirements

For Local API:

- Airzone Webserver, Airzone Hub, Aidoo Pro or Aidoo Pro Fancoil exposing Local API v1.
- Home Assistant must be able to reach the device IP.
- Default Local API port: `3000`.

For Cloud API:

- An Airzone Cloud account.
- Cloud devices visible in that account.
- Internet access from Home Assistant to Airzone Cloud.

Important: controllers such as Flexa 3 by themselves may not expose the Local REST API. You usually need a Webserver/Aidoo device for Local API access.

## Installation

### HACS

1. Open **HACS -> Integrations**.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add `https://github.com/tecnoyfoto/airzone_control` as an **Integration**.
4. Install **Airzone Control**.
5. Restart Home Assistant.

### Manual

Copy the integration folder into your Home Assistant configuration:

```text
config/
  custom_components/
    airzone_control/
      __init__.py
      manifest.json
      config_flow.py
      const.py
      coordinator.py
      coordinator_cloud.py
      climate.py
      sensor.py
      binary_sensor.py
      select.py
      switch.py
      button.py
      translations/
```

Then restart Home Assistant.

## Configuration

Add the integration from:

**Settings -> Devices & services -> Add integration -> Airzone Control**

You will be asked to choose a connection type.

### Local API

Use this for the main HVAC installation.

Fields:

- **Host**: IP address of the Airzone Webserver/Aidoo device.
- **Port**: usually `3000`.

The integration tries to detect the correct API prefix automatically. If detection fails, it lets you choose a prefix manually.

Devices announced on the network may appear automatically in Home Assistant through Zeroconf. For HTTPS connections, keep TLS verification enabled whenever the device certificate allows it.

Quick checks:

```text
http://<IP>:3000/api/v1/webserver
http://<IP>:3000/api/v1/version
```

### Cloud API

Use this when you need devices that are not available through the Local API.

Fields:

- Airzone Cloud email.
- Airzone Cloud password.
- Cloud profile.
- Categories/devices to expose.

Cloud profiles:

- **Use all Cloud API devices**: exposes all supported Cloud categories.
- **Complement Local API**: intended for Local + Cloud mixed installations. It enables energy and IAQ categories and lets you choose exact Cloud devices.
- **Custom**: lets you choose categories and devices manually.

For a Local + Cloud installation, choose **Complement Local API** and select only the Cloud energy meter or Wi-Fi IAQ sensors you actually want. Complementary and custom profiles require at least one selected device before saving.

If Airzone Cloud rejects credentials that previously worked, Home Assistant can renew them through the reauthentication flow without creating a new entry.

## Options

Open:

**Settings -> Devices & services -> Airzone Control -> Configure**

Common options:

- Polling interval.
- Logical zone groups.
- Cloud profile and Cloud category/device filters for Cloud entries.
- TLS verification for Local API entries.
- Optional integration driver registration on compatible devices.

The minimum interval is `5` seconds for Local API and `15` seconds for Cloud API. Cloud API keeps a default value of `30` seconds.

Saving options reloads the integration automatically.

## Group Thermostats

Groups let you create one thermostat entity that controls several Local API zones.

Easy UI:

- Set a group name.
- Select the zones.
- Save options.

Advanced JSON example:

```json
[
  {
    "id": "day_area",
    "name": "Day area",
    "zones": ["1/3", "1/4", "1/5"]
  },
  {
    "id": "night_area",
    "name": "Night area",
    "zones": ["1/1", "1/2"]
  }
]
```

## Entities

Local API can expose:

- Zone climate entities.
- Master system climate entities.
- Group climate entities.
- Zone temperature, setpoint, mode, fan speed, sleep and slat controls where available.
- System sensors and switches.
- Webserver sensors.
- IAQ sensors and ventilation entities.
- Hotel-style buttons to turn all zones on/off where supported.

Cloud API can expose:

- Read-only climate zones when enabled.
- Cloud IAQ sensors.
- Cloud energy meter sensors.
- Cloud ACS/auxiliary data where supported by the integration.

## Diagnostics

Files generated for support omit configuration data and identifiers that are not needed to analyze integration behavior. They include technical source and transport status to help troubleshoot issues.

Internal identifiers may still be used inside Home Assistant to keep entities and filters stable, but they are not included in the support file when they are not needed for analysis.

## Known Limitations

- Cloud API support is read-only in this release.
- Cloud write support is intentionally disabled until it is validated safely.
- Cloud polling should stay conservative. The public default is `30` seconds.
- The meaning and period of some energy counters may vary by Airzone model or firmware.
- Not every Airzone device exposes the same Local API fields; entities are created dynamically when fields exist.

## Troubleshooting

- **Local API does not connect**: use the Webserver/Aidoo IP, not the controller IP. Check port `3000`, firewall/VLAN rules and the `/webserver` endpoint.
- **Device is not discovered**: add it manually by IP. mDNS discovery may be blocked by the network.
- **Missing entities**: the connected device may not expose those fields.
- **Duplicate thermostats after adding Cloud**: use the Cloud profile **Complement Local API** and disable/select Cloud devices carefully.
- **Cloud IAQ or energy becomes unavailable**: increase the Cloud polling interval and check Airzone Cloud availability.

## Compatibility

Known useful Local API targets:

- Airzone Webserver / Hub / 5G / Wi-Fi webserver.
- Aidoo Pro.
- Aidoo Pro Fancoil.

Known Cloud device families currently handled:

- `az_zone`, `aidoo`, `aidoo_it`
- `az_airqsensor`
- `az_energy_clamp`
- `az_acs`, `aidoo_acs`
- `az_vmc`, `az_relay`, `az_dehumidifier`

## Translations

Included languages:

- English
- Spanish
- Catalan
- French
- German
- Italian
- Portuguese
- Basque
- Galician
- Dutch

Some new Cloud strings may fall back to English in secondary languages until native translations are reviewed.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)
