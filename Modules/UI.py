# Ui.py
from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Qt, QObject, Signal, QTimer
import sys
import json
from pathlib import Path
import threading
from pynput.keyboard import Controller
import pyperclip
import inspect
from . import error as E  # Imports Error.py
from . import config_manager as config_manager
from . import MathEngine as MathEngine


if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys._MEIPASS)
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent




def boolean(value):
    if value == "True":
        return True
    elif value == "False":
        return False
    else:
        return "-1"


def get_line_number():
    return inspect.currentframe().f_back.f_lineno






def background_process(current_text):
    return MathEngine.calculate(current_text)


def is_shift_pressed():
    tastatur_controller = Controller()
    return tastatur_controller.shift_pressed


class Worker(QObject):
    job_finished = Signal(object, str)

    def __init__(self, problem):
        super().__init__()
        self.daten = problem

    def run_Calc(self):

        try:
            ergebnis = MathEngine.calculate(self.daten)
            self.job_finished.emit(ergebnis, self.daten)

        except E.MathError as e:
            self.job_finished.emit(e, self.daten)

        except Exception as e:
            critical_error = E.MathError(
                message=f"Unexpected crash: {e}",
                code="9999",
                equation=self.daten
            )
            self.job_finished.emit(critical_error, self.daten)





class SettingsDialog(QtWidgets.QDialog):
    settings_saved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.widgets = {}



        self.setWindowTitle("Calculator Settings")
        self.resize(300, 200)
        self.setMinimumSize(300, 200)
        self.setMaximumSize(300, 200)

        main_layout = QtWidgets.QVBoxLayout(self)

        self.setting_value_list = config_manager.load_setting_value("all")
        self.setting_description_list = config_manager.load_setting_description("all")

        if len(self.setting_value_list) == len(self.setting_description_list):
            for key_value in self.setting_value_list:
                value = self.setting_value_list[key_value]
                description = self.setting_description_list[key_value]

                if value == True or value == False:
                    checkbox = QtWidgets.QCheckBox(description)
                    checkbox.setChecked(value)
                    main_layout.addWidget(checkbox)
                    self.widgets[key_value] = checkbox

                elif MathEngine.isInt(value):
                    row_h_layout = QtWidgets.QHBoxLayout()
                    main_layout.addLayout(row_h_layout)
                    label = QtWidgets.QLabel(description + " (min. 2):")
                    input_field = QtWidgets.QLineEdit()
                    input_field.setPlaceholderText(str(value))
                    self.input_field_decimal = input_field

                    row_h_layout.addWidget(label)
                    row_h_layout.addWidget(self.input_field_decimal)
                    row_h_layout.setStretch(1, 1)
                    self.widgets[key_value] = self.input_field_decimal

        else:
            print("Error. JSON files desynchronized.")




        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        main_layout.addWidget(button_box)
        main_layout.addStretch(1)

        button_box.accepted.connect(lambda: self.save_settings(self.setting_value_list))

        button_box.rejected.connect(self.reject)
        self.update_darkmode()

    # 2e2e2e
    # 121212

    def save_settings(self, setting_value_list):
        #print(f"Alte Einstellungen: {setting_value_list}")

        try:
            for key_value in self.widgets:
                if key_value not in setting_value_list:
                    continue

                widget = self.widgets[key_value]
                if isinstance(widget, QtWidgets.QCheckBox):

                    new_value = widget.isChecked()

                    if setting_value_list[key_value] != new_value:
                        #print(f"Ändere {key_value} zu {new_value}")
                        setting_value_list[key_value] = new_value

                elif isinstance(widget, QtWidgets.QLineEdit):

                    new_value_str = widget.text().strip()
                    old_value = setting_value_list[key_value]
                    if new_value_str == "":
                        new_value_str = setting_value_list[key_value]
                    try:
                        new_value_int = int(new_value_str)
                        if key_value == "decimal_places" and new_value_int < 2:
                            raise ValueError(f"'{new_value_int}' is too small. Minimum is 2.")
                        if old_value != new_value_int:
                            setting_value_list[key_value] = new_value_int

                    except ValueError as e:
                        print(f"Ungültige Eingabe: {e}")
                        QtWidgets.QMessageBox.critical(self, "Ungültige Eingabe",
                                                       f"Error in input for '{key_value}':\n\n{e}\n\nPlease correct your input.")

                        return
            #print(f"Speichere neue Einstellungen: {setting_value_list}")
            gespeicherte_settings = config_manager.save_setting(setting_value_list)

            if gespeicherte_settings != {}:
                self.settings_saved.emit()
                self.accept()
                self.update_darkmode()
            else:
                QtWidgets.QMessageBox.critical(self, "Error",
                                               "Settings could not be saved (error in config_manager).")

        except Exception as e:
            # Fängt alle anderen Fehler ab (z.B. widget nicht gefunden)
            QtWidgets.QMessageBox.critical(self, "Fatal Error", f"An error has occurred: {e}")




    def update_darkmode(self):
        if self.setting_value_list["darkmode"] == True:
            self.setStyleSheet("""
                        QDialog {background-color: #121212;}
                        QLabel {color: white;}
                        QCheckBox {color: white;}
                        QLineEdit {background-color: #444444;color: white;border: 1px solid #666666;}
                        QDialogButtonBox QPushButton {background-color: #666666;color: white;}""")
        else:
            self.setStyleSheet("")


