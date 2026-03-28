"""Constants for pyunifiapi."""

# Default controller settings
DEFAULT_CONTROLLER_PORT = 443
DEFAULT_SITE = 'default'
DEFAULT_SSH_USERNAME = 'ubnt'
DEFAULT_SSH_PASSWORD = 'ubnt'

# Ubiquiti cloud endpoints
CLOUD_SSO_URL = 'https://sso.ui.com/api/sso/v1'
CLOUD_ACCESS_URL = 'https://cloudaccess.svc.ui.com'
CLOUD_IOT_HOST = 'a1ewuiz2p7wdvw-ats.iot.us-west-2.amazonaws.com'
CLOUD_IOT_REGION = 'us-west-2'
# Legacy (deprecated, does not resolve)
CLOUD_WSS_URL = 'wss://device-airos.svc.ubnt.com/api/airos/v1/unifi/events'
CLOUD_DEVICE_URL = 'https://device-airos.svc.ubnt.com/api/airos/v1/unifi'

# SDP polling
SDP_POLL_MAX_RETRIES = 90
SDP_POLL_INTERVAL = 2.0

# WebRTC
WEBRTC_CHANNEL_OPEN_TIMEOUT = 30.0
ICE_GATHERING_TIMEOUT = 30.0

# SSH session
SSH_SESSION_TTL = -1  # No TTL (device-side timeout)
SSH_AUTO_CLOSE_TIMEOUT = 30.0

# Controller API paths
API_LOGIN = '/api/auth/login'
API_CMD_DEVMGR = '/api/s/{site}/cmd/devmgr'
API_CMD_SDN = '/api/s/{site}/cmd/sdn'
API_STAT_DEVICE = '/api/s/{site}/stat/device'
API_STAT_STA = '/api/s/{site}/stat/sta'
API_STAT_SYSINFO = '/api/s/{site}/stat/sysinfo'
API_STAT_HEALTH = '/api/s/{site}/stat/health'
API_STAT_EVENT = '/api/s/{site}/stat/event'
API_STAT_ALARM = '/api/s/{site}/stat/alarm'
API_STAT_SESSIONS = '/api/s/{site}/stat/session'
API_STAT_ALLUSER = '/api/s/{site}/stat/alluser'
API_STAT_GUEST = '/api/s/{site}/stat/guest'
API_STAT_DASHBOARD = '/api/s/{site}/stat/dashboard'
API_STAT_ROGUEAP = '/api/s/{site}/stat/rogueap'
API_LIST_WLANCONF = '/api/s/{site}/list/wlanconf'
API_LIST_NETWORKCONF = '/api/s/{site}/list/networkconf'
API_LIST_PORTCONF = '/api/s/{site}/list/portconf'
API_LIST_PORTFORWARD = '/api/s/{site}/list/portforward'
API_LIST_WLANGROUP = '/api/s/{site}/list/wlangroup'
API_REST_WLANCONF = '/api/s/{site}/rest/wlanconf'
API_REST_DEVICE = '/api/s/{site}/rest/device'
API_GET_SETTING = '/api/s/{site}/get/setting'
API_SELF_SITES = '/api/self/sites'
API_STAT_SITES = '/api/stat/sites'
API_CMD_STAMGR = '/api/s/{site}/cmd/stamgr'
