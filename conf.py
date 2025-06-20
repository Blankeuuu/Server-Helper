import ujson

DEFAULTS = {
    "SSID": "Wifi Name",
    "PASSWORD": "Wifi Password",
    "SERVER_URL": "http://(your server ip):61208",
    "lang": "ENG",
    "unit": "GB",
    "refresh": 5,
    "sleep_start": 22,
    "sleep_end": 6,
    "sleep_enabled": 0,
    "eco_mode": 0,
    "timezone": 0  # UTC+0
}



def load():
    try:
        with open("conf.json", "r") as f:
            data = ujson.load(f)
        for k in DEFAULTS:
            if k not in data:
                data[k] = DEFAULTS[k]
        return data
    except Exception:
        return DEFAULTS.copy()

def save(settings):
    try:
        with open("conf.json", "w") as f:
            ujson.dump(settings, f)
    except Exception as e:
        print("Błąd zapisu ustawień:", e)

settings = load()

# Stałe adresy API, generowane na podstawie SERVER_URL
SERVER_URL = settings["SERVER_URL"]
SSID = settings["SSID"]
PASSWORD = settings["PASSWORD"]
CPU_URL = SERVER_URL + '/api/4/cpu'
MEM_URL = SERVER_URL + '/api/4/mem'
SENSORS_URL = SERVER_URL + '/api/4/sensors'
DISK_URL = SERVER_URL + '/api/4/fs'
NETWORK_URL = SERVER_URL + '/api/4/network'
SYSTEM_URL = SERVER_URL + '/api/4/system'

