import network
import time
import urequests
import gc
from machine import Pin, I2C, reset, RTC
import ssd1306
import math
import conf
import ugit

# ======================
# KONFIGURACJA WERSJI
# ======================
MAIN_VERSION = "1.2.1"

# ======================
# SYSTEM JĘZYKOWY
# ======================
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

# ======================
# KONFIGURACJA USTAWIEN
# ======================
settings = [
    {"label": "LANG", "key": "lang", "options": ["ENG", "PL"], "index": 0},
    {"label": "UNIT", "key": "unit", "options": ["B", "KB", "MB", "GB"], "index": 3},
    {"label": "REFRESH", "key": "refresh", "min": 1, "max": 60, "step": 1},
    {"label": "SLEEP_START", "key": "sleep_start", "min": 0, "max": 23, "极": 1},
    {"label": "SLEEP_END", "key": "sleep_end", "min": 0, "max": 23, "step": 1}
]

settings_state = {
    "lang": "ENG",
    "unit": "GB",
    "refresh": 5,
    "sleep_start": 22,
    "sleep_end": 6
}

# ======================
# ZMIENNE GLOBALNE
# ======================
settings_index = 0
in_settings = False
in_update_confirm = False
screen_off = False
last_activity_time = time.ticks_ms()
SLEEP_DURATION = 15 * 1000  # 15 sekund aktywności po przebudzeniu
settings_scroll_offset = 0

# Konfiguracja połączenia
SSID = conf.SSID
PASSWORD = conf.PASSWORD
REFRESH_INTERVAL = settings_state["refresh"]
CPU_URL = conf.CPU_URL
MEM_URL = conf.MEM_URL
SENSORS_URL = conf.SENSORS_URL
DISK_URL = conf.DISK_URL
NETWORK_URL = conf.NETWORK_URL
SYSTEM_URL = conf.SYSTEM_URL

# Inicjalizacja sprzętu
i2c = I2C(0, scl=Pin(1), sda=Pin(0))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)
button_k1 = Pin(2, Pin.IN, Pin.PULL_UP)
button_k2 = Pin(3, Pin.IN, Pin.PULL_UP)
button_k3 = Pin(4, Pin.IN, Pin.PULL_UP)
button_k4 = Pin(5, Pin极, Pin.PULL_UP)

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

# ======================
# FUNKCJE POMOCNICZE
# ======================

def T(key):
    """Zwraca tłumaczenie dla danego klucza w aktualnym języku"""
    return LANGS[settings_state.get("lang", "ENG")][key]

def ascii_polish(text):
    """Konwertuje polskie znaki diakrytyczne na ASCII"""
    pol = "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
    asc = "acelnoszzACELNOSZZ"
    return ''.join(asc[pol.index(c)] if c in pol else c for c in text)

def trigger_alert(msg):
    """Aktywuje alert z podaną wiadomością"""
    global alert_active, alert_message, alert_start_time
    alert_active = True
    alert_message = msg
    alert_start_time = time.ticks_ms()

