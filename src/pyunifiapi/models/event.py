"""Event model and event key enumeration."""

from __future__ import annotations

from enum import StrEnum
from typing import final

from pyunifiapi.models.api import ApiItem


class EventKey(StrEnum):
    """Known event types emitted by the UniFi controller."""

    # Controller
    CONTROLLER_UPDATE_AVAILABLE = 'EVT_GW_UpdateAvailable'

    # Access point events
    AP_ADOPTED = 'EVT_AP_Adopted'
    AP_AUTO_READOPTED = 'EVT_AP_AutoReadopted'
    AP_CHANNEL_CHANGED = 'EVT_AP_ChannelChanged'
    AP_CONNECTED = 'EVT_AP_Connected'
    AP_DELETED = 'EVT_AP_Deleted'
    AP_DETECT_ROGUE_AP = 'EVT_AP_DetectRogueAP'
    AP_DISCOVERED_PENDING = 'EVT_AP_DiscoveredPending'
    AP_FIRMWARE_UPDATED = 'EVT_AP_Upgraded'
    AP_ISOLATED = 'EVT_AP_Isolated'
    AP_LOST_CONTACT = 'EVT_AP_Lost_Contact'
    AP_POSSIBLE_INTERFERENCE = 'EVT_AP_PossibleInterference'
    AP_RADAR_DETECTED = 'EVT_AP_RadarDetected'
    AP_RESTARTED = 'EVT_AP_Restarted'
    AP_RESTARTED_UNKNOWN = 'EVT_AP_RestartedUnknown'
    AP_UPGRADE_FAILED = 'EVT_AP_UpgradeFailed'
    AP_UPGRADE_SCHEDULED = 'EVT_AP_UpgradeScheduled'

    # Dream Machine / UDM events
    DM_CONNECTED = 'EVT_DM_Connected'
    DM_LOST_CONTACT = 'EVT_DM_Lost_Contact'
    DM_RESTARTED = 'EVT_DM_Restarted'
    DM_UPGRADED = 'EVT_DM_Upgraded'

    # Gateway events
    GW_ADOPTED = 'EVT_GW_Adopted'
    GW_CONNECTED = 'EVT_GW_Connected'
    GW_DELETED = 'EVT_GW_Deleted'
    GW_FIRMWARE_UPDATED = 'EVT_GW_Upgraded'
    GW_LOST_CONTACT = 'EVT_GW_Lost_Contact'
    GW_RESTARTED = 'EVT_GW_Restarted'
    GW_RESTARTED_UNKNOWN = 'EVT_GW_RestartedUnknown'
    GW_WAN_TRANSITION = 'EVT_GW_WANTransition'

    # Switch events
    SW_ADOPTED = 'EVT_SW_Adopted'
    SW_CONNECTED = 'EVT_SW_Connected'
    SW_DELETED = 'EVT_SW_Deleted'
    SW_FIRMWARE_UPDATED = 'EVT_SW_Upgraded'
    SW_LOST_CONTACT = 'EVT_SW_Lost_Contact'
    SW_POE_OVERLOAD = 'EVT_SW_PoeOverload'
    SW_POE_DISCONNECT = 'EVT_SW_PoeDisconnect'
    SW_RESTARTED = 'EVT_SW_Restarted'
    SW_RESTARTED_UNKNOWN = 'EVT_SW_RestartedUnknown'
    SW_STP_PORT_BLOCKING = 'EVT_SW_StpPortBlocking'
    SW_UPGRADE_SCHEDULED = 'EVT_SW_UpgradeScheduled'

    # Wired client events
    WIRED_CLIENT_BLOCKED = 'EVT_LC_Blocked'
    WIRED_CLIENT_CONNECTED = 'EVT_LU_Connected'
    WIRED_CLIENT_DISCONNECTED = 'EVT_LU_Disconnected'
    WIRED_CLIENT_UNBLOCKED = 'EVT_LC_Unblocked'

    # Wireless client events
    WIRELESS_CLIENT_BLOCKED = 'EVT_WC_Blocked'
    WIRELESS_CLIENT_CONNECTED = 'EVT_WU_Connected'
    WIRELESS_CLIENT_DISCONNECTED = 'EVT_WU_Disconnected'
    WIRELESS_CLIENT_ROAM = 'EVT_WU_Roam'
    WIRELESS_CLIENT_ROAM_RADIO = 'EVT_WU_RoamRadio'
    WIRELESS_CLIENT_UNBLOCKED = 'EVT_WC_Unblocked'

    # Guest events
    WIRELESS_GUEST_CONNECTED = 'EVT_WG_Connected'
    WIRELESS_GUEST_DISCONNECTED = 'EVT_WG_Disconnected'
    WIRELESS_GUEST_ROAM = 'EVT_WG_Roam'
    WIRELESS_GUEST_AUTHORIZED = 'EVT_WG_Authorization'

    # Admin events
    ADMIN_LOGIN = 'EVT_AD_Login'
    ADMIN_LOGOUT = 'EVT_AD_Logout'

    # IPS/IDS events
    IPS_ALERT = 'EVT_IPS_IpsAlert'

    # VPN events
    VPN_CLIENT_CONNECTED = 'EVT_VPN_ClientConnected'
    VPN_CLIENT_DISCONNECTED = 'EVT_VPN_ClientDisconnected'


@final
class Event(ApiItem):
    """A controller event from the WebSocket events stream."""

    @property
    def id(self) -> str:
        return self.raw.get('_id', '')

    @property
    def key(self) -> str:
        return self.raw.get('key', '')

    @property
    def event_key(self) -> EventKey | None:
        """Parsed EventKey, or None if the key is unrecognized."""
        try:
            return EventKey(self.key)
        except ValueError:
            return None

    @property
    def msg(self) -> str:
        return self.raw.get('msg', '')

    @property
    def datetime(self) -> str:
        return self.raw.get('datetime', '')

    @property
    def time(self) -> int:
        return self.raw.get('time', 0)

    @property
    def site_id(self) -> str:
        return self.raw.get('site_id', '')

    @property
    def subsystem(self) -> str:
        return self.raw.get('subsystem', '')

    @property
    def mac(self) -> str:
        """MAC of the device or client this event relates to."""
        return self.raw.get('user', self.raw.get('client', self.raw.get('ap', self.raw.get('sw', self.raw.get('gw', '')))))

    @property
    def ap(self) -> str:
        return self.raw.get('ap', '')

    @property
    def client(self) -> str:
        return self.raw.get('client', '')

    @property
    def device(self) -> str:
        return self.raw.get('sw', self.raw.get('gw', self.raw.get('ap', '')))

    @property
    def hostname(self) -> str:
        return self.raw.get('hostname', '')

    @property
    def ssid(self) -> str:
        return self.raw.get('ssid', '')

    @property
    def channel(self) -> int:
        return self.raw.get('channel', 0)

    @property
    def radio(self) -> str:
        return self.raw.get('radio', '')

    @property
    def duration(self) -> int:
        return self.raw.get('duration', 0)

    @property
    def bytes_sent(self) -> int:
        return self.raw.get('bytes', 0)

    @property
    def version_from(self) -> str:
        return self.raw.get('version_from', '')

    @property
    def version_to(self) -> str:
        return self.raw.get('version_to', '')

    @property
    def network(self) -> str:
        return self.raw.get('network', '')

    @property
    def is_guest(self) -> bool:
        return self.raw.get('guest', '') == 'true' or self.raw.get('is_guest', False)
