# PicoServerMonitor

A lightweight, WiFi-enabled hardware monitor for Ubuntu servers using Raspberry Pi Pico W and an SSD1306 OLED display. This project displays real-time server stats (CPU, RAM, temperature, disk usage, network info) and supports configuration via a hardware menu. It is designed for easy deployment and remote monitoring of home or small office servers.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Function Descriptions](#function-descriptions)
- [Configuration-confpy](#configuration-confpy)
- [Server Setup](#server-setup)
- [Update Settings](#update-settings)
- [Known Issues](#known-issues)
- [Links](#links)

---

## Installation

**Hardware Requirements:**
- Raspberry Pi Pico W (RP2040, WiFi, Bluetooth)
- SSD1306 0.96" OLED display (I2C, 128x64, 4-button panel)
- MicroSD card (64GB recommended)
- Ubuntu server (tested on 20.04/22.04)

**Software Prerequisites:**
- MicroPython firmware for Pico W ([Download here](https://micropython.org/download/rp2-pico-w/))
- [mpremote](https://github.com/micropython/micropython/tree/master/tools/mpremote) or [Thonny IDE](https://thonny.org/) for uploading files
- Python 3.x on the server

**Installation Steps:**

1. **Flash MicroPython:**
   - Download the latest MicroPython UF2 for Pico W.
   - Hold the BOOTSEL button, connect Pico to USB, and drag the UF2 file to the RPI-RP2 drive.

2. **Prepare the Project Files:**
   - Clone or download this repository.
   - Edit `conf.py` with your WiFi and server details (see [Configuration-confpy](#configuration-confpy)).
   - Upload all `.py` files (including `conf.py`) to the Pico W using Thonny or mpremote:

     ```sh
     mpremote connect  cp *.py :
     ```

3. **Connect Hardware:**
   - Wire the SSD1306 display to the Pico W (I2C: SCL=GP1, SDA=GP0).
   - Connect the four buttons to GP2, GP3, GP4, GP5 (active low with pull-ups).

4. **Insert MicroSD (optional):**
   - For extended logging or updates, insert a formatted microSD card.

---

## Usage

- **Power the Pico W:** Connect via USB or 5V supply.
- **Boot:** The display will show server connection status and stats.
- **Navigation:**
  - K1: Increase value / Previous disk / Increase brightness
  - K2: Decrease value / Next disk / Decrease brightness
  - K3: Next page (Stats → Disks → Network)
  - K4: Open settings menu / Back

- **Settings Menu:** Hold K4 to enter. Use K1/K2 to change values, K3 to move, K4 to exit.
- **Alerts:** If CPU, RAM, or temperature exceeds thresholds, an alert appears.
- **Sleep & Eco Modes:** Configurable via settings for power saving.

---

## Function Descriptions

| Function                    | Description                                                                                 |
|-----------------------------|---------------------------------------------------------------------------------------------|
| `main()`                    | Main loop: handles UI, button input, data fetching, sleep/eco logic                        |
| `fetch_data()`              | Fetches CPU, RAM, and temperature stats from the server                                     |
| `fetch_disk_data()`         | Retrieves disk usage info from the server                                                   |
| `fetch_net_data()`          | Retrieves network interface stats from the server                                           |
| `display_stats()`           | Renders CPU, RAM, and temperature on the OLED display                                       |
| `display_disk_details()`    | Shows disk usage, allows cycling through disks                                              |
| `display_net_data()`        | Shows network stats (sent/received, speed, IP)                                              |
| `display_settings_panel()`  | Draws the settings menu and handles navigation                                              |
| `save_settings()`           | Saves current settings to `conf.py`                                                         |
| `reset_settings()`          | Restores settings to defaults                                                               |
| `do_update_with_progress()` | Handles OTA update progress and triggers update script (`ugit.update_main()`)               |
| `connect_wifi()`            | Connects to WiFi using credentials from `conf.py`                                           |
| `ascii_polish()`            | Converts Polish characters to ASCII for OLED compatibility                                  |
| `trigger_alert()`           | Displays alert messages for critical server states                                          |
| `eco_mode_active()`         | Determines if eco mode should dim the display                                               |
| `is_sleep_time()`           | Checks if the device should enter sleep mode based on settings                              |

---

## Configuration (conf.py)

The `conf.py` file stores all user-editable settings. Example:

```python
SSID = "YourWiFiSSID"
PASSWORD = "YourWiFiPassword"
SERVER_URL = "http://192.168.1.100:61208"
CPU_URL = SERVER_URL + "/api/cpu"
MEM_URL = SERVER_URL + "/api/mem"
SENSORS_URL = SERVER_URL + "/api/sensors"
DISK_URL = SERVER_URL + "/api/disk"
NETWORK_URL = SERVER_URL + "/api/net"
SYSTEM_URL = SERVER_URL + "/api/system"
settings = {
    "lang": "ENG",        # "ENG" or "PL"
    "unit": "GB",         # "B", "KB", "MB", "GB"
    "refresh": 5,         # Refresh interval (seconds)
    "eco_mode": 0,        # 0=off, 1=on
    "sleep_enabled": 0,   # 0=off, 1=on
    "sleep_start": 23,    # Sleep start hour (0-23)
    "sleep_end": 7,       # Sleep end hour (0-23)
    "timezone": 0         # Timezone offset from UTC
}
DEFAULTS = settings.copy()

def save(settings_dict):
    # Save settings to file (implementation provided in code)
    pass
```

**How to configure:**
- Edit WiFi credentials and server URLs to match your network and server.
- Adjust `settings` for your preferences (language, units, refresh interval, etc.).

---

## Server Setup

**Server Requirements:**
- Ubuntu server with Python 3.x
- [psutil](https://pypi.org/project/psutil/) and [Flask](https://pypi.org/project/Flask/) installed

**Install dependencies:**

```sh
sudo apt update
sudo apt install python3-pip
pip3 install flask psutil
```

**Example server-side script:**

```python
from flask import Flask, jsonify
import psutil
import platform

app = Flask(__name__)

@app.route("/api/cpu")
def cpu():
    return jsonify({"total": psutil.cpu_percent(interval=0.5)})

@app.route("/api/mem")
def mem():
    return jsonify({"percent": psutil.virtual_memory().percent})

@app.route("/api/sensors")
def sensors():
    # Example: return CPU temperature
    try:
        import sensors
        temps = sensors.get_temperatures()
        return jsonify([{"label": "CPUTIN", "value": temps["coretemp"].current}])
    except:
        return jsonify([])

@app.route("/api/disk")
def disk():
    disks = []
    for part in psutil.disk_partitions():
        usage = psutil.disk_usage(part.mountpoint)
        disks.append({
            "mnt_point": part.mountpoint,
            "device": part.device,
            "percent": usage.percent,
            "used": usage.used,
            "size": usage.total
        })
    return jsonify({"fs": disks})

@app.route("/api/net")
def net():
    net_io = psutil.net_io_counters(pernic=True)
    return jsonify([{
        "interface_name": k,
        "bytes_sent": v.bytes_sent,
        "bytes_recv": v.bytes_recv,
        "speed": 0  # Fill with actual speed if available
    } for k, v in net_io.items()])

@app.route("/api/system")
def system():
    return jsonify({"hostname": platform.node()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=61208)
```

- Save as `server_api.py` and run: `python3 server_api.py`
- Ensure your firewall allows port 61208.

---

## Update Settings

- **OTA Update:** In the settings menu, select "Update" and confirm. The device will fetch and apply the latest code using the `ugit` module.
- **Manual Update:** Upload new `.py` files via Thonny or mpremote.

---

## Known Issues

- **Polish Language Formatting:** Some Polish characters are not rendered natively on the SSD1306 OLED. The function `ascii_polish()` transliterates Polish diacritics to ASCII, which may affect text appearance.
- **Disk Filtering:** The device ignores loop devices, snap/core, and certain mounts for clarity.
- **Network Speed:** Actual interface speed may not be available on all systems; the server script reports 0 if not implemented.
- **Button Debounce:** Button presses are debounced in software, but rapid presses may occasionally be missed.
- **Server Offline Alerts:** If the server is unreachable, "Serwer offline!" will be shown.

---

## Links

- [Project Repository](https://github.com/Blankeuuu/Server-Helper)
- [MicroPython for Pico W](https://micropython.org/download/rp2-pico-w/)
- [SSD1306 MicroPython Driver](https://github.com/micropython/micropython/blob/master/drivers/display/ssd1306.py)
- [Thonny IDE](https://thonny.org/)
- [mpremote Tool](https://github.com/micropython/micropython/tree/master/tools/mpremote)
- [psutil Documentation](https://psutil.readthedocs.io/)
- [Flask Documentation](https://flask.palletsprojects.com/)

---

For questions or contributions, please open an issue or pull request on the [GitHub repository](https://github.com/Blankeuuu/Server-Helper).
```

---