class CalculatorPrototype(QtWidgets.QWidget):
    display_font_size = 4.8
    shift_is_held = False

    hold_timer = None
    initial_delay = 500
    repeat_interval = 100
    was_held = False
    held_button_value = None


    def __init__(self):
        super().__init__()

        self.setting_value_list = config_manager.load_setting_value("all")

        self.thread_active = False
        self.received_result = False
        self.first_run = True
        self.previous_equation = ""
        self.undo = ["0"]
        self.redo = []
        self.hold_timer = QTimer(self)
        self.hold_timer.timeout.connect(self.handle_hold_tick)
        self.current_text = ""

        icon_path = PROJECT_ROOT / "icons" / "icon.png"
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

        self.current_text = self.display.text()

        if self.received_result == True and not value == "<":
            self.received_result = False
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
        if self.current_text.strip() == "False" or self.current_text.strip() == "True":
            self.current_text = "0"
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

            if self.current_text.endswith("True") or self.current_text.endswith("False"):
                self.current_text = self.current_text[:-5]

            elif self.current_text.endswith("sin(") or self.current_text.endswith("cos(") or self.current_text.endswith(
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

            if self.thread_active:
                print("FEHLER: Eine Berechnung läuft bereits!")  # 4002
                return
            else:
                self.thread_active = True
                self.update_return_button()

            text_to_display = self.display.text()
            self.current_text = text_to_display
            if self.setting_value_list["show_equation"]  == True and self.previous_equation and not "x" in self.current_text:
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
                self.thread_active = False
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
                print(f"The key '{value}' was pressed.")
            elif len(self.redo) > 0:
                self.undo.append(self.redo.pop())
                self.current_text = self.undo[-1]
                self.display.setText(self.current_text)
                print(f"The key '{value}' was pressed.")


        elif value == '📋':
            if self.shift_is_held and self.setting_value_list["shift_to_copy"] == True:

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

                    response = self.setting_value_list["after_paste_enter"]


                    if response == False:
                        self.update_font_size_display()
                        pass
                    elif response == True:
                        if self.thread_active:
                            print("ERROR: A calculation is already running!")  # 4002
                            return
                        else:
                            self.thread_active = True
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

        print(f"The key '{value}' was pressed.")

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
        return_button = self.button_objects.get('⏎')
        if not return_button:
            return
        if self.thread_active == True:
            return_button.setStyleSheet("background-color: #FF0000; color: white; font-weight: bold;")
            return_button.setText("X")
        elif self.thread_active == False:
            return_button.setStyleSheet("background-color: #007bff; color: white; font-weight: bold;")
            return_button.setText("⏎")
        return_button.update()

    def update_darkmode(self):

        if self.setting_value_list["darkmode"] == True:
            for text, button in self.button_objects.items():
                if text != '⏎':
                    button.setStyleSheet("background-color: #121212; color: white; font-weight: bold;")
                    button.update()
                if text == '⏎':
                    return_button = self.button_objects.get('⏎')
                    if not return_button:
                        return
                    if self.thread_active == True:
                        return_button.setStyleSheet("background-color: #FF0000; color: white; font-weight: bold;")
                        return_button.setText("X")
                    elif self.thread_active == False:
                        return_button.setStyleSheet("background-color: #007bff; color: white; font-weight: bold;")
                        return_button.setText("⏎")

            self.setStyleSheet(f"background-color: #121212;")
            self.display.setStyleSheet("background-color: #121212; color: white; font-weight: bold;")

        elif self.setting_value_list["darkmode"] == False:
            for text, button in self.button_objects.items():
                if text != '⏎':
                    button.setStyleSheet("font-weight: normal;")
                    button.update()
                if text == '⏎':
                    return_button = self.button_objects.get('⏎')
                    if not return_button:
                        return
                    if self.thread_active == True:
                        return_button.setStyleSheet("background-color: #FF0000; color: white; font-weight: bold;")
                        return_button.setText("X")
                    elif self.thread_active == False:
                        return_button.setStyleSheet("background-color: #007bff; color: white; font-weight: bold;")
                        return_button.setText("⏎")
            self.setStyleSheet("")
            self.display.setStyleSheet("font-weight: bold;")

    def open_settings(self):
        settings_dialog = SettingsDialog(self)
        settings_dialog.exec()
        self.setting_value_list = config_manager.load_setting_value("all")
        self.update_darkmode()

    def get_message_box_stylesheet(self):
        if self.setting_value_list["darkmode"] == True:
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
        self.received_result = True
        self.thread_active = False

        if equation.endswith('=') and self.setting_value_list["show_equation"] == True:
            equation = equation[:-1]
        print(ergebnis)
        self.update_return_button()

        if isinstance(ergebnis, E.MathError):
            error_obj = ergebnis

            error_box = QtWidgets.QMessageBox(self)
            error_code = error_obj.code
            additional_info = f"Details: {error_obj.message}\nEquation: {error_obj.equation}"

            error_box.setIcon(QtWidgets.QMessageBox.Critical)
            error_box.setWindowTitle("Calculation error")
            error_box.setText(f"Error {error_code}: {E.ERROR_MESSAGES.get(error_code, 'Unknown error')}")
            error_box.setInformativeText(additional_info)
            error_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
            error_box.setStyleSheet(self.get_message_box_stylesheet())
            error_box.exec()

            self.display.setText(equation)
            self.update_font_size_display()
            return


        math_engine_output = ergebnis.strip()
        final_display_text = ""

        show_equation_setting = self.setting_value_list["show_equation"]

        if (math_engine_output == "= True" or math_engine_output == "= False") and show_equation_setting == True:
            math_engine_output = math_engine_output[math_engine_output.index("=")+1:]
            final_display_text = f"{equation} | {math_engine_output}"

        elif(math_engine_output == "= True" or math_engine_output == "= False") and show_equation_setting == False:
            math_engine_output = math_engine_output[math_engine_output.index("=")+1:]
            final_display_text = f"{math_engine_output}"

        elif show_equation_setting == True:
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

        elif show_equation_setting== False:
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


def main():
    app = QtWidgets.QApplication()
    window = CalculatorPrototype()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    app = QtWidgets.QApplication()
    window = CalculatorPrototype()
    window.show()
    sys.exit(app.exec())