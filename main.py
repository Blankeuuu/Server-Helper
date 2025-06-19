import network
import time
import urequests
import gc
from machine import Pin, I2C, reset, RTC
import ssd1306
import math
import conf
import ugit

MAIN_VERSION = "1.2.0"

LANGS = {
    "ENG": {
        "SETTINGS": "SETTINGS",
        "UNIT": "Unit",
        "REFRESH": "Refresh",
        "LANG": "Language",
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
        "UPDATE": "Update",
        "CONFIRM_UPDATE": "Check for update?",
        "YES": "Y=K1",
        "NO": "N=K2",
        "VERSION": "Ver",
        "SLEEP_START": "Sleep Start",
        "SLEEP_END": "Sleep End",
        "SLEEP_MODE": "Sleep Mode"
    },
    "PL": {
        "SETTINGS": "USTAWIENIA",
        "UNIT": "Jednostka",
        "REFRESH": "Odswiezanie",
        "LANG": "Jezyk",
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
        "UPDATE": "Aktualizuj",
        "CONFIRM_UPDATE": "Wyszukac aktualizacje?",
        "YES": "T=K1",
        "NO": "N=K2",
        "VERSION": "Wersja",
        "SLEEP_START": "Sen Start",
        "SLEEP_END": "Sen Koniec",
        "SLEEP_MODE": "Tryb Snu"
    }
}

# Zwiększona lista ustawień
settings = [
    {"label": "LANG", "key": "lang", "options": ["ENG", "PL"], "index": 0},
    {"label": "UNIT", "key": "unit", "options": ["B", "KB", "MB", "GB"], "index": 3},
    {"label": "REFRESH", "key": "refresh", "min": 1, "max": 60, "step": 1},
    {"label": "SLEEP_START", "key": "sleep_start", "min": 0, "max": 23, "step": 1},
    {"label": "SLEEP_END", "key": "sleep_end", "min": 0, "max": 23, "step": 1}
]

# Stan ustawień z domyślnymi wartościami
settings_state = {
    "lang": "ENG",
    "unit": "GB",
    "refresh": 5,
    "sleep_start": 22,  # 22:00
    "sleep_end": 6      # 06:00
}

settings_index = 0
in_settings = False
in_update_confirm = False
screen_off = False
last_activity_time = time.ticks_ms()
SLEEP_DURATION = 15 * 1000  # 15 sekund aktywności po przebudzeniu
settings_scroll_offset = 0  # Przesunięcie dla przewijania ustawień

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
        if len(l) < max_chars:
            x = (128 - len(l)*6)//2
        else:
            x = 1
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

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    for _ in range(20):
        if wlan.isconnected():
            return wlan
        time.sleep(1)
    trigger_alert("Brak WiFi!")
    raise RuntimeError("Nie udalo sie polaczyc z WiFi")

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
        dy = int((1 - (abs(dx)/4))**0.5 * 2) if abs(dx) <= 4 else 极
        if dy > 0:
            oled.pixel(x+8+dx, y+9+2-dy, 1)
    oled.fill_rect(x+8-2, y+13, 5, 3, 1)

def display_stats(data):
    oled.fill(0)
    global server_name
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
    wlan = network.WLAN(network.STA_IF)
    wifi_ok = wlan.isconnected()
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
    oled.show()

def display_settings_panel():
    oled.fill(0)
    global settings, settings_index, settings_state, settings_scroll_offset
    oled.text(T("SETTINGS"), 16, 0, 1)
    oled.hline(0, 12, 128, 1)
    
    # Automatyczne przewijanie
    if settings_index < settings_scroll_offset:
        settings_scroll_offset = settings_index
    elif settings_index >= settings_scroll_offset + 3:
        settings_scroll_offset = settings_index - 2
    
    # Wyświetlanie tylko widocznych ustawień
    visible_settings = settings[settings_scroll_offset:settings_scroll_offset+3]
    
    for i, s in enumerate(visible_settings):
        y = 20 + 12 * i
        idx = settings_scroll_offset + i
        prefix = ">" if idx == settings_index else " "
        key = s["key"]
        label = T(s["label"])
        val = settings_state[key]
        oled.text(f"{prefix}{label}: {val}", 0, y, 1)
    
    # Dodaj opcję aktualizacji jako ostatnią
    y = 20 + 12 * len(visible_settings)
    prefix = ">" if settings_index == len(settings) else " "
    oled.text(f"{prefix}{T('UPDATE')}", 0, y, 1)
    oled.text(f"{T('VERSION')}: {MAIN_VERSION}", 64, y, 1)
    oled.show()

def display_update_confirm():
    oled.fill(0)
    oled.text(T("UPDATE"), 0, 0, 1)
    oled.hline(0, 12, 128, 1)
    oled.text(T("CONFIRM_UPDATE"), 0, 24, 1)
    oled.text(T("YES"), 0, 44, 1)
    oled.text(T("NO"), 64, 44, 1)
    oled.show()

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

def is_sleep_time():
    try:
        # Pobierz aktualną godzinę (uproszczone - w rzeczywistości potrzebujesz RTC)
        _, _, _, hour, _, _, _, _ = time.localtime()
        start = settings_state["sleep_start"]
        end = settings_state["sleep_end"]
        
        if start < end:
            return start <= hour < end
        else:
            return hour >= start or hour < end
    except:
        return False

