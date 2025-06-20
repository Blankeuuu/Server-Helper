import network
import time
import urequests
import gc
import ntptime
from machine import Pin, I2C, reset
import ssd1306
import math
import conf
import ugit

MAIN_VERSION = "1.2.8"

LANGS = {
    "ENG": {
        "SETTINGS": "SETTINGS",
        "LANG": "Language",
        "UNIT": "Unit",
        "REFRESH": "Refresh",
        "SLEEP_MODE": "Sleep Mode",
        "SLEEP_ENABLED": "On/Off",
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
        "PROGRESS": "Progress",
        "TIMEZONE": "Timezone",
        "ECO_MODE": "Eco Mode",
        "RESET_DEFAULTS": "Reset Defaults",
        "RESET_CONFIRM": "Reset all settings?",
        "RESET_DONE": "Defaults loaded!"
    },
    "PL": {
        "SETTINGS": "USTAWIENIA",
        "LANG": "Jezyk",
        "UNIT": "Jednostka",
        "REFRESH": "Odswiezanie",
        "SLEEP_MODE": "Tryb Snu",
        "SLEEP_ENABLED": "wł/wył",
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
        "PROGRESS": "Postęp",
        "TIMEZONE": "Strefa czasowa",
        "ECO_MODE": "Tryb Eco",
        "RESET_DEFAULTS": "Przywróć domyślne",
        "RESET_CONFIRM": "Przywrócić ustawienia?",
        "RESET_DONE": "Domyślne ustawienia!"
    }
}

settings = [
    {"label": "VERSION", "header": True},
    {"label": "UPDATE", "update": True},
    {"label": "LANG", "key": "lang", "options": ["ENG", "PL"]},
    {"label": "UNIT", "key": "unit", "options": ["B", "KB", "MB", "GB"]},
    {"label": "REFRESH", "key": "refresh", "min": 1, "max": 60, "step": 1},
    {"label": "ECO_MODE", "key": "eco_mode", "options": [0, 1]},
    {"label": "SLEEP_MODE", "header": True},
    {"label": "SLEEP_ENABLED", "key": "sleep_enabled", "options": [0, 1]},
    {"label": "SLEEP_START", "key": "sleep_start", "min": 0, "max": 23, "step": 1},
    {"label": "SLEEP_END", "key": "sleep_end", "min": 0, "max": 23, "step": 1},
    {"label": "TIMEZONE", "key": "timezone", "min": -12, "max": 14, "step": 1},
    {"label": "RESET_DEFAULTS", "reset": True}
]

settings_state = conf.settings.copy()

settings_index = 0
in_settings = False
in_update_confirm = False
in_update_progress = False
in_reset_confirm = False
screen_off = False
last_activity_time = time.ticks_ms()
SLEEP_DURATION = 15 * 1000
ECO_TIMEOUT = 120 * 1000  # 2 min
settings_scroll_offset = 0
sleep_wake_ignore = False

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
eco_brightness = 30
slider_visible = False
slider_show_time = 0
current_page = 0

filtered_disks = []
selected_disk_index = 0
server_name = "Server"

alert_active = False
alert_message = ""
alert_start_time = 0

wifi_reconnect_time = 0
wifi_last_status = False
wifi = None

def T(key):
    lang = settings_state.get("lang", "ENG")
    return LANGS[lang][key]

def ascii_polish(text):
    pol = "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
    asc = "acelnoszzACELNOSZZ"
    return ''.join(asc[pol.index(c)] if c in pol else c for c in text)

def save_settings():
    conf.save(settings_state)

def reset_settings():
    global settings_state
    settings_state = conf.DEFAULTS.copy()
    save_settings()

def trigger_alert(msg):
    global alert_active, alert_message, alert_start_time
    alert_active = True
    alert_message = msg
    alert_start_time = time.ticks_ms()

