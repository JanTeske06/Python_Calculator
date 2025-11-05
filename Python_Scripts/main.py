#main.py
import sys
import os
from pathlib import Path
import json




import config_manager as config_manager
import UI as UI




def check_files_exist():


    UI_file = Path(__file__).resolve().parent / "UI.py"
    MathEngine_file = Path(__file__).resolve().parent / "MathEngine.py"
    ScientificEngine_file = Path(__file__).resolve().parent / "ScientificEngine.py"
    config_man_file = Path(__file__).resolve().parent / "config_manager.py"
    config_file = Path(__file__).resolve().parent.parent / "config.ini"
    icon_file = Path(__file__).resolve().parent.parent / "icons" / "icon.png"


    REQUIRED = [
        UI_file,
        MathEngine_file,
        ScientificEngine_file,
        config_file,
        config_man_file,
        icon_file
    ]

    missing_files = []
    b = 0
    while b < len(REQUIRED):
        current_path = REQUIRED[b]
        if not current_path.exists():
            missing_files.append(current_path.name)
        b+=1

    if missing_files:
        print("Fehler: Folgende Dateien fehlen:")
        for file in missing_files:
            print(f"- {file}")
        sys.exit(1)



def main():
    all_settings = config_manager.load_setting("all")
    print(all_settings)
    UI.main()


if __name__ == "__main__":
    debug = 0  # 1 = activated, 0 = deactivated
    check_files_exist()
    main()