# Main.py
""""" Entry point for the Advanced Python Calculator.

   Responsibilities:
   - Detect run mode (script vs PyInstaller.exe)
   - Verify required files exist in development mode
   - Load configuration and start the Qt GUI
   
"""""
import sys
import PySide6
import PySide6
import pyperclip
import pynput
from pathlib import Path
from Modules import config_manager as config_manager, UI as UI


# Resolve project root depending on run mode (Script or .exe)

if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys._MEIPASS)
else:
    PROJECT_ROOT = Path(__file__).resolve().parent



def check_files_exist():

    """
      Fail fast in development if required files are missing / moved / renamed.

      Rationale:
      - In dev: helpful, early error instead of a vague crash when UI/engine imports fail.
      - In production (.exe): files are embedded by the bundler -> this check is skipped.
    """

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
        print("Error: The following files are missing or in the wrong location:")
        for file_name in missing_files:
            print(f"- {file_name}")
        sys.exit(1)


def main():

    """
    Load configuration and start the GUI.
    - Keep this thin: no business logic here.
    """

    all_settings = config_manager.load_setting_value("all")
    print("Config geladen:", all_settings)

    # Delegate control to the UI layer; the UI owns the event loop.
    UI.main()


if __name__ == "__main__":
    # Two explicit modes aid debugging & packaging clarity.
    is_running_as_exe = getattr(sys, 'frozen', False)

    if not is_running_as_exe:
        print("Developer Mode: Checking file paths...")
        check_files_exist()
    else:
        print("Production mode (.exe) is starting...")
    main()