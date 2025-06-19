import network
import time
import urequests
import gc
from machine import Pin, I2C, reset
import ssd1306
import math
import conf
import ugit

MAIN_VERSION = "1.2.4"

LANGS = {
    "ENG": {
        "SETTINGS": "SETTINGS",
        "LANG": "Language",
        "UNIT": "Unit",
        "REFRESH": "Refresh",
        "SLEEP_MODE": "Sleep Mode",
        "SLEEP_START": "Start",
        "SLEEP_END": "End",
        "UPDATE": "Update",
        "CONFIRM_UPDATE": "Check for update?",
        "YES": "Y=K1",
        "NO": "N=K2",
        "VERSION": "Ver",
        "BACK": "K4=Back",
        "PLUS": "K1+",
        "MINUS": "K2-",
        "NEXT": "K3->",
        "DISK_NONE": "No disks",
        "OCCUP": "Usage",
        "USED": "Used",
        "SIZE": "Size",
        "ALERT": "ALERT",
        "MENU": "Menu",
        "NETWORK_NO": "enp3s0 no data",
        "BRIGHTNESS": "Brightness",
        "UPDATING": "Updating...",
        "PROGRESS": "Progress"
    },
    "PL": {
        "SETTINGS": "USTAWIENIA",
        "LANG": "Jezyk",
        "UNIT": "Jednostka",
        "REFRESH": "Odswiezanie",
        "SLEEP_MODE": "Tryb Snu",
        "SLEEP_START": "Start",
        "SLEEP_END": "Koniec",
        "UPDATE": "Aktualizuj",
        "CONFIRM_UPDATE": "Wyszukac aktualizacje?",
        "YES": "T=K1",
        "NO": "N=K2",
        "VERSION": "Wersja",
        "BACK": "K4=Wstecz",
        "PLUS": "K1+",
        "MINUS": "K2-",
        "NEXT": "K3->",
        "DISK_NONE": "Brak dyskow",
        "OCCUP": "Zajecie",
        "USED": "Uzyte",
        "SIZE": "Rozmiar",
        "ALERT": "ALERT",
        "MENU": "Menu",
        "NETWORK_NO": "enp3s0 brak danych",
        "BRIGHTNESS": "Jasnosc",
        "UPDATING": "Aktualizacja...",
        "PROGRESS": "Postęp"
    }
}

# Kolejność i wygląd ustawień
settings = [
    {"label": "LANG", "key": "lang", "options": ["ENG", "PL"]},
    {"label": "UNIT", "key": "unit", "options": ["B", "KB", "MB", "GB"]},
    {"label": "REFRESH", "key": "refresh", "min": 1, "max": 60, "step": 1},
    {"label": "SLEEP_MODE", "header": True},  # Nagłówek
    {"label": "SLEEP_START", "key": "sleep_start", "min": 0, "max": 23, "step": 1},
    {"label": "SLEEP_END", "key": "sleep_end", "min": 0, "max": 23, "step": 1},
    {"label": "UPDATE", "update": True}
]

settings_state = conf.settings.copy()

settings_index = 0
in_settings = False
in_update_confirm = False
in_update_progress = False
screen_off = False
last_activity_time = time.ticks_ms()
SLEEP_DURATION = 15 * 1000
settings_scroll_offset = 0

SSID = conf.SSID
PASSWORD = conf.PASSWORD
REFRESH_INTERVAL = settings_state["refresh"]
CPU_URL = conf.CPU_URL
MEM_URL = conf.MEM_URL
SENSORS_URL = conf.SENSORS_URL
DISK_URL = conf.DISK_URL
NETWORK_URL = conf.NETWORK_URL
SYSTEM_URL = conf.SYSTEM_URL

i2c = I2C(0, scl=Pin(1), sda=Pin(0))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

button_k1 = Pin(2, Pin.IN, Pin.PULL_UP)
button_k2 = Pin(3, Pin.IN, Pin.PULL_UP)
button_k3 = Pin(4, Pin.IN, Pin.PULL_UP)
button_k4 = Pin(5, Pin.IN, Pin.PULL_UP)

brightness = 128
slider_visible = False
slider_show_time = 0
current_page = 0

filtered_disks = []
selected_disk_index = 0
server_name = "Server"

alert_active = False
alert_message = ""
alert_start_time = 0

def T(key):
    lang = settings_state.get("lang", "ENG")
    return LANGS[lang][key]

def ascii_polish(text):
    pol = "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
    asc = "acelnoszzACELNOSZZ"
    return ''.join(asc[pol.index(c)] if c in pol else c for c in text)

def save_settings():
    """Zapisuje aktualne ustawienia do pliku conf.json"""
    conf.save(settings_state)

def trigger_alert(msg):
    global alert_active, alert_message, alert_start_time
    alert_active = True
    alert_message = msg
    alert_start_time = time.ticks_ms()