def show_alert(msg, now):
    oled.fill(0)
    oled.rect(0, 0, 128, 64, 1)
    alert_text = T("ALERT")
    x_alert = (128 - len(alert_text)*8)//2
    for dy in [0,1]:
        oled.text(alert_text, x_alert, 6+dy, 1)
    max_chars = 21
    max_lines_on_screen = 3
    lines = []
    m = ascii_polish(msg)
    while len(m) > 0:
        lines.append(m[:max_chars])
        m = m[max_chars:]
    if len(lines) <= max_lines_on_screen:
        visible_lines = lines
    else:
        scroll_period = 2000
        first_line = (now // scroll_period) % (len(lines) - max_lines_on_screen + 1)
        visible_lines = lines[first_line:first_line+max_lines_on_screen]
    for idx, l in enumerate(visible_lines):
        y = 28 + idx*12
        x = (128 - len(l)*6)//2 if len(l) < max_chars else 1
        oled.text(l, x, y, 1)
    oled.show()

def check_alert_clear():
    global alert_active
    if (not button_k1.value() or not button_k2.value() or
        not button_k3.value() or not button_k4.value()):
        alert_active = False

def set_brightness(value):
    global brightness
    brightness = max(0, min(255, value))
    oled.contrast(brightness)

def connect_wifi(auto_reconnect=True):
    global wifi, wifi_last_status, wifi_reconnect_time
    if wifi is None:
        wifi = network.WLAN(network.STA_IF)
    wifi.active(True)
    if not wifi.isconnected():
        wifi.connect(SSID, PASSWORD)
        timeout = 10
        while timeout > 0:
            if wifi.isconnected():
                break
            time.sleep(1)
            timeout -= 1
    wifi_last_status = wifi.isconnected()
    wifi_reconnect_time = time.ticks_ms()
    return wifi

def ensure_wifi():
    global wifi_reconnect_time
    now = time.ticks_ms()
    if wifi is None or not wifi.isconnected():
        if time.ticks_diff(now, wifi_reconnect_time) > 10000:
            connect_wifi()
    return wifi and wifi.isconnected()

def fetch_server_name():
    global server_name
    try:
        response = urequests.get(SYSTEM_URL)
        data = response.json()
        response.close()
        gc.collect()
        if "hostname" in data:
            server_name = ascii_polish(str(data["hostname"]))
        else:
            server_name = "Serwer"
    except Exception as e:
        print("Nie mogę pobrać nazwy serwera:", e)
        server_name = "Server"

def fetch_data():
    data = {}
    try:
        response = urequests.get(CPU_URL)
        cpu_data = response.json()
        response.close()
        data['cpu'] = cpu_data.get('total', 'N/A')
        gc.collect()
    except Exception as e:
        print(f"CPU error: {e}")
        data['cpu'] = 'N/A'
    try:
        response = urequests.get(MEM_URL)
        mem_data = response.json()
        response.close()
        data['mem'] = mem_data.get('percent', 'N/A')
        gc.collect()
    except Exception as e:
        print(f"MEM error: {e}")
        data['mem'] = 'N/A'
    try:
        response = urequests.get(SENSORS_URL)
        sensors = response.json()
        response.close()
        gc.collect()
        temp_value = 'N/A'
        for sensor in sensors:
            if sensor.get('label') == 'CPUTIN':
                temp_value = sensor.get('value', 'N/A')
                break
        data['temp'] = temp_value
    except Exception as e:
        print(f"TEMP error: {e}")
        data['temp'] = 'N/A'
    return data

def fetch_disk_data():
    try:
        response = urequests.get(DISK_URL)
        data = response.json()
        response.close()
        gc.collect()
        return data
    except Exception as e:
        print('Disk data error:', e)
        return None

def fetch_net_data():
    try:
        response = urequests.get(NETWORK_URL)
        data = response.json()
        response.close()
        gc.collect()
        return data
    except Exception as e:
        print('Net data error:', e)
        return None

def get_server_ip():
    # Wyciągnięcie IP z SERVER_URL (np. http://192.168.50.4:61208)
    url = conf.SERVER_URL
    if "://" in url:
        url = url.split("://",1)[1]
    if "/" in url:
        url = url.split("/",1)[0]
    ip = url.split(":")[0]
    return ip

def draw_brightness_slider():
    oled.fill_rect(0, 54, 128, 10, 0)
    slider_length = int((brightness / 255) * 128)
    oled.fill_rect(0, 54, slider_length, 8, 1)
    oled.rect(0, 54, 128, 8, 1)
    slider_label = T("BRIGHTNESS")
    x_label = (128 - len(slider_label)*6)//2
    for i, char in enumerate(slider_label):
        char_x = x_label + i*6
        char_mid = char_x + 3
        color = 0 if char_mid < slider_length else 1
        oled.text(char, char_x, 55, color)

def update_filtered_disks(data):
    global filtered_disks
    filtered_disks = []
    if data:
        if isinstance(data, dict) and 'fs' in data:
            fs_list = data['fs']
        elif isinstance(data, list):
            fs_list = data
        else:
            fs_list = []
        for disk in fs_list:
            mnt = disk.get('mnt_point', '')
            dev = disk.get('device', '')
            if dev.startswith('/dev/loop') or '/snap/' in mnt or '/core' in mnt or '/ngrok' in mnt or '/micro' in mnt:
                continue
            if not mnt:
                continue
            filtered_disks.append(disk)

def simplify_disk_name(mnt):
    if mnt == '/':
        base = 'root'
    elif mnt.startswith('/mnt/'):
        base = ascii_polish(mnt[5:])
    elif mnt.startswith('/boot'):
        base = 'boot'
    elif mnt.startswith('/home'):
        base = 'home'
    elif mnt.startswith('/var'):
        base = 'var'
    elif mnt.startswith('/srv'):
        base = 'srv'
    elif mnt.startswith('/media'):
        base = 'media'
    elif mnt.startswith('/'):
        base = ascii_polish(mnt[1:])
    else:
        base = ascii_polish(mnt)
    return base

def format_bytes_custom(val, unit):
    try:
        val = float(val)
    except:
        return str(val)
    units = ["B", "KB", "MB", "GB"]
    unit_index = units.index(unit) if unit in units else 3
    factor = 1024 ** unit_index
    return f"{val / factor:.1f}{unit}"

def display_disk_details():
    oled.fill(0)
    global filtered_disks, selected_disk_index, settings_state
    total_disks = len(filtered_disks)
    unit = settings_state.get("unit", "GB")
    if not filtered_disks:
        oled.text(T("DISK_NONE"), 0, 0)
    else:
        disk = filtered_disks[selected_disk_index]
        mnt = disk.get('mnt_point', disk.get('device', 'N/A'))
        label = simplify_disk_name(mnt)
        if len(label) > 4:
            label = label[:4] + "..."
        percent = disk.get('percent', 0)
        used = disk.get('used', 'N/A')
        size = disk.get('size', 'N/A')

        used_disp = format_bytes_custom(used, unit)
        size_disp = format_bytes_custom(size, unit)

        oled.text(T("OCCUP"), 0, 20, 1)
        oled.text("{:>3}%".format(int(percent)), 70, 20, 1)
        oled.fill_rect(0, 30, int(percent/100*128), 8, 1)
        oled.rect(0, 30, 128, 8, 1)
        idx_str = f" ({selected_disk_index+1}/{total_disks})"
        line1 = f"{label}{idx_str}"
        oled.text(line1, 0, 4, 1)
        oled.text(f"{T('USED')}: {ascii_polish(used_disp)}", 0, 44, 1)
        oled.text(f"{T('SIZE')}: {ascii_polish(size_disp)}", 0, 54, 1)
    oled.show()

def draw_wifi_icon(x, y, connected=True):
    for dx in range(-8, 9):
        dy = int((1 - (abs(dx)/8))**0.5 * 6) if abs(dx) <= 8 else 0
        if dy > 0:
            oled.pixel(x+8+dx, y+1+6-dy, 1)
    for dx in range(-6, 7):
        dy = int((1 - (abs(dx)/6))**0.5 * 4) if abs(dx) <= 6 else 0
        if dy > 0:
            oled.pixel(x+8+dx, y+5+4-dy, 1)
    for dx in range(-4, 5):
        dy = int((1 - (abs(dx)/4))**0.5 * 2) if abs(dx) <= 4 else 0
        if dy > 0:
            oled.pixel(x+8+dx, y+9+2-dy, 1)
    oled.fill_rect(x+8-2, y+13, 5, 3, 1)

def display_stats(data):
    oled.fill(0)
    global server_name
    # Wyśrodkowana nazwa serwera na górze (czas usunięty)
    name_disp = ascii_polish(server_name)
    x_name = (128 - len(name_disp)*8)//2
    oled.text(name_disp, x_name, 0, 1)
    oled.hline(0, 10, 128, 1)
    try:
        cpu = float(data['cpu'])
    except:
        cpu = 0
    try:
        mem = float(data['mem'])
    except:
        mem = 0
    try:
        temp = float(data['temp'])
    except:
        temp = 0
    oled.text("{:>3}%".format(int(cpu)), 6, 20, 1)
    oled.fill_rect(0, 34, int(cpu/100*40), 4, 1)
    oled.rect(0, 34, 40, 4, 1)
    oled.text("CPU", 10, 40, 1)
    oled.text("{:>3}%".format(int(mem)), 48, 20, 1)
    oled.fill_rect(44, 34, int(mem/100*40), 4, 1)
    oled.rect(44, 34, 40, 4, 1)
    oled.text("RAM", 52, 40, 1)
    oled.text("{:>3}".format(int(temp)), 90, 20, 1)
    oled.text("C", 110, 20, 1)
    oled.fill_rect(88, 34, min(int((temp/100)*40),40), 4, 1)
    oled.rect(88, 34, 40, 4, 1)
    oled.text("TEMP", 92, 40, 1)
    oled.hline(0, 52, 128, 1)
    wlan = wifi
    wifi_ok = wlan and wlan.isconnected()
    draw_wifi_icon(2, 54, wifi_ok)
    ssid_disp = ascii_polish(SSID)
    oled.text(ssid_disp, 24, 56, 1)
    if slider_visible:
        draw_brightness_slider()
    oled.show()

def draw_net_icon(x, y):
    oled.line(x+4, y+8, x+4, y+2, 1)
    oled.pixel(x+4, y+1, 1)
    oled.pixel(x+2, y+4, 1)
    oled.pixel(x+6, y+4, 1)
    oled.pixel(x+1, y+6, 1)
    oled.pixel(x+7, y+6, 1)
    oled.pixel(x+0, y+8, 1)
    oled.pixel(x+8, y+8, 1)

def draw_upload_icon(x, y):
    oled.vline(x+4, y+2, 8, 1)
    oled.hline(x+2, y+2, 5, 1)
    oled.pixel(x+4, y, 1)
    oled.pixel(x+3, y+1, 1)
    oled.pixel(x+5, y+1, 1)

def draw_download_icon(x, y):
    oled.vline(x+4, y, 8, 1)
    oled.hline(x+2, y+6, 5, 1)
    oled.pixel(x+4, y+8, 1)
    oled.pixel(x+3, y+7, 1)
    oled.pixel(x+5, y+7, 1)

def draw_speed_icon(x, y):
    for i in range(8):
        angle = i * (3.1415/4)
        dx = int(5 * math.cos(angle))
        dy = int(5 * math.sin(angle))
        oled.pixel(x+4+dx, y+4+dy, 1)
    oled.ellipse(x+4, y+4, 3, 3, 1)

def draw_ip_icon(x, y):
    # Prosta ikonka IP (monitor z kropką)
    oled.rect(x, y, 16, 10, 1)
    oled.hline(x+3, y+8, 10, 1)
    oled.fill_rect(x+7, y+11, 2, 2, 1)
    oled.pixel(x+14, y+12, 1)

def display_net_data(data):
    oled.fill(0)
    iface = None
    unit = "MB"
    if data and isinstance(data, list):
        for i in data:
            if i.get('interface_name', '') == 'enp3s0':
                iface = i
                break
    draw_net_icon(4, 4)
    oled.text("enp3s0", 20, 0, 1)
    oled.hline(0, 12, 128, 1)
    if iface:
        sent = iface.get('bytes_sent', 0)
        recv = iface.get('bytes_recv', 0)
        speed = iface.get('speed', 0)
        draw_upload_icon(4, 18)
        oled.text(format_bytes_custom(sent, unit), 20, 16, 1)
        draw_download_icon(4, 32)
        oled.text(format_bytes_custom(recv, unit), 20, 30, 1)
        draw_speed_icon(4, 46)
        oled.text(format_bytes_custom(speed, unit)+"/s", 20, 44, 1)
    else:
        oled.text(T("NETWORK_NO"), 0, 28)
    # IP serwera centralnie pod bandwidth z własną ikoną
    ip = get_server_ip()
    x_ip = (128 - len(ip)*8)//2
    draw_ip_icon(x_ip-18, 54)  # Ikona z lewej strony IP
    oled.text(ip, x_ip, 56, 1)
    oled.show()

def scroll_version_text(version, y, selected, now):
    max_width = 64
    char_width = 8
    text = version
    text_px = len(text) * char_width
    if selected and text_px > max_width:
        scroll_period = 1000 + (text_px - max_width) * 40
        offset = int((now % scroll_period) / 40)
        start = min(offset, len(text) - (max_width // char_width))
        text = text[start:start + (max_width // char_width)]
    else:
        text = text[:max_width // char_width]
    return text

def display_settings_panel(now=0):
    oled.fill(0)
    global settings, settings_index, settings_state, settings_scroll_offset
    oled.rect(0, 0, 128, 12, 1)
    oled.text(T("SETTINGS"), 33, 2, 1)
    oled.hline(0, 12, 128, 1)

    visible_lines = 3
    if settings_index < settings_scroll_offset:
        settings_scroll_offset = settings_index
    elif settings_index >= settings_scroll_offset + visible_lines:
        settings_scroll_offset = settings_index - visible_lines + 1
    visible_settings = settings[settings_scroll_offset:settings_scroll_offset+visible_lines]
    visible_idx = 0
    total_items = len(settings)
    for i, s in enumerate(visible_settings):
        y = 18 + 14 * visible_idx
        idx = settings_scroll_offset + i
        if s.get("header") and s["label"] == "VERSION":
            version_text = f"{T('VERSION')}. {MAIN_VERSION.strip()}"
            oled.text("- " + version_text + " -", 8, y, 1)
            oled.hline(0, y+10, 128, 1)
        elif s.get("header"):
            oled.text("- " + T(s["label"]) + " -", 10, y, 1)
            oled.hline(0, y+10, 128, 1)
        elif s.get("update"):
            if idx == settings_index:
                oled.rect(0, y-2, 128, 14, 1)
                oled.fill_rect(2, y, 124, 10, 0)
            prefix = ">" if idx == settings_index else " "
            oled.text(f"{prefix}{T('UPDATE')}", 4, y, 1)
        elif s.get("reset"):
            if idx == settings_index:
                oled.rect(0, y-2, 128, 14, 1)
                oled.fill_rect(2, y, 124, 10, 0)
            prefix = ">" if idx == settings_index else " "
            oled.text(f"{prefix}{T('RESET_DEFAULTS')}", 4, y, 1)
        else:
            if idx == settings_index:
                oled.rect(0, y-2, 128, 14, 1)
                oled.fill_rect(2, y, 124, 10, 0)
            prefix = ">" if idx == settings_index else " "
            val = settings_state[s["key"]]
            if s["key"] == "sleep_enabled" or s["key"] == "eco_mode":
                val = "On" if val else "Off"
            oled.text(f"{prefix}{T(s['label'])}: {val}", 4, y, 1)
        visible_idx += 1
    oled.show()

def display_update_confirm():
    oled.fill(0)
    oled.rect(0, 0, 128, 64, 1)
    oled.text(T("UPDATE"), 4, 8, 1)
    oled.hline(0, 18, 128, 1)
    oled.text(T("CONFIRM_UPDATE"), 4, 28, 1)
    oled.text(T("YES"), 4, 48, 1)
    oled.text(T("NO"), 64, 48, 1)
    oled.show()

def display_reset_confirm():
    oled.fill(0)
    oled.rect(0, 0, 128, 64, 1)
    oled.text(T("RESET_DEFAULTS"), 4, 8, 1)
    oled.hline(0, 18, 128, 1)
    oled.text(T("RESET_CONFIRM"), 4, 28, 1)
    oled.text(T("YES"), 4, 48, 1)
    oled.text(T("NO"), 64, 48, 1)
    oled.show()

def display_reset_done():
    oled.fill(0)
    oled.rect(0, 0, 128, 64, 1)
    oled.text(T("RESET_DONE"), 12, 28, 1)
    oled.show()
    time.sleep(1)

def display_update_progress(progress=0):
    oled.fill(0)
    oled.rect(0, 0, 128, 64, 1)
    oled.text(T("UPDATING"), 4, 8, 1)
    oled.hline(0, 18, 128, 1)
    oled.text(f"{T('PROGRESS')}: {progress}%", 4, 32, 1)
    bar_width = int(progress * 1.2)
    oled.rect(4, 48, 120, 8, 1)
    oled.fill_rect(4, 48, bar_width, 8, 1)
    oled.show()

def do_update_with_progress():
    for p in [10, 40, 70, 100]:
        display_update_progress(p)
        time.sleep(0.4)
    ugit.update_main()

def check_alert_triggers(data, disk_data):
    try:
        cpu = float(data.get('cpu', 0))
        if cpu > 90:
            trigger_alert("CPU > 90%")
    except:
        pass
    try:
        mem = float(data.get('mem', 0))
        if mem > 90:
            trigger_alert("RAM > 90%")
    except:
        pass
    try:
        temp = float(data.get('temp', 0))
        if temp > 75:
            trigger_alert("TEMP > 75C")
    except:
        pass

def get_local_hour():
    try:
        t = time.localtime()
        hour = t[3]
        tz = int(settings_state.get("timezone", 0))
        local_hour = (hour + tz) % 24
        return local_hour
    except:
        return 0

def is_sleep_time():
    if not settings_state.get("sleep_enabled", 0):
        return False
    try:
        local_hour = get_local_hour()
        start = settings_state["sleep_start"]
        end = settings_state["sleep_end"]
        if start < end:
            return start <= local_hour < end
        else:
            return local_hour >= start or local_hour < end
    except:
        return False

def handle_sleep_mode():
    global screen_off, last_activity_time, sleep_wake_ignore
    if is_sleep_time():
        if not button_k1.value() or not button_k2.value() or not button_k3.value() or not button_k4.value():
            if screen_off:
                sleep_wake_ignore = True
            screen_off = False
            last_activity_time = time.ticks_ms()
            oled.poweron()
            oled.contrast(brightness)
        if time.ticks_diff(time.ticks_ms(), last_activity_time) > SLEEP_DURATION:
            screen_off = True
            oled.poweroff()
    else:
        screen_off = False
        oled.poweron()
        oled.contrast(brightness)

def eco_mode_active():
    if settings_state.get("eco_mode", 0):
        now = time.ticks_ms()
        return time.ticks_diff(now, last_activity_time) > ECO_TIMEOUT
    return False

def any_button_pressed():
    return (not button_k1.value() or not button_k2.value() or
            not button_k3.value() or not button_k4.value())

def main():
    global settings_index, in_settings, in_update_confirm, in_update_progress, in_reset_confirm, settings_scroll_offset
    global brightness, slider_visible, slider_show_time, current_page, selected_disk_index
    global alert_active, alert_message, alert_start_time, server_name, sleep_wake_ignore, last_activity_time

    connect_wifi()
    try:
        ntptime.settime()
    except:
        pass
    fetch_server_name()
    set_brightness(brightness)
    last_press_time = time.ticks_ms()
    debounce_delay = 200
    last_fetch = time.ticks_ms() - settings_state["refresh"] * 1000
    data = fetch_data()
    disk_data = None
    net_data = None

    eco_active = False

    while True:
        now = time.ticks_ms()
        ensure_wifi()
        handle_sleep_mode()

        if eco_mode_active():
            if not eco_active:
                set_brightness(eco_brightness)
                eco_active = True
        else:
            if eco_active:
                set_brightness(brightness)
                eco_active = False

        if screen_off:
            time.sleep(0.1)
            continue
        if sleep_wake_ignore:
            if any_button_pressed():
                while any_button_pressed():
                    time.sleep(0.01)
                sleep_wake_ignore = False
            continue
        if alert_active:
            show_alert(alert_message, now)
            check_alert_clear()
            if time.ticks_diff(now, alert_start_time) > 10000:
                alert_active = False
            time.sleep(0.05)
            continue
        if in_settings:
            num_options = len(settings)
            if in_update_progress:
                do_update_with_progress()
                in_update_progress = False
                in_settings = False
                continue
            if in_update_confirm:
                display_update_confirm()
                if not button_k1.value():
                    in_update_confirm = False
                    in_update_progress = True
                elif not button_k2.value():
                    in_update_confirm = False
                time.sleep(0.05)
                continue
            if in_reset_confirm:
                display_reset_confirm()
                if not button_k1.value():
                    in_reset_confirm = False
                    reset_settings()
                    display_reset_done()
                elif not button_k2.value():
                    in_reset_confirm = False
                time.sleep(0.05)
                continue
            s = settings[settings_index]
            if s.get("header"):
                if not button_k3.value() and time.ticks_diff(now, last_press_time) > debounce_delay:
                    settings_index = (settings_index + 1) % num_options
                    last_press_time = now
            elif s.get("update"):
                if (not button_k1.value() or not button_k2.value()) and time.ticks_diff(now, last_press_time) > debounce_delay:
                    in_update_confirm = True
                    last_press_time = now
                elif not button_k3.value() and time.ticks_diff(now, last_press_time) > debounce_delay:
                    settings_index = (settings_index + 1) % num_options
                    last_press_time = now
            elif s.get("reset"):
                if (not button_k1.value() or not button_k2.value()) and time.ticks_diff(now, last_press_time) > debounce_delay:
                    in_reset_confirm = True
                    last_press_time = now
                elif not button_k3.value() and time.ticks_diff(now, last_press_time) > debounce_delay:
                    settings_index = (settings_index + 1) % num_options
                    last_press_time = now
            else:
                key = s["key"]
                if not button_k1.value() and time.ticks_diff(now, last_press_time) > debounce_delay:
                    if "options" in s:
                        idx = s["options"].index(settings_state[key])
                        settings_state[key] = s["options"][(idx + 1) % len(s["options"])]
                    else:
                        settings_state[key] = min(s["max"], settings_state[key] + s["step"])
                    save_settings()
                    last_press_time = now
                elif not button_k2.value() and time.ticks_diff(now, last_press_time) > debounce_delay:
                    if "options" in s:
                        idx = s["options"].index(settings_state[key])
                        settings_state[key] = s["options"][(idx - 1) % len(s["options"])]
                    else:
                        settings_state[key] = max(s["min"], settings_state[key] - s["step"])
                    save_settings()
                    last_press_time = now
                elif not button_k3.value() and time.ticks_diff(now, last_press_time) > debounce_delay:
                    settings_index = (settings_index + 1) % num_options
                    last_press_time = now
            if not button_k4.value() and time.ticks_diff(now, last_press_time) > debounce_delay:
                in_settings = False
                settings_index = 0
                settings_scroll_offset = 0
                last_press_time = now
            display_settings_panel(now)
            time.sleep(0.05)
            continue
        if any_button_pressed():
            last_activity_time = time.ticks_ms()
        if current_page == 1 and filtered_disks:
            if not button_k1.value() and time.ticks_diff(now, last_press_time) > debounce_delay:
                selected_disk_index = (selected_disk_index - 1) % len(filtered_disks)
                last_press_time = now
            elif not button_k2.value() and time.ticks_diff(now, last_press_time) > debounce_delay:
                selected_disk_index = (selected_disk_index + 1) % len(filtered_disks)
                last_press_time = now
            elif not button_k3.value() and time.ticks_diff(now, last_press_time) > debounce_delay:
                current_page = 2
                net_data = fetch_net_data()
                last_press_time = now
        elif current_page == 2:
            if not button_k3.value() and time.ticks_diff(now, last_press_time) > debounce_delay:
                current_page = 0
                last_press_time = now
        else:
            if not button_k1.value() and time.ticks_diff(now, last_press_time) > debounce_delay:
                set_brightness(brightness + 15)
                slider_visible = True
                slider_show_time = now
                last_press_time = now
            elif not button_k2.value() and time.ticks_diff(now, last_press_time) > debounce_delay:
                set_brightness(brightness - 15)
                slider_visible = True
                slider_show_time = now
                last_press_time = now
            elif not button_k3.value() and time.ticks_diff(now, last_press_time) > debounce_delay:
                if current_page == 0:
                    current_page = 1
                    disk_data = fetch_disk_data()
                    update_filtered_disks(disk_data)
                    selected_disk_index = 0
                elif current_page == 1:
                    current_page = 2
                    net_data = fetch_net_data()
                elif current_page == 2:
                    current_page = 0
                last_press_time = now
            elif not button_k4.value() and time.ticks_diff(now, last_press_time) > debounce_delay:
                in_settings = True
                settings_index = 0
                settings_scroll_offset = 0
                last_press_time = now
        if slider_visible and time.ticks_diff(now, slider_show_time) > 3000:
            slider_visible = False
        if time.ticks_diff(now, last_fetch) > settings_state["refresh"] * 1000:
            if current_page == 0:
                try:
                    data = fetch_data()
                    fetch_server_name()
                except:
                    trigger_alert("Serwer offline!")
            elif current_page == 1:
                try:
                    disk_data = fetch_disk_data()
                    update_filtered_disks(disk_data)
                    if selected_disk_index >= len(filtered_disks):
                        selected_disk_index = 0
                except:
                    trigger_alert("Serwer offline!")
            elif current_page == 2:
                try:
                    net_data = fetch_net_data()
                except:
                    trigger_alert("Serwer offline!")
            last_fetch = now
            check_alert_triggers(data, disk_data)
        if current_page == 0:
            display_stats(data)
        elif current_page == 1:
            display_disk_details()
        elif current_page == 2:
            display_net_data(net_data)
        time.sleep(0.03)
        gc.collect()

if __name__ == "__main__":
    main()