def handle_sleep_mode():
    global screen_off, last_activity_time
    
    if is_sleep_time():
        # Sprawdź czy użytkownik nacisnął przycisk
        if not button_k1.value() or not button_k2.value() or not button_k3.value() or not button_k4.value():
            screen_off = False
            last_activity_time = time.ticks_ms()
            oled.poweron()
            oled.contrast(brightness)
        
        # Sprawdź czy minęło 15 sekund od ostatniej aktywności
        if time.ticks_diff(time.ticks_ms(), last_activity_time) > SLEEP_DURATION:
            screen_off = True
            oled.poweroff()
    else:
        screen_off = False
        oled.poweron()
        oled.contrast(brightness)

def main():
    global brightness, slider_visible, slider_show_time, current_page, selected_disk_index
    global alert_active, alert_message, alert_start_time, server_name
    global in_settings, settings_index, settings_state, REFRESH_INTERVAL
    global in_update_confirm, settings_scroll_offset, screen_off, last_activity_time

    try:
        connect_wifi()
        fetch_server_name()
        set_brightness(brightness)
        last_press_time = time.ticks_ms()
        debounce_delay = 200
        last_fetch = time.ticks_ms() - REFRESH_INTERVAL * 1000
        data = fetch_data()
        disk_data = None
        net_data = None

        while True:
            now = time.ticks_ms()
            
            # Sprawdź tryb snu
            handle_sleep_mode()
            
            if screen_off:
                time.sleep(0.1)
                continue

            if alert_active:
                show_alert(alert_message, now)
                check_alert_clear()
                if time.ticks_diff(now, alert_start_time) > 10000:
                    alert_active = False
                time.sleep(0.05)
                continue

            # --- PANEL USTAWIEŃ ---
            if in_settings:
                num_options = len(settings) + 1
                if in_update_confirm:
                    display_update_confirm()
                    if time.ticks_diff(now, last_press_time) > debounce_delay:
                        if not button_k1.value() or not button_k2.value():
                            ugit.update_main()
                            in_update_confirm = False
                            in_settings = False
                            last_press_time = now
                    time.sleep(0.05)
                    continue

                if time.ticks_diff(now, last_press_time) > debounce_delay:
                    if settings_index < len(settings):
                        if not button_k1.value():
                            s = settings[settings_index]
                            key = s["key"]
                            if "options" in s:
                                current_idx = s["options"].index(settings_state[key])
                                new_idx = (current_idx + 1) % len(s["options"])
                                settings_state[key] = s["options"][new_idx]
                            else:
                                settings_state[key] = min(s["max"], settings_state[key] + s["step"])
                                if key == "refresh":
                                    REFRESH_INTERVAL = settings_state[key]
                            last_press_time = now
                        elif not button_k2.value():
                            s = settings[settings_index]
                            key = s["key"]
                            if "options" in s:
                                current_idx = s["options"].index(settings_state[key])
                                new_idx = (current_idx - 1) % len(s["options"])
                                settings_state[key] = s["options"][new_idx]
                            else:
                                settings_state[key] = max(s["min"], settings_state[key] - s["step"])
                                if key == "refresh":
                                    REFRESH_INTERVAL = settings_state[key]
                            last_press极 now
                    else:
                        # Jeśli jesteśmy na opcji "Update", zarówno K1 jak i K2 wywołują potwierdzenie
                        if not button_k1.value() or not button_k2.value():
                            in_update_confirm = True
                            last_press_time = now
                    if not button_k3.value():
                        settings_index = (settings_index + 1) % num_options
                        last_press_time = now
                    elif not button_k4.value():
                        in_settings = False
                        settings_index = 0
                        settings_scroll_offset = 0
                        last_press_time = now

                display_settings_panel()
                time.sleep(0.05)
                continue

            if time.ticks_diff(now, last_press_time) > debounce_delay:
                if current_page == 1 and filtered_disks:
                    if not button_k1.value():
                        selected_disk_index = (selected_disk_index - 1) % len(filtered_disks)
                        last_press_time = now
                    elif not button_k2.value():
                        selected_disk_index = (selected_disk_index + 1) % len(filtered_disks)
                        last_press_time = now
                    elif not button_k3.value():
                        current_page = 2
                        net_data = fetch_net_data()
                        last_press_time = now
                elif current_page == 2:
                    if not button_k3.value():
                        current_page = 0
                        last_press_time = now
                else:
                    if not button_k1.value():
                        set_brightness(brightness + 15)
                        slider_visible = True
                        slider_show_time = now
                        last_press_time = now
                    elif not button_k2.value():
                        set_brightness(brightness - 15)
                        slider_visible = True
                        slider_show_time = now
                        last_press_time = now
                    elif not button_k3.value():
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
                    elif not button_k4.value():
                        in_settings = True
                        settings_index = 0
                        settings_scroll_offset = 0
                        last_press_time = now

            if slider_visible and time.ticks_diff(now, slider_show_time) > 3000:
                slider_visible = False

            if time.ticks_diff(now, last_fetch) > REFRESH_INTERVAL * 1000:
                if current_page == 0:
                    data = fetch_data()
                    fetch_server_name()
                elif current_page == 1:
                    disk_data = fetch_disk_data()
                    update_filtered_disks(disk_data)
                    if selected_disk_index >= len(filtered_disks):
                        selected_disk_index = 0
                elif current_page == 2:
                    net_data = fetch_net_data()
                last_fetch = now
                check_alert_triggers(data, disk_data)

            if current_page == 0:
                display_stats(data)
            elif current_page == 1:
                display_disk_details()
            elif current_page == 2:
                display_net_data(net_data)

            time.sleep(0.05)
            gc.collect()

    except Exception as e:
        trigger_alert("Krytyczny blad!")
        print(f"Krytyczny blad: {e}")
        time.sleep(5)
        reset()

if __name__ == "__main__":
    main()
