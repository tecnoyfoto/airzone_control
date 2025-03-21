**Airzone Control Integration**

[🇪🇸 Lee este documento en español](README.es.md)

This integration allows controlling and monitoring Airzone HVAC systems through their local API (default port 3000). Unlike the official integration, this version is specifically designed to:

- Support systems with multiple zones.
- Expose an expanded set of sensors (e.g., temperature, humidity, battery, firmware, IAQ, and diagnostics).
- Group entities by device in Home Assistant.
- Provide manual control of the master thermostat mode through a selector.
-----
**Features**

- **Automatic Zone Detection:** The integration automatically detects available zones via the local API.
- **Individual Zone Control (climate):** Each zone creates a climate entity allowing:
  - Turning the zone on or off.
  - Changing mode (based on the API response).
  - Adjusting temperature setpoints.
  - Viewing current room temperature.
- **Zone Sensors (sensor):** Sensors created for each zone include:
  - Temperature (based on roomTemp).
  - Humidity (if reported by firmware).
  - Battery status ("Ok" or "Low", detecting Error 8 or low levels).
  - Thermostat firmware version (value from thermos\_firmware).
  - Demand data (heat, cold, and ventilation) if reported by API.
  - Dual setpoints if applicable (coolsetpoint and heatsetpoint).
  - Global IAQ sensor (CO₂, PM2.5, PM10, TVOC, pressure, index, and score, based on available information).
- **Global System Control:** Entities are grouped into an “Airzone System” device including:
  - A sensor displaying the global mode.
  - A sensor indicating fan speed.
  - A sensor showing the "sleep mode" status.
  - Optional sensors for system ID, firmware, errors, and units (Celsius/Fahrenheit).
  - An aggregated sensor summarizing zones with low battery (showing zone names, e.g., "Kitchen, Study", or "None" if all are okay).
- **Manual Master Mode Control:** Includes a selector to manually force the master thermostat mode (e.g., "Stop" or "Heat"). Upon startup, it reads the current mode from the API and synchronizes, allowing users to override automatic behavior when necessary.
-----
**Prerequisites**

- Airzone device with local API enabled (typically accessible at http://:3000).
- Airzone Webserver must be in the same local network as Home Assistant.
- Verify manually (using curl or browser) that accessing http://:3000/api/v1/hvac?systemid=1&zoneid=1 returns the expected JSON response.
-----
**Installation**

1. Download the repository files (or clone) into your config/custom\_components/airzone\_control folder. The structure should look like:

custom\_components

└── airzone\_control

`    `├── \_\_init\_\_.py

`    `├── manifest.json

`    `├── config\_flow.py

`    `├── const.py

`    `├── coordinator.py

`    `├── climate.py

`    `├── sensor.py

`    `├── switch.py

`    `├── select.py

`    `└── translations

`        `├── es.json

`        `└── ca.json

2. Restart Home Assistant to detect the new integration.
2. Configure the integration:
   1. Go to **Settings → Devices & Services → + Add Integration**.
   1. Search for “Airzone Control” in the list.
   1. Enter the IP of the Airzone Webserver and the port (default is 3000), then press **Submit**.
   1. After a few seconds, the integration will install and begin displaying entities.
-----
**Created Entities**

- **Climate:** A climate entity is created for each detected zone, allowing individual control.
- **Sensors:** Sensors include:
  - Temperature, humidity, battery, and firmware per zone.
  - Demand data (heat, cold, air) and dual setpoints if applicable.
  - Global IAQ sensors (CO₂, PM2.5, PM10, TVOC, pressure, index, score, and ventilation mode).
  - Global system data (mode, fan speed, sleep mode, ID, firmware, errors, and units).
  - Aggregated sensor summarizing zones with low battery.
- **Switches:** Switches are included for:
  - Turning the entire system on or off.
  - Activating or deactivating ECO mode.
- **Selector:** A "select" entity for manually forcing the master thermostat mode (options: "Stop" and "Heat"), automatically synchronized with the current state after restart.
-----
**Devices in Home Assistant**

- Each zone appears as a separate device (e.g., “Airzone Zone Study”) with respective climate and sensor entities.
- The global system (Airzone System) groups system-wide data entities, including battery status and manual mode selector.
- Global IAQ sensor is displayed as an additional device (“Airzone IAQ Sensor”).
-----
**Usage**

- **On/Off:** Use the Home Assistant climate card to turn zones on or off.
- **Adjust Temperature:** Set the desired temperature directly through the climate interface.
- **Manual Mode Control:** Use "Airzone Manual Mode" selector to manually set the master thermostat mode ("Stop" or "Heat").
- **Battery Monitoring:** Check the “Zones amb Bateria Baixa” sensor for quick reference of zones needing battery attention.
-----
**Frequently Asked Questions**

- **What if only certain zones report some data (e.g., humidity)?** This is normal if certain wireless thermostats do not report values or report intermittently due to low batteries or communication issues.
- **What does “Error 8” in the API mean?** Generally, this indicates the Lite thermostat isn't properly communicating with the central controller, often due to low batteries or wireless connection issues.
-----
**Limitations**

- Tested with firmware versions 3.6x and 3.7x on Airzone Webserver.
- IAQ data availability depends on hardware and firmware support.
- Certain diagnostic or firmware update functionalities might not be available depending on device or API capabilities.
-----
**Contributions**

Contributions and suggestions to improve this integration are welcome. You can submit PRs or issues via GitHub.

-----
**License**

This work is licensed under a [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-nc-sa/4.0/).

