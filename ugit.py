import urequests
import machine

GITHUB_RAW_URL = "https://github.com/Blankeuuu/Server-Helper/raw/refs/heads/main/main.py"

def update_main():
    try:
        print("Pobieram nowy main.py z GitHub...")
        r = urequests.get(GITHUB_RAW_URL)
        if r.status_code == 200:
            with open("main.py", "w") as f:
                f.write(r.text)
            print("main.py zaktualizowany, restartuje...")
            r.close()
            machine.reset()
        else:
            print("Błąd pobierania:", r.status_code)
            r.close()
    except Exception as e:
        print("Błąd OTA:", e)
