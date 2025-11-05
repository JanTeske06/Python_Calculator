# Ui.py
from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Qt
import sys
import subprocess
import os
from pathlib import Path
import time
import configparser
import threading
from PySide6.QtCore import QObject, Signal, QTimer
import json
from pynput.keyboard import Controller
import pyperclip
import error as E  # Imports Error.py
import inspect

received_result = False

config = Path(__file__).resolve().parent.parent / "config.ini"
config_man = str(Path(__file__).resolve().parent / "config_manager.py")
MathEngine = str(Path(__file__).resolve().parent / "MathEngine.py")
python_interpreter = sys.executable

thread_active = False
darkmode = False


def boolean(value):
    if value == "True":
        return True
    elif value == "False":
        return False
    else:
        return "-1"
def get_line_number():
    return inspect.currentframe().f_back.f_lineno

def Calc(problem):
    cmd = [
        python_interpreter,
        MathEngine,
        problem
    ]
    try:
        ergebnis = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
        )
        zurueckgeschickter_string = ergebnis.stdout.strip()
        if ergebnis.returncode != 0 and not zurueckgeschickter_string.startswith("!!ERROR!!"):
            print(f"Ein unerwarteter Prozessfehler ist aufgetreten: {ergebnis.stderr}")
            return f"!!ERROR!! 4700 Unerwarteter Prozessfehler. Code: {ergebnis.returncode}"

        return zurueckgeschickter_string
    except subprocess.SubprocessError as e:
        print(f"Ein Fehler beim Starten des Prozesses ist aufgetreten: {e}")
        return f"!!ERROR!! 4700 Fehler beim Starten des Prozesses: {e}"

def Config_manager(action, section, key_value, new_value):
    cmd = [
        python_interpreter,
        config_man,
        action,
        section,
        key_value,
        new_value
    ]
    try:
        ergebnis = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            check=True)
        zurueckgeschickter_string = ergebnis.stdout.strip()
        zurueckgeschickter_string = ergebnis.stdout.strip()
        return zurueckgeschickter_string
    except subprocess.CalledProcessError as e:
        print(f"Ein Fehler ist aufgetreten: {e}") #4700


def background_process(current_text):
    return Calc(current_text)


def is_shift_pressed():
    tastatur_controller = Controller()
    return tastatur_controller.shift_pressed


class Worker(QObject):
    job_finished = Signal(str, str)
    global thread_active

    def __init__(self, problem):
        super().__init__()
        self.daten = problem
        self.previous = problem

    def run_Calc(self):
        global thread_active
        ergebnis = Calc(self.daten)
        self.job_finished.emit(ergebnis, self.previous)
        thread_active = False


class Config_Signal(QObject):
    all_settings = dict

    def __init__(self):
        global all_settings
        super().__init__()
        all_settings = json.loads(Config_manager("load", "all", "0", "0"))
        print(all_settings)

    def load(self, key_value):
        return all_settings[str(key_value)]

    def save(self, section, key_value, new_value):
        return (Config_manager("save", str(section), str(key_value), str(new_value)))


