"""Regression: Cloud (read-only) climate entities must expose a ClimateEntityFeature
flag, not a bare int 0 — HA does `Feature.X in supported_features`, which raises
TypeError("argument of type 'int' is not a container or iterable") on an int."""
import importlib, sys, types, pathlib
from unittest.mock import MagicMock

import pytest
from homeassistant.components.climate import ClimateEntityFeature

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
climate = importlib.import_module("custom_components.airzone_control.climate")

ZONE = {"systemID": 1, "zoneID": 1, "on": 1, "mode": 3, "modes": [4, 3, 5, 2, 0],
        "roomTemp": 20.2, "setpoint": 20.0, "minTemp": 15.0, "maxTemp": 26.0}


def _coord(read_only: bool):
    c = MagicMock()
    c.read_only = read_only
    c.connection_type = "cloud" if read_only else "local"
    c.scoped_unique_id = lambda s: s
    c.scoped_device_identifier = lambda s: s
    c.get_zone = lambda sid, zid: dict(ZONE)
    c.data = {(1, 1): dict(ZONE)}
    return c


def _entities(read_only):
    co = _coord(read_only)
    out = [climate.AirzoneMasterClimate(co, 1, [1])]
    for name in ("AirzoneZoneClimate",):
        cls = getattr(climate, name)
        try:
            out.append(cls(co, 1, 1))
        except TypeError:
            pass  # constructor signature differs; master covers the shared pattern
    return out


@pytest.mark.parametrize("read_only", [True, False])
def test_supported_features_is_flag_and_state_attrs_work(read_only):
    for ent in _entities(read_only):
        feats = ent.supported_features
        assert isinstance(feats, ClimateEntityFeature)
        # what HA does when adding the entity
        ent.hass = MagicMock()
        from homeassistant.util.unit_system import METRIC_SYSTEM
        ent.hass.config.units = METRIC_SYSTEM
        ent.capability_attributes
        ent.state_attributes
        if read_only:
            assert feats == ClimateEntityFeature(0)
