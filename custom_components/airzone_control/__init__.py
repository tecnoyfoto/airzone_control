from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CLOUD_CATEGORY_CLIMATE_ZONES,
    CONNECTION_TYPE_CLOUD,
    CONNECTION_TYPE_LOCAL,
    CONF_CLOUD_EXCLUDE_IAQ_NAMES,
    CONF_CLOUD_INCLUDE_BOUND_IAQS,
    CONF_CLOUD_INCLUDE_CATEGORIES,
    CONF_CLOUD_INCLUDE_DEVICE_IDS,
    CONF_CLOUD_PROFILE,
    CONF_CONNECTION_TYPE,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USER_ID,
    DEFAULT_CLOUD_EXCLUDE_IAQ_NAMES,
    DEFAULT_CLOUD_INCLUDE_BOUND_IAQS,
    DEFAULT_CLOUD_INCLUDE_CATEGORIES,
    DEFAULT_CLOUD_INCLUDE_DEVICE_IDS,
    DEFAULT_CLOUD_PROFILE,
    DEFAULT_CLOUD_SCAN_INTERVAL,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    CLOUD_PROFILE_COMPLEMENT_LOCAL,
    CLOUD_PROFILE_CUSTOM,
)
from .coordinator import AirzoneCoordinator
from .coordinator_cloud import AirzoneCloudCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.BUTTON,
]


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recargar la integración cuando cambian options/data."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Cargar integración Airzone Control desde una config entry."""
    connection_type = entry.data.get(CONF_CONNECTION_TYPE, CONNECTION_TYPE_LOCAL)
    if connection_type == CONNECTION_TYPE_CLOUD:
        scan = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_CLOUD_SCAN_INTERVAL),
        )
        cloud_profile = entry.options.get(
            CONF_CLOUD_PROFILE,
            entry.data.get(CONF_CLOUD_PROFILE, DEFAULT_CLOUD_PROFILE),
        )
        include_categories = entry.options.get(
            CONF_CLOUD_INCLUDE_CATEGORIES,
            entry.data.get(CONF_CLOUD_INCLUDE_CATEGORIES, DEFAULT_CLOUD_INCLUDE_CATEGORIES),
        )
        include_device_ids = entry.options.get(
            CONF_CLOUD_INCLUDE_DEVICE_IDS,
            entry.data.get(CONF_CLOUD_INCLUDE_DEVICE_IDS, DEFAULT_CLOUD_INCLUDE_DEVICE_IDS),
        )
        require_device_selection = (
            cloud_profile in {CLOUD_PROFILE_COMPLEMENT_LOCAL, CLOUD_PROFILE_CUSTOM}
            and (
                CONF_CLOUD_INCLUDE_DEVICE_IDS in entry.options
                or CONF_CLOUD_INCLUDE_DEVICE_IDS in entry.data
            )
        )
        include_bound_iaqs = entry.options.get(CONF_CLOUD_INCLUDE_BOUND_IAQS)
        if include_bound_iaqs is None:
            include_bound_iaqs = (
                DEFAULT_CLOUD_INCLUDE_BOUND_IAQS
                if CLOUD_CATEGORY_CLIMATE_ZONES in include_categories
                else False
            )

        coordinator = AirzoneCloudCoordinator(
            hass,
            email=entry.data.get(CONF_EMAIL, ""),
            password=entry.data.get(CONF_PASSWORD, ""),
            scan_interval=scan,
            user_id=entry.data.get(CONF_USER_ID),
            include_categories=include_categories,
            include_bound_iaqs=include_bound_iaqs,
            include_device_ids=include_device_ids,
            require_device_selection=require_device_selection,
            exclude_iaq_names=entry.options.get(
                CONF_CLOUD_EXCLUDE_IAQ_NAMES,
                entry.data.get(CONF_CLOUD_EXCLUDE_IAQ_NAMES, DEFAULT_CLOUD_EXCLUDE_IAQ_NAMES),
            ),
        )
        coordinator.cloud_profile = cloud_profile
    else:
        scan = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        host = entry.data.get("host", DEFAULT_HOST)
        port = entry.data.get(CONF_PORT, DEFAULT_PORT)
        api_prefix = entry.data.get("api_prefix")
        coordinator = AirzoneCoordinator(
            hass,
            host=host,
            port=port,
            scan_interval=scan,
            api_prefix=api_prefix,
        )

    coordinator.config_entry = entry  # type: ignore[attr-defined]

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "connection_type": connection_type,
    }

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Descargar una config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    bundle = hass.data.get(DOMAIN, {}).pop(entry.entry_id, {})
    coord: AirzoneCoordinator | None = bundle.get("coordinator")
    if coord:
        await coord.async_close()

    return unload_ok
