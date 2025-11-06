# config_manager.py
import sys
import configparser
from pathlib import Path
import json

config_json = Path(__file__).resolve().parent.parent / "config.json"
ui_strings = Path(__file__).resolve().parent.parent / "ui_strings.json"



def load_setting_value(key_value):
    try:
        with open(config_json, 'r', encoding= 'utf-8') as f:
            settings_dict = json.load(f)

    except (FileNotFoundError, json.JSONDecodeError):
        return {}


    if key_value == "all":
        return settings_dict

    else:
        return settings_dict.get(key_value, 0)


def load_setting_description(key_value):
    try:
        with open(ui_strings, 'r', encoding= 'utf-8') as f:
            settings_dict = json.load(f)

    except (FileNotFoundError, json.JSONDecodeError):
        return {}


    if key_value == "all":
        return settings_dict

    else:
        return settings_dict.get(key_value, 0)




def save_setting(settings_dict):
    try:
        with open (config_json, 'w', encoding= 'utf-8') as f:
            json.dump(settings_dict, f, indent=4)
            return settings_dict

    except (FileNotFoundError, json.JSONDecodeError):
        return{}





if __name__ == "__main__":
    print(load_setting_value("after_paste_enter"))


    all_settings = load_setting_value("all")
    all_settings["darkmode"] = True
    save_setting(all_settings)
    print(load_setting_value("darkmode"))

    print(load_setting_value("darkmode"))

    all_settings = load_setting_value("all")
    all_settings["darkmode"] = False
    save_setting(all_settings)
    print(load_setting_value("darkmode"))
    print(load_setting_value("all"))
