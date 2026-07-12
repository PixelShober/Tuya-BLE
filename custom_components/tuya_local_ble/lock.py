"""The Tuya BLE integration."""
from __future__ import annotations

from dataclasses import dataclass, field

import logging
from typing import Any, Callable
from datetime import datetime, timedelta
from threading import Timer
import time

from homeassistant.components.lock import (
    LockEntityDescription,
    LockEntity,
    LockEntityFeature,
    LockState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from homeassistant.const import (
    STATE_UNKNOWN,
)

from .const import DOMAIN
from .devices import TuyaBLEData, TuyaBLEEntity, TuyaBLEProductInfo
from .lock_protocol import build_accessory_lock_payload
from .tuya_ble import TuyaBLEDataPointType, TuyaBLEDevice
from .tuya_ble.exceptions import TuyaBLEDeviceError

_LOGGER = logging.getLogger(__name__)

TuyaBLELockIsAvailable = Callable[["TuyaBLELock", TuyaBLEProductInfo], bool] | None
TuyaBLELockCommandBuilder = Callable[[TuyaBLEDevice, bool], bytes]


def _build_gj635_command(device: TuyaBLEDevice, unlock: bool) -> bytes:
    """Build a GJ-635 DP 71 command without replaying a captured packet."""
    try:
        return build_accessory_lock_payload(device.ble_unlock_check, unlock=unlock)
    except ValueError as exc:
        raise TuyaBLEDeviceError(1) from exc

@dataclass
class TuyaBLELockMapping:
    dp_id: int
    dp_id_lock: int
    dp_id_unlock: int
    dp_id_nop: int
    keep_connect_timer: int
    description: LockEntityDescription = field(
        default_factory=lambda: LockEntityDescription(
            key="push",
            translation_key="push",
        )
    )
    force_add: bool = True
    keep_connect: bool = False
    dp_type: TuyaBLEDataPointType | None = None
    is_available: TuyaBLELockIsAvailable = None
    command_builder: TuyaBLELockCommandBuilder | None = None
    # Key safes only open (release the latch); they cannot be locked remotely
    # and re-latch mechanically. Present them as open-only.
    open_only: bool = False

@dataclass
class TuyaBLECategoryLockMapping:
    products: dict[str, list[TuyaBLELockMapping]] | None = None
    mapping: list[TuyaBLELockMapping] | None = None


mapping: dict[str, TuyaBLECategoryLockMapping] = {
    "jtmspro": TuyaBLECategoryLockMapping(
        products={
            "rlyxv7pe":  # Gimdow Smart Lock
            [
                TuyaBLELockMapping(
                    dp_id_unlock=6,
                    dp_id_lock=46,
                    dp_id=47,
                    # refer to sdk, dp 52 is for deleting temp password
                    # should be safe as a dummy keep alive message
                    dp_id_nop=52,
                    keep_connect=True,
                    keep_connect_timer=60,
                    description=LockEntityDescription(
                        key="manual_lock"
                    ),
                ),
            ],
            "hc7n0urm":  # Raykube A1 Ultra / A1 Pro Max TuyaOS FD50 lock
            [
                TuyaBLELockMapping(
                    dp_id_unlock=6,
                    dp_id_lock=46,
                    # V4 events are parsed, but the full state model is still unknown.
                    # The entity reflects successful remote unlock after V4 ACK.
                    dp_id=118,
                    dp_id_nop=52,
                    keep_connect=False,
                    keep_connect_timer=60,
                    description=LockEntityDescription(
                        key="manual_lock"
                    ),
                ),
            ],
            # GJ-635APP+KEY (laxpwq3g) is a key safe: it only opens and has no
            # closed/latched state to report, so it is a button (button.py),
            # not a lock entity.
        }
    ), 
}


def get_mapping_by_device(device: TuyaBLEDevice) -> list[TuyaBLECategoryLockMapping]:
    category = mapping.get(device.category)
    if category is not None and category.products is not None:
        product_mapping = category.products.get(device.product_id)
        if product_mapping is not None:
            return product_mapping
        if category.mapping is not None:
            return category.mapping
        else:
            return []
    else:
        return []


class TuyaBLELock(TuyaBLEEntity, LockEntity):
    """Representation of a Tuya BLE Lock."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator,
        device: TuyaBLEDevice,
        product: TuyaBLEProductInfo,
        mapping: TuyaBLELockMapping,
    ) -> None:
        super().__init__(hass, coordinator, device, product, mapping.description)
        self._mapping = mapping
        self._current_state = STATE_UNKNOWN
        if mapping.open_only:
            # Offer an Open action; rest state is latched so the card shows
            # Unlock/Open instead of a meaningless Lock action.
            self._attr_supported_features = LockEntityFeature.OPEN
            self._current_state = LockState.LOCKED
        self._target_state = None
        self._commanded = False
        self._commanded_timer = None
        self._datapoint_nop = None
        self._isjammed = False
        self._update_attrs()
        if mapping.keep_connect:
            self._thread = Timer(self._mapping.keep_connect_timer, self.send_nop_request)
            self._thread.start()
            self._datapoint_nop = device.datapoints.get_or_create(
                self._mapping.dp_id_nop,
                TuyaBLEDataPointType.DT_BOOL,
                False,
            )

    def send_nop_request(self):
        while True:
            if self._datapoint_nop:
                self._hass.create_task(self._datapoint_nop.set_value(True))
            time.sleep(self._mapping.keep_connect_timer)

    @property
    def is_locked(self) -> bool | None:
        """Return true if device is locked."""
        if self._current_state == STATE_UNKNOWN:
            return None
        return self._current_state == LockState.LOCKED

    @property
    def is_locking(self) -> bool:
        """Return true if device is locking."""
        return (
            self._current_state == LockState.UNLOCKED
            and self._target_state == LockState.LOCKED
            and self._commanded
        )

    @property
    def is_unlocking(self) -> bool:
        """Return true if device is unlocking."""
        return (
            self._current_state == LockState.LOCKED
            and self._target_state == LockState.UNLOCKED
            and self._commanded
        )

    @property
    def is_jammed(self) -> bool | None:
        """Return true if device is jammed."""
        return self._isjammed

    # Alarm properties
    @property
    def should_poll(self) -> bool: return False

    def _update_attrs(self) -> None:
        is_locked = self.is_locked
        self._attr_is_locking = self.is_locking
        self._attr_is_unlocking = self.is_unlocking
        self._attr_is_locked = is_locked
        self._attr_is_unlocked = None if is_locked is None else not is_locked
        self._attr_is_jammed = self.is_jammed
        self._attr_changed_by = super().changed_by

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        if self._mapping.open_only:
            # A key safe cannot be latched remotely; it re-latches mechanically
            # when closed. Ignore the lock command instead of sending a bogus one.
            _LOGGER.debug(
                "%s: lock command ignored (open-only key safe)",
                self._device.address,
            )
            return
        await self._set_lock_state(LockState.LOCKED)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        await self._set_lock_state(LockState.UNLOCKED)

    async def async_open(self, **kwargs: Any) -> None:
        """Open (release) the device — same command path as unlock."""
        await self._set_lock_state(LockState.UNLOCKED)

    async def _set_lock_state(self, state: str) -> None:
        self._target_state = state
        self._update_attrs()
        self.async_write_ha_state()

        if self._target_state == LockState.UNLOCKED:
            dp_id = self._mapping.dp_id_unlock
        else:
            dp_id = self._mapping.dp_id_lock

        if self._mapping.command_builder is not None:
            payload = self._mapping.command_builder(
                self._device,
                self._target_state == LockState.UNLOCKED,
            )
            datapoint = self._device.datapoints.get_or_create(
                dp_id,
                TuyaBLEDataPointType.DT_RAW,
                b"",
            )
            await datapoint.set_value(payload)
            self._current_state = self._target_state
            self._commanded = False
            self._isjammed = False
            self._update_attrs()
            self.async_write_ha_state()
            return

        datapoint = self._device.datapoints.get_or_create(
            dp_id,
            TuyaBLEDataPointType.DT_BOOL,
            False,
        )

        if self._device.product_id == "hc7n0urm" and self._target_state == LockState.UNLOCKED:
            await datapoint.set_value(True)
            self._current_state = LockState.UNLOCKED
            self._commanded = False
            self._isjammed = False
            self._update_attrs()
            self.async_write_ha_state()
            return

        if self._device.product_id == "hc7n0urm" and self._target_state == LockState.LOCKED:
            await datapoint.set_value(True)
            self._current_state = LockState.LOCKED
            self._commanded = False
            self._isjammed = False
            self._update_attrs()
            self.async_write_ha_state()
            return

        #Gimdow need true to activate lock/unlock commands
        self._hass.create_task(datapoint.set_value(True))
        self._commanded = True
        self._commanded_timer = datetime.now()


    def update_device_state(self):
        datapoint = self._device.datapoints[self._mapping.dp_id]
        if self._mapping.command_builder is not None:
            if datapoint and datapoint.changed_by_device:
                # DP 19 reports a completed BLE unlock event. The lock does not
                # expose a persistent bolt state in the confirmed data model.
                self._current_state = LockState.UNLOCKED
                self._commanded = False
                self._isjammed = False
            return
        if datapoint:
            if datapoint.value:
                self._current_state = LockState.UNLOCKED
            else:
                self._current_state = LockState.LOCKED
            if self._commanded:
                if ( self._current_state != self._target_state):
                    if ( datetime.now() > self._commanded_timer + timedelta(seconds = 12) ):
                        self._isjammed = True
                        self._commanded = False
                else:
                    self._commanded = False
                    self._isjammed = False

    @callback
    def _handle_coordinator_update(self) -> None:
        self.update_device_state()
        self._update_attrs()
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if self._mapping.command_builder is not None:
            return bool(self._device.ble_unlock_check)
        if self._device.product_id == "hc7n0urm":
            # Battery locks sleep and may not keep an active BLE connection between
            # commands. Allow Home Assistant to call unlock; the command path will
            # establish a connection on demand.
            return True
        result = super().available
        if result and self._mapping.is_available:
            result = self._mapping.is_available(self, self._product)
        return result


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tuya BLE sensors."""
    data: TuyaBLEData = hass.data[DOMAIN][entry.entry_id]
    mappings = get_mapping_by_device(data.device)
    entities: list[TuyaBLELock] = []
    for mapping in mappings:
        if mapping.force_add or data.device.datapoints.has_id(
            mapping.dp_id, mapping.dp_type
        ):
            entities.append(
                TuyaBLELock(
                    hass,
                    data.coordinator,
                    data.device,
                    data.product,
                    mapping,
                )
            )
    async_add_entities(entities)
