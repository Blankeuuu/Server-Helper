# PicoServerMonitor

A lightweight, WiFi-enabled hardware monitor for Ubuntu servers using Raspberry Pi Pico W and an SSD1306 OLED display. This project displays real-time server stats (CPU, RAM, temperature, disk usage, network info) and supports configuration via a hardware menu. It is designed for easy deployment and remote monitoring of home or small office servers.

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
   - Edit `conf.py` with your WiFi and server details (see [Configuration](#configuration-confpy)).
   - Upload all `.py` files (including `conf.py`) to the Pico W using Thonny or mpremote.