# ... (pozostałe funkcje: fetch, display, sleep, obsługa przycisków - identyczne jak w Twoim kodzie, z wywołaniem save_settings() po każdej zmianie ustawień)

def display_settings_panel(now=0):
    """Wyświetla panel ustawień z nagłówkami i update na dole"""
    oled.fill(0)
    global settings, settings_index, settings_state, settings_scroll_offset
    oled.text(T("SETTINGS"), 16, 0, 1)
    oled.hline(0, 12, 128, 1)
    visible_lines = 3
    # Automatyczne przewijanie
    if settings_index < settings_scroll_offset:
        settings_scroll_offset = settings_index
    elif settings_index >= settings_scroll_offset + visible_lines:
        settings_scroll_offset = settings_index - visible_lines + 1
    visible_settings = settings[settings_scroll_offset:settings_scroll_offset+visible_lines]
    visible_idx = 0
    for i, s in enumerate(visible_settings):
        y = 20 + 12 * visible_idx
        idx = settings_scroll_offset + i
        if s.get("header"):
            oled.text(T(s["label"]), 0, y, 1)
        elif s.get("update"):
            prefix = ">" if idx == settings_index else " "
            oled.text(f"{prefix}{T('UPDATE')}", 0, y, 1)
            version_disp = scroll_version_text(MAIN_VERSION, y, idx==settings_index, time.ticks_ms())
            oled.text(f"{T('VERSION')}: {version_disp}", 64, y, 1)
        else:
            prefix = ">" if idx == settings_index else " "
            val = settings_state[s["key"]]
            oled.text(f"{prefix}{T(s['label'])}: {val}", 0, y, 1)
        visible_idx += 1
    oled.show()

def display_update_progress(progress=0):
    """Wyświetla loading bar aktualizacji OTA"""
    oled.fill(0)
    oled.text(T("UPDATING"), 0, 0, 1)
    oled.hline(0, 12, 128, 1)
    oled.text(f"{T('PROGRESS')}: {progress}%", 0, 32, 1)
    bar_width = int(progress * 1.28)
    oled.rect(0, 48, 128, 8, 1)
    oled.fill_rect(0, 48, bar_width, 8, 1)
    oled.show()

def do_update_with_progress():
    """Pokazuje progres i wywołuje ugit.update_main()"""
    for p in [10, 40, 70, 100]:
        display_update_progress(p)
        time.sleep(0.4)
    ugit.update_main()

# ... (reszta funkcji jak w Twoim kodzie)

def main():
    global settings_index, in_settings, in_update_confirm, in_update_progress, settings_scroll_offset
    # ... (inicjalizacja jak w Twoim kodzie)
    while True:
        now = time.ticks_ms()
        # ... (obsługa sleep, alertów itd.)
        if in_settings:
            num_options = len(settings)
            if in_update_progress:
                do_update_with_progress()
                in_update_progress = False
                in_settings = False
                continue
            if in_update_confirm:
                display_update_confirm()
                if time.ticks_diff(now, last_press_time) > debounce_delay:
                    if not button_k1.value():
                        in_update_confirm = False
                        in_update_progress = True
                        last_press_time = now
                    elif not button_k2.value():
                        in_update_confirm = False
                        last_press_time = now
                time.sleep(0.05)
                continue
            if time.ticks_diff(now, last_press_time) > debounce_delay:
                s = settings[settings_index]
                if s.get("header"):
                    if not button_k3.value():
                        settings_index = (settings_index + 1) % num_options
                        last_press_time = now
                elif s.get("update"):
                    if not button_k1.value() or not button_k2.value():
                        in_update_confirm = True
                        last_press_time = now
                    elif not button_k3.value():
                        settings_index = (settings_index + 1) % num_options
                        last_press_time = now
                else:
                    key = s["key"]
                    if not button_k1.value():
                        if "options" in s:
                            idx = s["options"].index(settings_state[key])
                            settings_state[key] = s["options"][(idx + 1) % len(s["options"])]
                        else:
                            settings_state[key] = min(s["max"], settings_state[key] + s["step"])
                        save_settings()
                        last_press_time = now
                    elif not button_k2.value():
                        if "options" in s:
                            idx = s["options"].index(settings_state[key])
                            settings_state[key] = s["options"][(idx - 1) % len(s["options"])]
                        else:
                            settings_state[key] = max(s["min"], settings_state[key] - s["step"])
                        save_settings()
                        last_press_time = now
                    elif not button_k3.value():
                        settings_index = (settings_index + 1) % num_options
                        last_press_time = now
                if not button_k4.value():
                    in_settings = False
                    settings_index = 0
                    settings_scroll_offset = 0
                    last_press_time = now
            display_settings_panel(now)
            time.sleep(0.05)
            continue
        # ... (reszta głównej pętli jak w Twoim kodzie)

if __name__ == "__main__":
    main()
