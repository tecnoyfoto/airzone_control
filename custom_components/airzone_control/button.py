from __future__ import annotations

import asyncio
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .coordinator import AirzoneCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add_entities):
    data = hass.data.get(DOMAIN, {})
    coord: AirzoneCoordinator | None = None
    if isinstance(data, dict):
        coord = data.get(entry.entry_id, {}).get("coordinator")
    if not isinstance(coord, AirzoneCoordinator):
        return

    entities: list[ButtonEntity] = []
    for sid in sorted({sid for (sid, _) in (coord.data or {}).keys()}):
        entities.append(SystemEcoButton(coord, sid, mode="auto"))
        entities.append(SystemEcoButton(coord, sid, mode="manual"))

    add_entities(entities)

class SystemEcoButton(CoordinatorEntity[AirzoneCoordinator], ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, mode: str) -> None:
        super().__init__(coordinator)
        self._sid = int(system_id)
        self._mode = mode  # "auto" | "manual"
        self._attr_name = f"Sistema {self._sid} - ECO {mode.capitalize()}"
        self._attr_unique_id = f"{DOMAIN}_button_eco_{mode}_{self._sid}"
        self._attr_icon = "mdi:leaf"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"system-{self._sid}")},
            name=f"Sistema {self._sid}",
            manufacturer="Airzone",
            model="HVAC System",
        )

    async def async_press(self) -> None:
        # La API expone 'eco_adapt' en el payload de zona (p.ej. "manual").
        # Aplicamos a todas las zonas del sistema vía PUT /hvac.
        tasks = []
        for (sid, zid), _ in (self.coordinator.data or {}).items():
            if sid == self._sid:
                tasks.append(self.coordinator.async_set_zone_params(self._sid, zid, eco_adapt=self._mode))
        if tasks:
            await asyncio.gather(*tasks)