def show_alert(msg, now):
    """Wyświetla alert na ekranie OLED"""
    oled.fill(0)
    oled.rect(0, 0, 128, 64, 1)
    alert_text = T("ALERT")
    x_alert = (128 - len(alert_text)*8)//2
    for dy in [0,1]:
        oled.text(alert_text, x_alert, 6+dy, 1)
    
    # Przygotowanie wiadomości do wyświetlenia
    max_chars = 21
    max_lines = 3
    lines = []
    m = ascii_polish(msg)
    
    while len(m) > 0:
        lines.append(m[:max_chars])
        m = m[max_chars:]
    
    if len(lines) <= max_lines:
        visible_lines = lines
    else:
        scroll_period = 2000
        first_line = (now // scroll_period) % (len(lines) - max_lines + 1)
        visible_lines = lines[first_line:first_line+max_lines]
    
    # Wyświetlanie linii
    for idx, l in enumerate(visible_lines):
        y = 28 + idx*12
        x = (128 - len(l)*6)//2 if len(l) < max_chars else 1
        oled.text(l, x, y, 1)
    
    oled.show()

def check_alert_clear():
    """Sprawdza czy alert został wyłączony przez użytkownika"""
    global alert_active
    if any(not btn.value() for btn in [button_k1, button_k2, button_k3, button_k4]):
        alert_active = False

def set_brightness(value):
    """Ustawia jasność wyświetlacza OLED"""
    global brightness
    brightness = max(0, min(255, value))
    oled.contrast(brightness)

def connect_wifi():
    """Łączy z siecią WiFi zdefiniowaną w konfiguracji"""
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
    """Pobiera nazwę serwera z API"""
    global server_name
    try:
        response = urequests.get(SYSTEM_URL)
        data = response.json()
        response.close()
        gc.collect()
        server_name = ascii_polish(data.get("hostname", "Serwer"))
    except Exception as e:
        print("Nie mogę pobrać nazwy serwera:", e)
        server_name = "Server"

def fetch_data():
    """Pobiera dane o CPU, RAM i temperaturze z serwera"""
    data = {}
    try:
        response = urequests.get(CPU_URL)
        data['cpu'] = response.json().get('total', 'N/A')
        response.close()
        gc.collect()
    except Exception as e:
        print(f"CPU error: {e}")
        data['cpu'] = 'N/A'
    
    # Analogicznie dla MEM i TEMP...
    return data

def fetch_disk_data():
    """Pobiera dane o dyskach z serwera"""
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
    """Pobiera dane sieciowe z serwera"""
    try:
        response = urequests.get(NETWORK_URL)
        data = response.json()
        response.close()
        gc.collect()
        return data
    except Exception as e:
        print('Net data error:', e)
        return None

# ======================
# FUNKCJE WYŚWIETLANIA
# ======================

def draw_brightness_slider():
    """Rysuje suwak jasności na dole ekranu"""
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
    """Filtruje i aktualizuje listę dysków do wyświetlenia"""
    global filtered_disks
    filtered_disks = []
    
    if data:
        fs_list = data.get('fs', []) if isinstance(data, dict) else data
        
        for disk in fs_list:
            mnt = disk.get('mnt_point', '')
            dev = disk.get('device', '')
            
            # Pomijanie dysków systemowych i specjalnych
            if any(pattern in dev or pattern in mnt for pattern in 
                  ['/dev/loop', '/snap/', '/core', '/ngrok', '/micro']):
                continue
            
            if mnt:
                filtered_disks.append(disk)

def simplify_disk_name(mnt):
    """Uproszcza nazwę punktu montowania dysku"""
    if mnt == '/': return 'root'
    if mnt.startswith('/mnt/'): return ascii_polish(mnt[5:])
    if mnt.startswith('/boot'): return 'boot'
    if mnt.startswith('/home'): return 'home'
    if mnt.startswith('/var'): return 'var'
    if mnt.startswith('/srv'): return 'srv'
    if mnt.startswith('/media'): return 'media'
    if mnt.startswith('/'): return ascii_polish(mnt[1:])
    return ascii_polish(mnt)

def format_bytes_custom(val, unit):
    """Formatuje bajty do wybranej jednostki"""
    try:
        val = float(val)
        units = ["B", "KB", "MB", "GB"]
        unit_index = units.index(unit) if unit in units else 3
        return f"{val / (1024 ** unit_index):.1f}{unit}"
    except:
        return str(val)

def display_disk_details():
    """Wyświetla szczegóły wybranego dysku"""
    oled.fill(0)
    global filtered_disks, selected_disk_index
    unit = settings_state.get("unit", "GB")
    
    if not filtered_disks:
        oled.text(T("DISK_NONE"), 0, 0)
    else:
        disk = filtered_disks[selected_disk_index]
        mnt = disk.get('mnt_point', 'N/A')
        label = simplify_disk_name(mnt)[:4] + "..." if len(mnt) > 4 else simplify_disk_name(mnt)
        percent = disk.get('percent', 0)
        used = format_bytes_custom(disk.get('used', 'N/A'), unit)
        size = format_bytes_custom(disk.get('size', 'N/A'), unit)
        total_disks = len(filtered_disks)
        
        oled.text(f"{label} ({selected_disk_index+1}/{total_disks})", 0, 4, 1)
        oled.text(T("OCCUP"), 0, 20, 1)
        oled.text(f"{int(percent)}%", 70, 20, 1)
        oled.fill_rect(0, 30, int(percent/100*128), 8, 1)
        oled.rect(0, 30, 128, 8, 1)
        oled.text(f"{T('USED')}: {ascii_polish(used)}", 0, 44, 1)
        oled.text(f"{T('SIZE')}: {ascii_polish(size)}", 0, 54, 1)
    
    oled.show()

def draw_wifi_icon(x, y, connected=True):
    """Rysuje ikonę WiFi w podanej pozycji"""
    # Rysowanie trzech łuków reprezentujących siłę sygnału
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
    
    # Rysowanie podstawy ikony
    oled.fill_rect(x+6, y+13, 5, 3, 1)

def display_stats(data):
    """Wyświetla główny ekran ze statystykami serwera"""
    oled.fill(0)
    
    # Nagłówek z nazwą serwera
    name_disp = ascii_polish(server_name)
    x_name = (128 - len(name_disp)*8)//2
    oled.text(name_disp, x_name, 0, 1)
    oled.hline(0, 10, 128, 1)
    
    # Dane CPU
    cpu = float(data.get('cpu', 0))
    oled.text(f"{int(cpu)}%", 6, 20, 1)
    oled.fill_rect(0, 34, int(cpu/100*40), 4, 1)
    oled.rect(0, 34, 40, 4, 1)
    oled.text("CPU", 10, 40, 1)
    
    # Dane RAM
    mem = float(data.get('mem', 0))
    oled.text(f"{int(mem)}%", 48, 20, 1)
    oled.fill_rect(44, 34, int(mem/100*40), 4, 1)
    oled.rect(44, 34, 40, 4, 1)
    oled.text("RAM", 52, 40, 1)
    
    # Dane temperatury
    temp = float(data.get('temp', 0))
    oled.text(f"{int(temp)}C", 90, 20, 1)
    oled.fill_rect(88, 34, min(int((temp/100)*40),40), 4, 1)
    oled.rect(88, 34, 40, 4, 1)
    oled.text("TEMP", 92, 40, 1)
    
    # Stopka z informacją o WiFi
    oled.hline(0, 52, 128, 1)
    wlan = network.WLAN(network.STA_IF)
    draw_wifi_icon(2, 54, wlan.isconnected())
    oled.text(ascii_polish(SSID), 24, 56, 1)
    
    # Suwak jasności (jeśli widoczny)
    if slider_visible:
        draw_brightness_slider()
    
    oled.show()

def display_net_data(data):
    """Wyświetla ekran ze statystykami sieciowymi"""
    oled.fill(0)
    iface = None
    unit = "MB"
    
    # Wyszukiwanie interfejsu enp3s0
    if data and isinstance(data, list):
        for i in data:
            if i.get('interface_name', '') == 'enp3s0':
                iface = i
                break
    
    # Rysowanie ikon i danych sieciowych
    draw_net_icon(4, 4)
    oled.text("enp3s0", 20, 0, 1)
    oled.hline(0, 12, 128, 1)
    
    if iface:
        # Wysyłane dane
        draw_upload_icon(4, 18)
        oled.text(format_bytes_custom(iface.get('bytes_sent', 0), unit), 20, 16, 1)
        
        # Odbierane dane
        draw_download_icon(4, 32)
        oled.text(format_bytes_custom(iface.get('bytes_recv', 0), unit), 20, 30, 1)
        
        # Prędkość połączenia
        draw_speed_icon(4, 46)
        oled.text(f"{format_bytes_custom(iface.get('speed', 0), unit)}/s", 20, 44, 1)
    else:
        oled.text(T("NETWORK_NO"), 0, 28)
    
    oled.show()

def display_settings_panel():
    """Wyświetla panel ustawień z możliwością przewijania"""
    oled.fill(0)
    global settings, settings_index, settings_scroll_offset
    oled.text(T("SETTINGS"), 16, 0, 1)
    oled.hline(0, 12, 128, 1)
    
    # Automatyczne przewijanie
    if settings_index < settings_scroll_offset:
        settings_scroll_offset = settings_index
    elif settings_index >= settings_scroll_offset + 3:
        settings_scroll_offset = settings_index - 2
    
    # Wyświetlanie widocznych ustawień
    visible_settings = settings[settings_scroll_offset:settings_scroll_offset+3]
    
    for i, s in enumerate(visible_settings):
        y = 20 + 12 * i
        idx = settings_scroll_offset + i
        prefix = ">" if idx == settings_index else " "
        val = settings_state[s["key"]]
        oled.text(f"{prefix}{T(s['label'])}: {val}", 0, y, 1)
    
    # Opcja aktualizacji na dole
    y = 20 + 12 * len(visible_settings)
    prefix = ">" if settings_index == len(settings) else " "
    oled.text(f"{prefix}{T('UPDATE')}", 0, y, 1)
    oled.text(f"{T('VERSION')}: {MAIN_VERSION}", 64, y, 1)
    oled.show()

def display_update_confirm():
    """Wyświetla potwierdzenie aktualizacji"""
    oled.fill(0)
    oled.text(T("UPDATE"), 0, 0, 1)
    oled.hline(0, 12, 128, 1)
    oled.text(T("CONFIRM_UPDATE"), 0, 24, 1)
    oled.text(T("YES"), 0, 44, 1)
    oled.text(T("NO"), 64, 44, 1)
    oled.show()

# ======================
# FUNKCJE LOGIKI SYSTEMU
# ======================

def check_alert_triggers(data, disk_data):
    """Sprawdza warunki dla alertów systemowych"""
    try:
        if float(data.get('cpu', 0)) > 90: trigger_alert("CPU > 90%")
        if float(data.get('mem', 0)) > 90: trigger_alert("RAM > 90%")
        if float(data.get('temp', 0)) > 75: trigger_alert("TEMP > 75C")
    except:
        pass

def is_sleep_time():
    """Sprawdza czy aktualnie obowiązuje okres uśpienia"""
    try:
        _, _, _, hour, _, _, _, _ = time.localtime()
        start = settings_state["sleep_start"]
        end = settings_state["sleep_end"]
        return (start <= hour < end) if start < end else (hour >= start or hour < end)
    except:
        return False

def handle_sleep_mode():
    """Zarządza trybem uśpienia ekranu"""
    global screen_off, last_activity_time
    
    if is_sleep_time():
        # Aktywacja po naciśnięciu przycisku
        if any(not btn.value() for btn in [button_k1, button_k2, button_k3, button_k4]):
            screen_off = False
            last_activity_time = time.ticks_ms()
            oled.poweron()
            oled.contrast(brightness)
        
        # Dezaktywacja po 15s bezczynności
        if time.ticks_diff(time.ticks_ms(), last_activity_time) > SLEEP_DURATION:
            screen_off = True
            oled.poweroff()
    else:
        screen_off = False
        oled.poweron()
        oled.contrast(brightness)

# ======================
# FUNKCJA GŁÓWNA
# ======================
def main():
    global brightness, current_page, alert_active, in_settings, in_update_confirm
    global last_activity_time, settings_scroll_offset, screen_off, last_press_time
    global last_fetch, data, disk_data, net_data, filtered_disks, selected_disk_index

    # Inicjalizacja połączeń
    connect_wifi()
    fetch_server_name()
    set_brightness(brightness)
    
    # Zmienne stanu
    last_press_time = time.ticks_ms()
    debounce_delay = 200
    last_fetch = time.ticks_ms() - REFRESH_INTERVAL * 1000
    data = fetch_data()
    disk_data = None
    net_data = None

    # Główna pętla programu
    while True:
        now = time.ticks_ms()
        
        # Zarządzanie trybem uśpienia
        handle_sleep_mode()
        if screen_off:
            time.sleep(0.1)
            continue

        # Obsługa alertów
        if alert_active:
            show_alert(alert_message, now)
            check_alert_clear()
            if time.ticks_diff(now, alert_start_time) > 10000:
                alert_active = False
            time.sleep(0.05)
            continue

        # Panel ustawień
        if in_settings:
            # ... (logika panelu ustawień)
            continue

        # Obsługa przycisków
        if time.ticks_diff(now, last_press_time) > debounce_delay:
            # ... (logika przycisków)
            pass

        # Aktualizacja danych
        if time.ticks_diff(now, last_fetch) > REFRESH_INTERVAL * 1000:
            # ... (pobieranie i aktualizacja danych)
            pass

        # Renderowanie aktualnego ekranu
        if current_page == 0:
            display_stats(data)
        elif current_page == 1:
            display_disk_details()
        elif current_page == 2:
            display_net_data(net_data)

        time.sleep(0.05)
        gc.collect()

if __name__ == "__main__":
    main()
