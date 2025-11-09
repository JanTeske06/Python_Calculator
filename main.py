import sys
import PySide6
import PySide6
import pyperclip
import pynput
from pathlib import Path
from Modules import config_manager as config_manager, UI as UI

if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys._MEIPASS)
else:
    # WIR LAUFEN ALS .PY (normales Skript)
    PROJECT_ROOT = Path(__file__).resolve().parent



def check_files_exist():
    modules_dir = PROJECT_ROOT / "Modules"
    UI_file = modules_dir / "UI.py"
    MathEngine_file = modules_dir / "MathEngine.py"
    ScientificEngine_file = modules_dir / "ScientificEngine.py"
    config_man_file = modules_dir / "config_manager.py"


    config_file_values = PROJECT_ROOT / "config.json"
    ui_strings = PROJECT_ROOT / "ui_strings.json"


    icon_file = PROJECT_ROOT / "icons" / "icon.png"

    REQUIRED = [
        UI_file,
        MathEngine_file,
        ScientificEngine_file,
        config_file_values,
        ui_strings,
        config_man_file,
        icon_file
    ]

    missing_files = []
    for file_path in REQUIRED:
        if not file_path.exists():
            missing_files.append(file_path.name)

    if missing_files:
        print("Fehler: Folgende Dateien fehlen oder sind am falschen Ort:")
        for file_name in missing_files:
            print(f"- {file_name}")
        sys.exit(1)


def main():
    all_settings = config_manager.load_setting_value("all")
    print("Config geladen:", all_settings)
    UI.main()


if __name__ == "__main__":
    check_files_exist()
    main()