class SettingsDialog(QtWidgets.QDialog):
    settings_saved = Signal()
    config_handler = Config_Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.previous_is_degree_active = "False"
        self.previous_darkmode_active = "False"
        self.previous_auto_enter_active = "False"
        self.previous_shift_copy_active = "False"
        self.previous_show_equation = "False"
        self.previous_input_text = "2"
        self.previous_fractions = "True"

        self.setWindowTitle("Calculator Settings")
        self.resize(300, 200)
        self.setMinimumSize(300, 200)
        self.setMaximumSize(300, 200)

        main_layout = QtWidgets.QVBoxLayout(self)

        row_h_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(row_h_layout)
        label = QtWidgets.QLabel("Decimal places (min. 2):")
        self.input_field = QtWidgets.QLineEdit()

        row_h_layout.addWidget(label)
        row_h_layout.addWidget(self.input_field)
        row_h_layout.setStretch(1, 1)

        self.is_degree_mode_check = QtWidgets.QCheckBox("Winkel in Grad (°)")
        main_layout.addWidget(self.is_degree_mode_check)

        self.after_paste_enter = QtWidgets.QCheckBox("Nach 📋 automatisch Enter")
        main_layout.addWidget(self.after_paste_enter)

        self.darkmode = QtWidgets.QCheckBox("Darkmode")
        main_layout.addWidget(self.darkmode)

        self.shift_to_copy = QtWidgets.QCheckBox("Shift + 📋 to copy")
        main_layout.addWidget(self.shift_to_copy)

        self.show_equation = QtWidgets.QCheckBox("Show equation")
        main_layout.addWidget(self.show_equation)

        self.show_fractions = QtWidgets.QCheckBox("Show fractions")
        main_layout.addWidget(self.show_fractions)

        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        main_layout.addWidget(button_box)
        main_layout.addStretch(1)

        button_box.accepted.connect(self.save_settings)

        button_box.rejected.connect(self.reject)
        self.load_current_settings()
        self.update_darkmode()

    # 2e2e2e
    # 121212
    def load_current_settings(self):

        def get_setting(key_value):
            response = self.config_handler.load(key_value)

            if response == "-1":
                return None
            return response

        decimals_str = get_setting("decimal_places")
        if decimals_str is not None:
            self.input_field.setPlaceholderText(decimals_str)
        else:
            self.input_field.setPlaceholderText('2')

        is_degree_active_str = get_setting("use_degrees")

        if str(is_degree_active_str) == "True":
            self.is_degree_mode_check.setChecked(True)
        else:
            self.is_degree_mode_check.setChecked(False)

        after_paste_enter_str = get_setting("after_paste_enter")
        if str(after_paste_enter_str) == "True":
            self.after_paste_enter.setChecked(True)
        else:
            self.after_paste_enter.setChecked(False)
        darkmode_active_str = get_setting("darkmode")
        if str(darkmode_active_str) == "True":
            self.darkmode.setChecked(True)

        elif str(darkmode_active_str) == "False":
            self.darkmode.setChecked(False)

        shift_copy_active_str = get_setting("shift_to_copy")
        if str(shift_copy_active_str) == "True":
            self.shift_to_copy.setChecked(True)
        elif str(shift_copy_active_str) == "False":
            self.shift_to_copy.setChecked(False)

        show_equation_str = get_setting("show_equation")
        if str(show_equation_str) == "True":
            self.show_equation.setChecked(True)
        elif str(show_equation_str) == "False":
            self.show_equation.setChecked(False)

        fraction_str = get_setting("fractions")
        if str(fraction_str) == "True":
            self.show_fractions.setChecked(True)
        elif str(fraction_str) == "False":
            self.show_fractions.setChecked(False)

        self.previous_is_degree_active = is_degree_active_str if is_degree_active_str is not None else "False"
        self.previous_darkmode_active = darkmode_active_str if darkmode_active_str is not None else "False"
        self.previous_auto_enter_active = after_paste_enter_str if after_paste_enter_str is not None else "False"
        self.previous_shift_copy_active = shift_copy_active_str if shift_copy_active_str is not None else "False"
        self.previous_show_equation = show_equation_str if show_equation_str is not None else "False"
        self.previous_input_text = decimals_str if decimals_str is not None else "2"
        self.previous_fractions = fraction_str if fraction_str is not None else "2"

    def save_settings(self):

        is_degree_active = str(self.is_degree_mode_check.isChecked())
        darkmode_active = str(self.darkmode.isChecked())
        auto_enter_active = str(self.after_paste_enter.isChecked())
        shift_copy_active = str(self.shift_to_copy.isChecked())
        show_equation_active = str(self.show_equation.isChecked())
        fraction_active = str(self.show_fractions.isChecked())

        input_text = self.input_field.text()
        input_decimals = input_text if input_text else "2"
        default_decimals = self.input_field.placeholderText() if self.input_field.placeholderText() else "2"
        input_decimals = input_text if input_text else default_decimals
        erfolgreich_gespeichert = True

        response = ""
        error_message = ""

        if (is_degree_active != self.previous_is_degree_active):
            response = self.config_handler.save("Scientific_Options", "use_degrees", str(is_degree_active))
            if response != "1" and not response == "":
                erfolgreich_gespeichert = False
                print("Fehler beim speichern")  # 4501
                error_message = error_message + " / Degree mode"
            elif response == "1":
                self.previous_is_degree_active = is_degree_active

        if darkmode_active != self.previous_darkmode_active:
            response = self.config_handler.save("UI", "darkmode", str(darkmode_active))
            if response != "1" and not response == "":
                erfolgreich_gespeichert = False
                print("Fehler beim speichern")  # 4501
                error_message = error_message + " / Darkmode"
            elif response == "1":
                self.previous_darkmode_active = darkmode_active

        if auto_enter_active != self.previous_auto_enter_active:
            response = self.config_handler.save("UI", "after_paste_enter", str(auto_enter_active))
            if response != "1" and not response == "":
                erfolgreich_gespeichert = False
                print("Fehler beim speichern")  # 4501
                error_message = error_message + " / Enter after Paste"
            elif response == "1":
                self.previous_auto_enter_active = auto_enter_active

        if shift_copy_active != self.previous_shift_copy_active:
            response = self.config_handler.save("UI", "shift_to_copy", str(shift_copy_active))
            if response != "1" and not response == "":
                erfolgreich_gespeichert = False
                print("Fehler beim speichern")  # 4501
                error_message = error_message + " / Shift + Copy"
            elif response == "1":
                self.previous_shift_copy_active = shift_copy_active

        if show_equation_active != self.previous_show_equation:
            response = self.config_handler.save("UI", "show_equation", str(show_equation_active))
            if response != "1" and not response == "":
                erfolgreich_gespeichert = False
                print("Fehler beim speichern")  # 4501
                error_message = error_message + " / show_equation"
            elif response == "1":
                self.previous_show_equation = show_equation_active

        if fraction_active != self.previous_fractions:
            response = self.config_handler.save("UI", "fractions", str(fraction_active))
            if response != "1" and not response == "":
                erfolgreich_gespeichert = False
                print("Fehler beim speichern")  # 4501
                error_message = error_message + " / fractions"
            elif response == "1":
                self.previous_fractions = fraction_active


        if input_decimals != self.previous_input_text:
            response = self.config_handler.save("Math_Options", "decimal_places", str(input_decimals))

            if response != "1" and not response == "":
                erfolgreich_gespeichert = False
                error_message = error_message + " / Decimals"  # 4501
            elif response == "1":
                self.previous_input_text = input_decimals

        if erfolgreich_gespeichert or response == "":
            self.settings_saved.emit()
            self.accept()
            Config_Signal()
            self.load_current_settings()
        else:
            QtWidgets.QMessageBox.critical(self, "Fehler",
                                           "Nicht alle Einstellungen konnten gespeichert werden." + error_message)  # 4501

    def update_darkmode(self):
        if self.config_handler.load("darkmode") == "True":
            self.setStyleSheet("""
                        QDialog {background-color: #121212;}
                        QLabel {color: white;}
                        QCheckBox {color: white;}
                        QLineEdit {background-color: #444444;color: white;border: 1px solid #666666;}
                        QDialogButtonBox QPushButton {background-color: #666666;color: white;}""")
        else:
            self.setStyleSheet("")


