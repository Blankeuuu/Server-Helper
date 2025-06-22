# Server Helper

A lightweight, WiFi-enabled hardware monitor for Ubuntu servers using Raspberry Pi Pico 2W and an SSD1306 OLED display. This project displays real-time server stats (CPU, RAM, temperature, disk usage, network info) and supports configuration via a hardware menu. It is designed for easy deployment and remote monitoring of home or small office servers.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Function Descriptions](#function-descriptions)
- [Configuration (conf.py)](#configuration-confpy)
- [Server Setup](#server-setup)
- [Update Settings](#update-settings)
- [Known Issues](#known-issues)
- [Links](#links)

---

## Installation

**Hardware Requirements:**
- Raspberry Pi Pico 2W (RP2040, WiFi, Bluetooth)
- SSD1306 0.96" OLED display (I2C, 128x64, 4-button panel)
- Ubuntu server (tested on 20.04/22.04)

**Software Prerequisites:**
- MicroPython firmware for Pico W/2W ([Download here](https://micropython.org/download/rp2-pico-w/))
- [mpremote](https://github.com/micropython/micropython/tree/master/tools/mpremote) or [Thonny IDE](https://thonny.org/) for uploading files
- Python 3.x on the server

**Installation Steps:**

1. **Flash MicroPython:**
   - Download the latest MicroPython UF2 for Pico 2W.
   - Hold the BOOTSEL button, connect Pico to USB, and drag the UF2 file to the RPI-RP2 drive.

2. **Prepare the Project Files:**
   - Clone or download this repository.
   - Edit `conf.py` with your WiFi and server details (see [Configuration (conf.py)](#configuration-confpy)).
   - Upload the following files to your Pico 2W using Thonny or mpremote:
     - `main.py`
     - `conf.py`
     - `ssd1306.py`
     - `ugit.py`

     Example with mpremote:
     ```sh
     mpremote connect  cp main.py :
     mpremote connect  cp conf.py :
     mpremote connect  cp ssd1306.py :
     mpremote connect  cp ugit.py :
     ```

3. **Connect Hardware:**
   
| pico PI 2W | Screen |
|------------|--------|
| GND        | GND    |
| 3V3        | VCC    |
| GP1        | SCL    |
| GP0        | SDA    |
| GP2        | K1     |
| GP3        | K2     |
| GP4        | K3     |
| GP5        | K4     |

---

## Usage

- **Power the Pico 2W:** Connect via USB or 5V supply.
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

The server-side component uses **Glances** with its built-in REST API.

### 1. Install Glances and Required Python Packages

On your Ubuntu server, install Glances and all required Python modules using apt:

```sh
sudo apt update
sudo apt install glances python3-bottle python3-psutil python3-netifaces python3-pip
```

- `glances` - the main monitoring tool
- `python3-bottle`, `python3-psutil`, `python3-netifaces` - required for the Glances API to function correctly

### 2. Start Glances with the Web API

Start Glances with the REST API enabled (default port 61208):

```sh
glances -w
```

You should see output indicating that the web server is running.  
Test access by opening:  
`http://:61208/api/`  
in your browser. You should see a JSON response.

### 3. (Optional) Run Glances as a systemd service

To have Glances start automatically on boot, create a systemd service:

```sh
sudo nano /etc/systemd/system/glances.service
```

Paste the following:

```
[Unit]
Description=Glances monitoring service
After=network.target

[Service]
ExecStart=/usr/bin/glances -w
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```sh
sudo systemctl daemon-reload
sudo systemctl enable glances
sudo systemctl start glances
```

Check status:

```sh
systemctl status glances
```

---

**Note:**  
- Your Pico 2W connects to the Glances API endpoint (default: `http://(server-ip):61208/api/4`).
- No additional Python scripts or Flask apps are required on the server—Glances provides all necessary endpoints out of the box.

---

## Update Settings

- **OTA Update:** In the settings menu, select "Update" and confirm. The device will fetch and apply the latest code using the `ugit` module.
- **Manual Update:** Upload new `.py` files (`main.py`, `conf.py`, `ssd1306.py`, `ugit.py`) via Thonny or mpremote.

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
- [MicroPython for Pico W/2W](https://micropython.org/download/RPI_PICO2_W/)
- [SSD1306 MicroPython Driver](https://github.com/stlehmann/micropython-ssd1306)
- [Thonny IDE](https://thonny.org/)
- [mpremote Tool](https://github.com/micropython/micropython/tree/master/tools/mpremote)
- [Glances Documentation](https://nicolargo.github.io/glances/)
- [psutil Documentation](https://psutil.readthedocs.io/)
- [Bottle Documentation](https://bottlepy.org/docs/dev/)

---

For questions or contributions, please open an issue or pull request on the [GitHub repository](https://github.com/Blankeuuu/Server-Helper).
