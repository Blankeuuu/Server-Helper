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

# ... (wszystkie Twoje dotychczasowe zmienne i funkcje, aż do miejsca gdzie kod się urywał) ...

# Dodane brakujące funkcje:

def eco_mode_active():
    if settings_state.get("eco_mode", 0):
        now = time.ticks_ms()
        return time.ticks_diff(now, last_activity_time) > ECO_TIMEOUT
    return False

def any_button_pressed():
    return (not button_k1.value() or not button_k2.value() or
            not button_k3.value() or not button_k4.value())

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