class CalculatorPrototype(QtWidgets.QWidget):
    config_handler = Config_Signal()
    display_font_size = 4.8
    first_run = True
    shift_is_held = False

    hold_timer = None
    initial_delay = 500
    repeat_interval = 100
    was_held = False
    held_button_value = None


    def __init__(self):
        super().__init__()
        self.previous_equation = ""
        self.undo = ["0"]
        self.redo = []
        self.hold_timer = QTimer(self)
        self.hold_timer.timeout.connect(self.handle_hold_tick)
        self.current_text = ""

        icon_path = Path(__file__).resolve().parent.parent / "icons" / "icon.png"
        app_icon = QtGui.QIcon(str(icon_path))

        self.setWindowIcon(app_icon)

        self.button_objects = {}
        self.setWindowTitle("Calculator")
        self.resize(200, 450)

        main_v_layout = QtWidgets.QVBoxLayout(self)

        expanding_policy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        )
        # Display (Stretch 1)
        self.display = QtWidgets.QLineEdit("0")
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.display.setReadOnly(True)
        font = self.display.font()
        font.setPointSize(46)
        self.display.setFont(font)

        self.display.setSizePolicy(expanding_policy)
        main_v_layout.addWidget(self.display, 1)

        button_container = QtWidgets.QWidget()
        main_v_layout.addWidget(button_container, 3)

        button_grid = QtWidgets.QGridLayout(button_container)

        button_grid.setSpacing(0)
        button_grid.setContentsMargins(0, 0, 0, 0)

        for i in range(7):  # vertikal
            button_grid.setRowStretch(i, 1)
        for j in range(5):  # horizental
            button_grid.setColumnStretch(j, 1)

        self.buttons = [
            ('⚙️', 0, 0), ('📋', 0, 1), ('↷', 0, 2), ('↶', 0, 3), ('<', 0, 4),

            ('π', 1, 0), ('e^(', 1, 1), ('x', 1, 2), ('√(', 1, 3), ('/', 1, 4),

            ('sin(', 2, 0), ('(', 2, 1), (')', 2, 2), ('^(', 2, 3), ('*', 2, 4),

            ('cos(', 3, 0), ('7', 3, 1), ('8', 3, 2), ('9', 3, 3), ('-', 3, 4),

            ('tan(', 4, 0), ('4', 4, 1), ('5', 4, 2), ('6', 4, 3), ('+', 4, 4),

            ('log(', 5, 0), ('1', 5, 1), ('2', 5, 2), ('3', 5, 3), ('=', 5, 4),

            ('C', 6, 0), (',', 6, 1), ('0', 6, 2), ('.', 6, 3), ('⏎', 6, 4)
        ]

        HOLD_BUTTONS = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '↶','↷','<']

        for self.text, self.row, self.col in self.buttons:
            self.button = QtWidgets.QPushButton(self.text)
            self.button.setSizePolicy(expanding_policy)

            if self.text == '⏎':
                self.button.setStyleSheet("background-color: #007bff; color: white; font-weight: bold;")
            elif self.text == '⚙️':
                self.button.clicked.connect(self.open_settings)

            if self.text in HOLD_BUTTONS:
                self.button.pressed.connect(lambda checked=False, val=self.text: self.handle_button_pressed_hold(val))
                self.button.released.connect(self.handle_button_released_hold)
                self.button.clicked.connect(lambda checked=False, val=self.text: self.handle_button_clicked_hold(val))
            else:
                self.button.clicked.connect(lambda checked=False, val=self.text: self.handle_button_press(val))

            button_grid.addWidget(self.button, self.row, self.col)
            self.button_objects[self.text] = self.button
            self.update_darkmode()


    def handle_button_pressed_hold(self, value):
        self.was_held = False
        self.held_button_value = value
        self.hold_timer.setInterval(self.initial_delay)
        self.hold_timer.start()

    def handle_button_released_hold(self):
        self.hold_timer.stop()
        self.held_button_value = None

    def handle_button_clicked_hold(self, value):
        if not self.was_held:
            self.handle_button_press(value)

    def handle_hold_tick(self):

        self.was_held = True
        if self.hold_timer.interval() == self.initial_delay:
            self.hold_timer.setInterval(self.repeat_interval)

        if self.held_button_value:
            self.handle_button_press(self.held_button_value)


    def resizeEvent(self, event):
        super().resizeEvent(event)

        self.setMinimumSize(400, 540)
        if self.first_run == False:
            for button_text, button_instance in self.button_objects.items():
                experiment = (button_instance.height() / 8) * 2
                if experiment <= 12:
                    experiment = 12
                font = button_instance.font()
                font.setPointSize((experiment))
                button_instance.setFont(font)


        elif self.first_run == True:
            for button_text, button_instance in self.button_objects.items():
                font = button_instance.font()
                font.setPointSize((12))
                button_instance.setFont(font)
                self.first_run = False
        self.update_font_size_display()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Shift:
            self.shift_is_held = True
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Shift:
            self.shift_is_held = False
        super().keyReleaseEvent(event)

    def handle_button_press(self, value):
        global first_run
        global mein_thread
        global received_result

        self.current_text = self.display.text()

        if received_result == True and not value == "<":
            received_result = False
            ungefaehr_zeichen = "\u2248"
            marker_to_find = ""

            if "|" in self.current_text:
                marker_to_find = "|"

            elif "=" in self.current_text:
                marker_to_find = "="

            elif 'x' in self.current_text:
                marker_to_find = ""

            elif ungefaehr_zeichen in self.current_text:
                marker_to_find = ungefaehr_zeichen

            if marker_to_find != "":
                try:
                    if marker_to_find != "|":
                        marker_index = self.current_text.index(marker_to_find)
                        start_index = marker_index + 1
                        temp_new_text = self.current_text[start_index:]
                        if temp_new_text.startswith(' '):
                            temp_new_text = temp_new_text[1:]
                        self.current_text = temp_new_text
                    elif marker_to_find == "|":
                        marker_index = self.current_text.index(marker_to_find)
                        start_index = marker_index -1
                        temp_new_text = self.current_text[:start_index]
                        if temp_new_text.startswith(' '):
                            temp_new_text = temp_new_text[:1]
                        self.current_text = temp_new_text

                except ValueError:
                    pass

        if value == 'C':
            self.current_text = "0"
            self.display.setText(self.current_text)

        elif (value == '<'):

            if len(self.current_text) <= 0 or self.current_text == "0":
                self.current_text = "0"
                self.display.setText(self.current_text)
                return

            elif len(self.undo) > 1:
                print(self.current_text)
                print(str(get_line_number()))
                if self.undo[-2] == '⏎':
                    print(self.undo)
                    print(str(get_line_number()))
                    #self.current_text = "3=3 |  True"
                    if "x" in self.current_text:
                        if "|" in self.current_text:
                            print(str(get_line_number()))
                            self.current_text = self.current_text[:self.current_text.index("|") -1]
                        elif "=" in self.current_text:
                            print(str(get_line_number()))
                            self.current_text = self.current_text[self.current_text.index("=") + 1:]
                        elif "≈" in self.current_text:
                            print(str(get_line_number()))
                            self.current_text = self.current_text[self.current_text.index("≈") + 1:]


                    elif "=" in self.current_text and (not "True" in self.current_text and not "False" in self.current_text):
                        print(str(get_line_number()))
                        self.current_text = self.current_text[self.current_text.index("=") + 1:]
                    elif "≈" in self.current_text and (not "True" in self.current_text and not "False" in self.current_text):
                        print(str(get_line_number()))
                        self.current_text = self.current_text[self.current_text.index("≈") + 1:]


                    elif "=" in self.current_text and ("True" in self.current_text or "False" in self.current_text):
                        print(str(get_line_number()))
                        self.current_text = self.current_text[:self.current_text.index("|") -1]

                    self.current_text = self.current_text + "0"


            if self.current_text.endswith("sin(") or self.current_text.endswith("cos(") or self.current_text.endswith(
                    "tan(") or self.current_text.endswith("log("):
                self.current_text = self.current_text[:-4]

            elif self.current_text.endswith("e^(") or self.current_text.endswith("sin") or self.current_text.endswith(
                    "cos") or self.current_text.endswith("tan") or self.current_text.endswith("log"):
                self.current_text = self.current_text[:-3]

            elif self.current_text.endswith("√(") or self.current_text.endswith("^(") or self.current_text.endswith("e^"):
                self.current_text = self.current_text[:-2]


            else:
                print(self.undo)
                print(str(get_line_number()))
                self.current_text = self.current_text[:-1]
            self.display.setText(self.current_text if self.current_text else "0")

        elif (value == '⚙️'):
            return

        elif value == '⏎':
            print(str(get_line_number()) + " " + self.current_text)
            global thread_active

            if thread_active:
                print("FEHLER: Eine Berechnung läuft bereits!")  # 4002
                return
            else:
                thread_active = True
                self.update_return_button()

            text_to_display = self.display.text()
            self.current_text = text_to_display

            if self.config_handler.load(
                    "show_equation") == "True" and self.previous_equation and not "x" in self.current_text:
                is_original_equation = (self.current_text == self.previous_equation)

                if not is_original_equation and not "x" in self.current_text:

                    value_part = None

                    if "|" in text_to_display:
                        value_part = text_to_display.split("|")[-1].strip()
                    elif "=" in text_to_display:
                        value_part = text_to_display.split("=")[-1].strip()
                    elif "\u2248" in text_to_display:
                        value_part = text_to_display.split("\u2248")[-1].strip()

                    if value_part:
                        self.current_text = f"{value_part}={value_part}"
            else:
                if "|" in self.current_text:
                    self.current_text = self.current_text.replace("|", "")

            self.display.setText("...")
            return_button = self.button_objects['⏎']
            QtWidgets.QApplication.processEvents()

            if not self.current_text.strip():
                print("FEHLER: Leerer String an MathEngine gesendet.")
                thread_active = False
                self.update_return_button()
                self.display.setText(text_to_display)
                return
            worker_instanz = Worker(self.current_text)
            mein_thread = threading.Thread(target=worker_instanz.run_Calc)
            mein_thread.start()
            worker_instanz.job_finished.connect(self.Calc_result)
            return




        elif value == '↶':
            if len(self.undo) >= 2 and self.undo[-2] == '⏎':
                self.redo.append(self.undo.pop())
                self.redo.append(self.undo.pop())
                self.current_text = self.undo[-1]
                self.display.setText(self.current_text)
                print(f"Es wurde die Taste '{value}' gedrückt.")

            elif len(self.undo) > 1:
                self.redo.append(self.undo.pop())
                self.current_text = self.undo[-1]
                self.display.setText(self.current_text)
                print(f"Es wurde die Taste '{value}' gedrückt.")
                print(self.undo)


        elif value == '↷':
            print("redo1: " + str(self.redo))
            if len(self.redo) >= 2 and self.redo[-1] == '⏎':
                print("redo2: " + str(self.redo))
                self.undo.append(self.redo.pop())
                self.undo.append(self.redo.pop())
                self.current_text = self.undo[-1]
                self.display.setText(self.current_text)
                print(f"Es wurde die Taste '{value}' gedrückt.")
            elif len(self.redo) > 0:
                self.undo.append(self.redo.pop())
                self.current_text = self.undo[-1]
                self.display.setText(self.current_text)
                print(f"Es wurde die Taste '{value}' gedrückt.")


        elif value == '📋':
            if self.shift_is_held and self.config_handler.load("shift_to_copy") == "True":

                if '=' in self.current_text and not 'x' in self.current_text:

                    equal = self.current_text.index("=")
                    copy_text = self.current_text[:equal] + self.current_text[equal + 1:]
                    pyperclip.copy(copy_text)
                else:

                    pyperclip.copy(self.current_text)

            else:

                clipboard = QtWidgets.QApplication.clipboard()
                clipboard_text = clipboard.text()
                if "x" in self.current_text or ("True" or "False") in self.current_text:
                    if "|" in self.current_text:
                        print(str(get_line_number()))
                        self.current_text = self.current_text[:self.current_text.index("|") - 1]

                if clipboard_text:
                    if self.current_text == "0":
                        self.current_text = clipboard_text
                    else:
                        self.current_text = self.current_text + clipboard_text




                    self.display.setText(self.current_text)
                    self.undo.append(self.current_text)
                    self.redo.clear()

                    response = self.config_handler.load("after_paste_enter")

                    if response == "False":
                        self.update_font_size_display()
                        pass
                    elif response == "True":
                        if thread_active:
                            print("FEHLER: Eine Berechnung läuft bereits!")  # 4002
                            return
                        else:
                            thread_active = True
                            self.update_return_button()
                            self.display.setText("...")
                            worker_instanz = Worker(self.current_text)

                            mein_thread = threading.Thread(target=worker_instanz.run_Calc)
                            mein_thread.start()
                            worker_instanz.job_finished.connect(self.Calc_result)

                return


        else:
            if self.current_text == "0" and value != ".":
                self.current_text = ""
            self.current_text += str(value)
            self.display.setText(self.current_text)

        self.update_font_size_display()

        if value != '↶' and value != '↷' and value != '📋':
            self.undo.append(self.current_text)
            self.redo.clear()

        print(f"Es wurde die Taste '{value}' gedrückt.")

    def update_font_size_display(self):
        self.current_text = self.display.text()
        MAX_FONT_SIZE = 60
        MIN_FONT_SIZE = 10

        self.display.setText(self.current_text)

        font = self.display.font()
        aktuelle_groesse = font.pointSize()
        fm = QtGui.QFontMetrics(font)

        r_margin = self.display.textMargins().right()
        l_margin = self.display.textMargins().left()
        padding = l_margin + r_margin + 5
        verfuegbare_breite = self.display.width() - padding

        text_breite = fm.horizontalAdvance(self.current_text)
        if len(self.current_text) >= 55:
            aktuelle_groesse = MIN_FONT_SIZE

        else:
            while text_breite > verfuegbare_breite and aktuelle_groesse >= MIN_FONT_SIZE:
                aktuelle_groesse -= 0.01
                font.setPointSize(aktuelle_groesse)
                fm = QtGui.QFontMetrics(font)
                text_breite = fm.horizontalAdvance(self.current_text)

            temp_size = aktuelle_groesse

            while temp_size <= MAX_FONT_SIZE:
                temp_size += 0.01
                font.setPointSize(temp_size)
                fm_temp = QtGui.QFontMetrics(font)
                text_breite_temp = fm_temp.horizontalAdvance(self.current_text)
                if text_breite_temp <= verfuegbare_breite:
                    aktuelle_groesse = temp_size
                else:
                    temp_size -= 0.01
                    break
        font.setPointSize(aktuelle_groesse)
        self.display.setFont(font)

    def update_return_button(self):
        global thread_active
        return_button = self.button_objects.get('⏎')
        if not return_button:
            return
        if thread_active == True:
            return_button.setStyleSheet("background-color: #FF0000; color: white; font-weight: bold;")
            return_button.setText("X")
        elif thread_active == False:
            return_button.setStyleSheet("background-color: #007bff; color: white; font-weight: bold;")
            return_button.setText("⏎")
        return_button.update()

    def update_darkmode(self):
        global darkmode
        global thread_active

        if self.config_handler.load("darkmode") == "True":
            for text, button in self.button_objects.items():
                if text != '⏎':
                    button.setStyleSheet("background-color: #121212; color: white; font-weight: bold;")
                    button.update()
                if text == '⏎':
                    return_button = self.button_objects.get('⏎')
                    if not return_button:
                        return
                    if thread_active == True:
                        return_button.setStyleSheet("background-color: #FF0000; color: white; font-weight: bold;")
                        return_button.setText("X")
                    elif thread_active == False:
                        return_button.setStyleSheet("background-color: #007bff; color: white; font-weight: bold;")
                        return_button.setText("⏎")

            self.setStyleSheet(f"background-color: #121212;")
            self.display.setStyleSheet("background-color: #121212; color: white; font-weight: bold;")

        elif self.config_handler.load("darkmode") == "False":
            for text, button in self.button_objects.items():
                if text != '⏎':
                    button.setStyleSheet("font-weight: normal;")
                    button.update()
                if text == '⏎':
                    return_button = self.button_objects.get('⏎')
                    if not return_button:
                        return
                    if thread_active == True:
                        return_button.setStyleSheet("background-color: #FF0000; color: white; font-weight: bold;")
                        return_button.setText("X")
                    elif thread_active == False:
                        return_button.setStyleSheet("background-color: #007bff; color: white; font-weight: bold;")
                        return_button.setText("⏎")
            self.setStyleSheet("")
            self.display.setStyleSheet("font-weight: bold;")

    def open_settings(self):
        settings_dialog = SettingsDialog(self)
        settings_dialog.exec()
        self.update_darkmode()

    def get_message_box_stylesheet(self):
        if self.config_handler.load("darkmode") == "True":
            return """
                QMessageBox { 
                    background-color: #121212; 
                    color: white; 
                }
                QLabel { 
                    color: white; 
                }
                QPushButton {
                    background-color: #2e2e2e;
                    color: white;
                    border: 1px solid #444444;
                    padding: 5px 15px;
                }
                QPushButton:hover {
                    background-color: #444444;
                }
            """
        else:
            return ""

    def Calc_result(self, ergebnis, equation):
        global received_result
        received_result = True

        if equation.endswith('=') and self.config_handler.load("show_equation") == "True":
            equation = equation[:-1]
        print(ergebnis)
        self.update_return_button()
        if ergebnis.startswith("!!ERROR!!"):
            error_message = ergebnis.replace("!!ERROR!! ", "")
            error_box = QtWidgets.QMessageBox(self)
            error_code = ergebnis[10:14]
            additional_info = ergebnis[14:]
            error_box.setIcon(QtWidgets.QMessageBox.Critical)
            error_box.setWindowTitle("Berechnungsfehler")

            error_box.setText(f"Error " + error_code + ": " + E.ERROR_MESSAGES.get(error_code, "Unbekannter Fehler"))
            error_box.setInformativeText(additional_info)

            error_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
            error_box.setStyleSheet(self.get_message_box_stylesheet())
            error_box.exec()
            self.display.setText(equation)
            self.update_font_size_display()
            return
        math_engine_output = ergebnis.strip()
        final_display_text = ""

        show_equation_setting = self.config_handler.load("show_equation")

        if (math_engine_output == "= True" or math_engine_output == "= False") and show_equation_setting == "True":
            math_engine_output = math_engine_output[math_engine_output.index("=")+1:]
            final_display_text = f"{equation} | {math_engine_output}"

        elif(math_engine_output == "= True" or math_engine_output == "= False") and show_equation_setting == "False":
            math_engine_output = math_engine_output[math_engine_output.index("=")+1:]
            final_display_text = f"{math_engine_output}"

        elif show_equation_setting == "True":
            is_solver_result = math_engine_output.startswith("x =") or math_engine_output.startswith("x \u2248")

            if is_solver_result:
                final_display_text = f"{equation} | {math_engine_output}"

            else:
                clean_result = math_engine_output

                if clean_result.startswith("=") or clean_result.startswith("\u2248"):
                    clean_result = clean_result[1:].strip()

                if math_engine_output.startswith("\u2248"):
                    final_display_text = f"{equation} {math_engine_output}"
                else:
                    final_display_text = f"{equation} = {clean_result}"

        elif show_equation_setting== "False":
            print("x")
            is_solver_result = math_engine_output.startswith("x =") or math_engine_output.startswith("x \u2248")

            if is_solver_result:
                final_display_text = f"{equation} | {math_engine_output}"
            else:
                clean_result = math_engine_output


                if math_engine_output.startswith("\u2248"):
                    final_display_text = f"{clean_result}"
                else:
                    final_display_text = f"{clean_result}"

        else:
            final_display_text = math_engine_output
        self.display.setText(final_display_text)
        if final_display_text != self.undo[-1]:
            self.undo.append('⏎')
            self.undo.append(final_display_text)
            self.redo.clear()

        self.update_font_size_display()

        print("undo: " + str(self.undo))
        print("redo: " + str(self.redo))
        self.previous_equation = equation


if __name__ == "__main__":
    Config_Signal()
    app = QtWidgets.QApplication(sys.argv)
    window = CalculatorPrototype()
    window.show()
    sys.exit(app.exec())