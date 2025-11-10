# UI.py
""""PySide6 user interface for the Advanced Python Calculator.

Structure
---------
- Calculator UI: main window with display and button grid
- Settings UI: modal dialog for user preferences

Responsibilities (Calculator)
-----------------------------
- Build window, display, layout and buttons
- Handle user input and maintain undo/redo
- Dispatch expression/equation to MathEngine in a worker thread
- Render results and show MathEngine errors as dialogs
- Keep the display readable (auto-resizing font, dark/light mode)
- Clipboard integration and optional auto-evaluate after paste


Responsibilities (Settings)
---------------------------

- Load Current Settings and Settings Descriptions via Config_Manager
- Validate user input (e.g. minimum decimal places)
- Save atomically and apply theme changes immediately


Threading Note
--------------
Long-running evaluation is executed off the UI thread in Worker(QObject), so the UI can still handle events like resizing.
Results (or errors) are emitted via a Qt signal and handled back in the UI.
"""""

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
from collections import Counter
from . import error as E  # Imports Error.py as a module
from . import config_manager as config_manager  # Imports config_manager.py as a module
from . import MathEngine as MathEngine  # Imports MathEngine.py as a module

# Resolve project root depending on run mode (Script or .exe)
if getattr(sys, 'frozen', False):
    # We are running in a PyInstaller bundle (.exe)
    PROJECT_ROOT = Path(sys._MEIPASS)
else:
    # We are running in a normal Python environment (.py)
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

# New: supported augmented-assignment operator tokens (UI feature flag in settings controls behavior)
augmented_assignment = ["+=", "*=", "/=", "-="]


def boolean(value):
    """""

    Simple helper function to check whether the value is a boolean or not.

    Returns True or False, depending on the value of the boolean, or -1, if its neither.

    """""

    if value == "True":
        return True
    elif value == "False":
        return False
    else:
        return "-1"


def get_line_number():
    # Name is self explanatory, used alot in Development and Debugging
    return inspect.currentframe().f_back.f_lineno


def is_shift_pressed():
    """""

    Small and simple check, whether shift is pressed or not.
    Used for the "shift to copy" setting.

    """""

    tastatur_controller = Controller()
    return tastatur_controller.shift_pressed


class Worker(QObject):
    """""

    This Class is always a seperat thread, responsible for transmitting the problem to MathEngine.py
    and emits a Signal when the calculations are done / failed back to the Calculator UI for processing

    """""

    job_finished = Signal(object, str)

    def __init__(self, problem):
        super().__init__()
        self.data = problem  # Renamed from 'self.daten' for clarity

    def run_Calc(self):

        try:
            # --- 1. Start Calculation ---
            # This is the call to the "engine". It runs in the separate thread.
            result = MathEngine.calculate(self.data)

            # --- 2. Send Success Signal ---
            # Emits the result back to the UI thread (connected to Calc_result)
            self.job_finished.emit(result, self.data)

        except E.MathError as e:
            # --- 3. Send Math Error Signal ---
            # Found a known, handled error (e.g., "Division by zero")
            self.job_finished.emit(e, self.data)

        except Exception as e:
            # --- 4. Send Critical Error Signal ---
            # Found an unexpected crash we didn't plan for (e.g., a bug in the code)
            critical_error = E.MathError(
                message=f"Unexpected crash: {e}",
                code="9999",
                equation=self.data  # Fixed typo from self.daten
            )
            self.job_finished.emit(critical_error, self.data)


class SettingsDialog(QtWidgets.QDialog):
    """""

    This class is responsible for managing the settings window, saving the new settings and opening and error
    message if something went wrong.

    All of the Settings can be seperated into two categories:
    1. Checkboxes   (Managed with True or False)
    2. Input Fields (Managed as a String)

    """""

    settings_saved = Signal()  # Signal to tell the main window to update

    def __init__(self, parent=None):
        """""

        Builds the UI for the Settings window and saves the Settings, if OK was pressed,
        or ignores the changes if Cancel was pressed. To make sure all of the Settings are up to date,
        it calls config_manager for the current states of the settings and the descriptions

        """""

        super().__init__(parent)
        self.widgets = {}  # Dictionary, in which all of the Widgets (Setting options) are saved and stored.

        # --- 1. Window Setup ---
        self.setWindowTitle("Calculator Settings")
        self.resize(300, 200)
        self.setMinimumSize(300, 200)
        self.setMaximumSize(300, 200)

        main_layout = QtWidgets.QVBoxLayout(self)

        # --- 2. Load Settings ---
        # Loads the Current Settings and Descriptions for the window,
        # so all the settings states and descriptions are displayed correctly
        self.setting_value_list = config_manager.load_setting_value("all")
        self.setting_description_list = config_manager.load_setting_description("all")

        # --- 3. Build Widgets ---
        # Checks whether the dictionaries for the descriptions and values are equally long,
        # to make sure its displayed correctly
        if len(self.setting_value_list) == len(self.setting_description_list):

            # The following for loop identifies the value of the Setting,
            # to correctly create a checkbox or input field.

            for key_value in self.setting_value_list:
                value = self.setting_value_list[key_value]
                description = self.setting_description_list[key_value]

                # --- 3a. Checkbox Builder (for Boolean settings) ---
                if value == True or value == False:
                    checkbox = QtWidgets.QCheckBox(description)
                    checkbox.setChecked(value)
                    main_layout.addWidget(checkbox)
                    self.widgets[key_value] = checkbox  # Store widget for later saving

                # --- 3b. Input Field Builder (for Integer settings) ---
                elif MathEngine.isInt(value):
                    row_h_layout = QtWidgets.QHBoxLayout()
                    main_layout.addLayout(row_h_layout)
                    label = QtWidgets.QLabel(description + " (min. 2):")
                    input_field = QtWidgets.QLineEdit()
                    input_field.setPlaceholderText(str(value))  # Show current value as placeholder
                    self.input_field_decimal = input_field

                    row_h_layout.addWidget(label)
                    row_h_layout.addWidget(self.input_field_decimal)
                    row_h_layout.setStretch(1, 1)  # Make input field expand
                    self.widgets[key_value] = self.input_field_decimal  # Store widget for later saving

        else:
            print("Error. JSON files desynchronized.")

        # --- 4. OK / Cancel Buttons ---
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        main_layout.addWidget(button_box)
        main_layout.addStretch(1)

        # Connects itself to the save_settings function and waits for a response, if the OK button was pressed
        button_box.accepted.connect(lambda: self.save_settings(self.setting_value_list))

        # If the cancel button was pressed, it doesnt do anything
        button_box.rejected.connect(self.reject)

        # Apply darkmode on initial load
        self.update_darkmode()

    def save_settings(self, setting_value_list):
        # --- 1. Save Settings Logic ---
        try:
            # Iterate over all widgets we created (Checkboxes, Input Fields)
            for key_value in self.widgets:
                if key_value not in setting_value_list:
                    continue  # Skip if widget key isn't in settings

                widget = self.widgets[key_value]

                # --- 2. Handle Checkboxes ---
                if isinstance(widget, QtWidgets.QCheckBox):

                    new_value = widget.isChecked()

                    if setting_value_list[key_value] != new_value:
                        # print(f"Changing {key_value} to {new_value}")
                        setting_value_list[key_value] = new_value

                # --- 3. Handle Input Fields (like 'decimal_places') ---
                elif isinstance(widget, QtWidgets.QLineEdit):

                    new_value_str = widget.text().strip()
                    old_value = setting_value_list[key_value]

                    # If user left it blank, keep the old value
                    if new_value_str == "":
                        new_value_str = setting_value_list[key_value]

                    try:
                        # --- 4. Validation ---
                        new_value_int = int(new_value_str)
                        # Specific rule for decimal_places
                        if key_value == "decimal_places" and new_value_int < 2:
                            raise ValueError(f"'{new_value_int}' is too small. Minimum is 2.")

                        # Only update if the value actually changed
                        if old_value != new_value_int:
                            setting_value_list[key_value] = new_value_int

                    except ValueError as e:
                        # --- 5. Input Validation Error ---
                        # Show an error box and STOP the save process
                        print(f"Invalid Input: {e}")
                        QtWidgets.QMessageBox.critical(self, "Invalid Input:",
                                                       f"Error in input for '{key_value}':\n\n{e}\n\nPlease correct your input.")

                        return  # Stop saving!

            # --- 6. Write to File ---
            # If all validations passed, save the updated dictionary to config.json
            gespeicherte_settings = config_manager.save_setting(setting_value_list)

            if gespeicherte_settings != {}:
                self.settings_saved.emit()  # Tell the main window to update
                self.accept()  # Close the settings dialog
                self.update_darkmode()  # Apply theme changes
            else:
                QtWidgets.QMessageBox.critical(self, "Error",
                                               "Settings could not be saved (error in config_manager).")

        except Exception as e:
            # Catch-all for any other unexpected error
            QtWidgets.QMessageBox.critical(self, "Fatal Error", f"An error has occurred: {e}")

    def update_darkmode(self):
        # Applies the darkmode stylesheet if the setting is True
        if self.setting_value_list["darkmode"] == True:
            self.setStyleSheet("""
                        QDialog {background-color: #121212;}
                        QLabel {color: white;}
                        QCheckBox {color: white;}
                        QLineEdit {background-color: #444444;color: white;border: 1px solid #666666;}
                        QDialogButtonBox QPushButton {background-color: #666666;color: white;}""")
        else:
            self.setStyleSheet("")  # Revert to default stylesheet


class CalculatorPrototype(QtWidgets.QWidget):
    # --- Class-level attributes for button hold logic ---
    display_font_size = 4.8
    shift_is_held = False  # Note: This is a class attribute, not instance
    hold_timer = None
    initial_delay = 500
    repeat_interval = 100
    was_held = False
    held_button_value = None

    def __init__(self):
        super().__init__()

        # --- 1. Load Settings ---
        self.setting_value_list = config_manager.load_setting_value("all")

        # --- 2. Instance State Variables ---
        # These are the "memory" of THIS calculator instance
        self.equation = ""  # New: stores the last equation text (used with show_equation/augmented assignment UI features)
        self.thread_active = False  # Is a calculation running?
        self.received_result = False  # Was the last text an answer?
        self.first_run = True  # For font resizing logic
        self.previous_equation = ""  # For "show_equation" logic
        self.undo = ["0"]  # Undo stack
        self.redo = []  # Redo stack
        self.hold_timer = QTimer(self)  # Timer for button hold
        self.hold_timer.timeout.connect(self.handle_hold_tick)
        self.current_text = ""  # The text currently being built
        self.display_text = ""  # New: optional buffer for display-related features

        # --- 3. Window Setup ---
        icon_path = PROJECT_ROOT / "icons" / "icon.png"
        app_icon = QtGui.QIcon(str(icon_path))
        self.setWindowIcon(app_icon)
        self.button_objects = {}  # Dictionary to store button widgets
        self.setWindowTitle("Calculator")
        self.resize(200, 450)
        main_v_layout = QtWidgets.QVBoxLayout(self)

        # --- 4. Sizing Policy ---
        # Makes widgets expand to fill space
        expanding_policy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        )

        # --- 5. Display Setup ---
        self.display = QtWidgets.QLineEdit("0")
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.display.setReadOnly(True)
        font = self.display.font()
        font.setPointSize(46)
        self.display.setFont(font)
        self.display.setSizePolicy(expanding_policy)
        main_v_layout.addWidget(self.display, 1)  # Add display with stretch factor 1

        # --- 6. Button Grid Setup ---
        button_container = QtWidgets.QWidget()
        main_v_layout.addWidget(button_container, 3)  # Add container with stretch factor 3
        button_grid = QtWidgets.QGridLayout(button_container)
        button_grid.setSpacing(0)
        button_grid.setContentsMargins(0, 0, 0, 0)

        # Make all button rows/columns expand equally
        for i in range(7):  # vertikal
            button_grid.setRowStretch(i, 1)
        for j in range(5):  # horizental
            button_grid.setColumnStretch(j, 1)

        # --- 7. Button Definitions ---
        # (text, row, column)
        self.buttons = [
            ('⚙️', 0, 0), ('📋', 0, 1), ('↷', 0, 2), ('↶', 0, 3), ('<', 0, 4),
            ('π', 1, 0), ('e^(', 1, 1), ('x', 1, 2), ('√(', 1, 3), ('/', 1, 4),
            ('sin(', 2, 0), ('(', 2, 1), (')', 2, 2), ('^(', 2, 3), ('*', 2, 4),
            ('cos(', 3, 0), ('7', 3, 1), ('8', 3, 2), ('9', 3, 3), ('-', 3, 4),
            ('tan(', 4, 0), ('4', 4, 1), ('5', 4, 2), ('6', 4, 3), ('+', 4, 4),
            ('log(', 5, 0), ('1', 5, 1), ('2', 5, 2), ('3', 5, 3), ('=', 5, 4),
            ('C', 6, 0), (',', 6, 1), ('0', 6, 2), ('.', 6, 3), ('⏎', 6, 4)
        ]

        # Buttons that support "press and hold"
        HOLD_BUTTONS = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '↶', '↷', '<']

        # --- 8. Button Creation Loop ---
        for self.text, self.row, self.col in self.buttons:
            self.button = QtWidgets.QPushButton(self.text)
            self.button.setSizePolicy(expanding_policy)

            # --- 8a. Special Button Connections ---
            if self.text == '⏎':
                self.button.setStyleSheet("background-color: #007bff; color: white; font-weight: bold;")
            elif self.text == '⚙️':
                self.button.clicked.connect(self.open_settings)

            # --- 8b. Input Button Connections (Hold vs. Click) ---
            if self.text in HOLD_BUTTONS:
                # Use press/release signals for hold logic
                self.button.pressed.connect(lambda checked=False, val=self.text: self.handle_button_pressed_hold(val))
                self.button.released.connect(self.handle_button_released_hold)
                self.button.clicked.connect(lambda checked=False, val=self.text: self.handle_button_clicked_hold(val))
            else:
                # Normal click connection
                self.button.clicked.connect(lambda checked=False, val=self.text: self.handle_button_press(val))

            button_grid.addWidget(self.button, self.row, self.col)
            self.button_objects[self.text] = self.button  # Store button for later (e.g., update_return_button)

        self.update_darkmode()  # Apply darkmode on initial load

    # --- Button Hold Logic ---
    def handle_button_pressed_hold(self, value):
        self.was_held = False  # Reset flag on new press
        self.held_button_value = value
        self.hold_timer.setInterval(self.initial_delay)  # Initial 500ms delay
        self.hold_timer.start()

    def handle_button_released_hold(self):
        # Stop the timer when button is released
        self.hold_timer.stop()
        self.held_button_value = None

    def handle_button_clicked_hold(self, value):
        # If the button was *not* held, it was a simple click.
        # This prevents firing a click *after* a hold.
        if not self.was_held:
            self.handle_button_press(value)

    def handle_hold_tick(self):
        # Timer fires, this is now officially a "hold"
        self.was_held = True
        # Speed up the timer for fast repeats (100ms)
        if self.hold_timer.interval() == self.initial_delay:
            self.hold_timer.setInterval(self.repeat_interval)

        # Trigger the button action again (e.g., add another '9')
        if self.held_button_value:
            self.handle_button_press(self.held_button_value)

    # --- Window/Key Event Handlers ---
    def resizeEvent(self, event):
        # This function handles the dynamic font resizing for the buttons
        super().resizeEvent(event)

        self.setMinimumSize(400, 540)
        if self.first_run == False:
            for button_text, button_instance in self.button_objects.items():
                # Calculate a new font size based on button height
                experiment = (button_instance.height() / 8) * 2
                if experiment <= 12:
                    experiment = 12
                font = button_instance.font()
                font.setPointSize((experiment))
                button_instance.setFont(font)

        elif self.first_run == True:
            # Set a default font size on first run
            for button_text, button_instance in self.button_objects.items():
                font = button_instance.font()
                font.setPointSize((12))
                button_instance.setFont(font)
                self.first_run = False

        self.update_font_size_display()  # Also update the display font

    def update_button_labels(self):
        """
        New: Toggle the clipboard button label depending on Shift state.
        - Shift held   → show 📑 (Paste)
        - Shift up     → show 📋 (Copy)
        This purely updates the label; actual behavior is handled in `handle_button_press`.
        """
        if self.shift_is_held:
            paste_button = self.button_objects.get("📋")
            if paste_button:
                paste_button.setText('📑')
        else:
            paste_button = self.button_objects.get('📋')
            if paste_button:
                paste_button.setText('📋')

    def keyPressEvent(self, event):
        # New: when Shift is pressed, reflect Paste-mode on the clipboard button label
        if event.key() == Qt.Key.Key_Shift:
            self.shift_is_held = True
            self.update_button_labels()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        # New: when Shift is released, return clipboard button label to Copy-mode
        if event.key() == Qt.Key.Key_Shift:
            self.shift_is_held = False
            self.update_button_labels()
        super().keyReleaseEvent(event)

    # --- MAIN BUTTON LOGIC ---
    # This is the "brain" of the calculator UI.
    def handle_button_press(self, value):
        global first_run  # Note: This is a global variable
        global mein_thread  # Note: This is a global variable

        # --- 1. Handle Input After a Result (=) ---
        # New: extract the last result using rindex so expressions like "12+=6 = 18" correctly pick "18".
        if len(self.undo) >= 2 and not value == "<" and self.undo[-2] == "⏎":
            ungefaehr_zeichen = "\u2248"
            marker_to_find = ""

            # Check what kind of result it was (equation, solver, etc.)
            if "|" in self.current_text:
                marker_to_find = "|"
            elif "=" in self.current_text:
                marker_to_find = "="
            elif 'x' in self.current_text:
                marker_to_find = ""
            elif ungefaehr_zeichen in self.current_text:
                marker_to_find = ungefaehr_zeichen

            # This logic extracts the *result* of the previous calculation
            # to be used as the *start* of the new one (e.g., "12+=6 = 18" -> "18")
            if marker_to_find != "":
                try:
                    if marker_to_find != "|":
                        # New: use rindex to get the last '=' or '≈' occurrence
                        marker_index = self.current_text.rindex(marker_to_find)
                        start_index = marker_index + 1
                        temp_new_text = self.current_text[start_index:].lstrip()
                        self.current_text = temp_new_text

                    elif marker_to_find == "|":
                        # For solver results, keep the equation part before the pipe
                        marker_index = self.current_text.index(marker_to_find)
                        temp_new_text = self.current_text[:marker_index].rstrip()
                        self.current_text = temp_new_text

                except ValueError:
                    pass  # Ignore if marker wasn't found

        # Resets the display if the last result was a boolean
        if self.current_text.strip() == "False" or self.current_text.strip() == "True":
            self.current_text = "0"
        #
        # if self.setting_value_list["show_equation"] == True and self.setting_value_list["allow_augmented_assignment"] == True and self.equation != "":
        #     self.display.setText(self.current_text)

        # --- 3. Handle Special Keys ---

        if value == 'C':
            # --- C (Clear) Key ---
            self.current_text = "0"
            self.display.setText(self.current_text)

        elif (value == '<'):
            # --- < (Backspace) Key ---

            # If display is already empty, do nothing
            if len(self.current_text) <= 0 or self.current_text == "0":
                self.current_text = "0"
                self.display.setText(self.current_text)
                return

            # Special logic for backspacing after an answer
            elif len(self.undo) > 1:
                print(self.current_text)
                print(str(get_line_number()))
                if self.undo[-2] == '⏎':
                    # This complex block handles backspacing after a result
                    # (e.g., "x=5 | ..." or "5+5=10")
                    print(self.undo)
                    print(str(get_line_number()))
                    # self.current_text = "3=3 |  True"
                    if "x" in self.current_text:
                        if "|" in self.current_text:
                            print(str(get_line_number()))
                            self.current_text = self.current_text[:self.current_text.index("|") - 1]
                        elif "=" in self.current_text:
                            print(str(get_line_number()))
                            self.current_text = self.current_text[self.current_text.index("=") + 1:]
                        elif "≈" in self.current_text:
                            print(str(get_line_number()))
                            self.current_text = self.current_text[self.current_text.index("≈") + 1:]
                    elif "=" in self.current_text and (
                            not "True" in self.current_text and not "False" in self.current_text):
                        print(str(get_line_number()))
                        self.current_text = self.current_text[self.current_text.index("=") + 1:]
                    elif "≈" in self.current_text and (
                            not "True" in self.current_text and not "False" in self.current_text):
                        print(str(get_line_number()))
                        self.current_text = self.current_text[self.current_text.index("≈") + 1:]
                    elif "=" in self.current_text and ("True" in self.current_text or "False" in self.current_text):
                        print(str(get_line_number()))
                        self.current_text = self.current_text[:self.current_text.index("|") - 1]
                    self.current_text = self.current_text + "0"

            # --- Smart Backspace Logic ---
            # Deletes entire functions (e.g., "sin(") in one go
            if self.current_text.endswith("True") or self.current_text.endswith("False"):
                self.current_text = self.current_text[:-5]
            elif self.current_text.endswith("sin(") or self.current_text.endswith("cos(") or self.current_text.endswith(
                    "tan(") or self.current_text.endswith("log("):
                self.current_text = self.current_text[:-4]
            elif self.current_text.endswith("e^(") or self.current_text.endswith("sin") or self.current_text.endswith(
                    "cos") or self.current_text.endswith("tan") or self.current_text.endswith("log"):
                self.current_text = self.current_text[:-3]
            elif self.current_text.endswith("√(") or self.current_text.endswith("^(") or self.current_text.endswith(
                    "e^"):
                self.current_text = self.current_text[:-2]
            else:
                # --- Normal Backspace (delete one character) ---
                print(self.undo)
                print(str(get_line_number()))
                self.current_text = self.current_text[:-1]

            # Update display, or show "0" if text is now empty
            self.display.setText(self.current_text if self.current_text else "0")

        elif (value == '⚙️'):
            # --- Settings Key ---
            return  # Logic is handled by self.open_settings, connected in __init__

        elif value == '⏎':
            # --- ⏎ (Enter/Calculate) Key ---
            print(str(get_line_number()) + " " + self.current_text)

            # Prevent starting a new calculation if one is already running
            if self.thread_active:
                print("ERROR: A calculation is already running!")  # 4002
                return
            else:
                self.thread_active = True
                self.update_return_button()  # Visually change ⏎ to X

            text_to_display = self.display.text()
            self.current_text = text_to_display

            # Logic to re-use previous result if "show_equation" is on
            if self.setting_value_list[
                "show_equation"] == True and self.previous_equation and not "x" in self.current_text:
                is_original_equation = (self.current_text == self.previous_equation)
                if not is_original_equation and not "x" in self.current_text:
                    value_part = None
                    if "|" in text_to_display:
                        value_part = text_to_display.split("|")[-1].strip()
                    elif "=" in text_to_display and self.setting_value_list["allow_augmented_assignment"] == False:
                        # New: respect setting to block augmented assignment reuse if disabled
                        value_part = text_to_display.split("=")[-1].strip()
                    elif "\u2248" in text_to_display:
                        value_part = text_to_display.split("\u2248")[-1].strip()
                    if value_part:
                        self.current_text = f"{value_part}={value_part}"
            else:
                # Clean up solver pipe character if present
                if "|" in self.current_text:
                    self.current_text = self.current_text.replace("|", "")

            # --- 4. Start Worker Thread ---
            # We give the calculation job to the Worker to keep the UI from freezing
            self.display.setText("...")  # Show "..." to indicate loading
            return_button = self.button_objects['⏎']
            QtWidgets.QApplication.processEvents()  # Force UI update *before* starting thread

            # --- Input Validation ---
            if not self.current_text.strip():
                print("ERROR: Empty string sent to MathEngine.")
                self.thread_active = False
                self.update_return_button()
                self.display.setText(text_to_display)
                return

            # --- Start Thread ---
            worker_instanz = Worker(self.current_text)
            mein_thread = threading.Thread(target=worker_instanz.run_Calc)
            mein_thread.start()

            # Connect the worker's "finished" signal to our result handler
            worker_instanz.job_finished.connect(self.Calc_result)
            return  # IMPORTANT: Stop function here. Result will arrive via signal.

        elif value == '↶':
            # --- Undo Key ---
            if len(self.undo) >= 2 and self.undo[-2] == '⏎':
                # Special case: Undo a calculation (pops 2 items: result and '⏎')
                self.redo.append(self.undo.pop())
                self.redo.append(self.undo.pop())
                self.current_text = self.undo[-1]
                self.display.setText(self.current_text)
                print(f"The key '{value}' was pressed.")
            elif len(self.undo) > 1:
                # Normal undo (pops 1 item)
                self.redo.append(self.undo.pop())
                self.current_text = self.undo[-1]
                self.display.setText(self.current_text)
                print(f"The key '{value}' was pressed.")
                print(self.undo)

        elif value == '↷':
            # --- Redo Key ---
            print("redo1: " + str(self.redo))
            if len(self.redo) >= 2 and self.redo[-1] == '⏎':
                # Special case: Redo a calculation (appends 2 items)
                print("redo2: " + str(self.redo))
                self.undo.append(self.redo.pop())
                self.undo.append(self.redo.pop())
                self.current_text = self.undo[-1]
                self.display.setText(self.current_text)
                print(f"The key '{value}' was pressed.")
            elif len(self.redo) > 0:
                # Normal redo (appends 1 item)
                self.undo.append(self.redo.pop())
                self.current_text = self.undo[-1]
                self.display.setText(self.current_text)
                print(f"The key '{value}' was pressed.")

        elif value == '📋' or value == '📑':
            # New: single handler for clipboard button.
            # - If Shift is held, interpret as Copy (📋) and copy current display.
            # - Otherwise, interpret as Paste (📑) and insert clipboard text.
            if self.shift_is_held:
                pyperclip.copy(self.display.text())
            else:
                clipboard = QtWidgets.QApplication.clipboard()
                clipboard_text = clipboard.text()

                # Clean solver/boolean decorations before pasting new content
                if "x" in self.current_text or ("True" or "False") in self.current_text:
                    if "|" in self.current_text:
                        print(str(get_line_number()))
                        self.current_text = self.current_text[:self.current_text.index("|") - 1]

                if clipboard_text:
                    # Replace "0" or append to existing input
                    if self.current_text == "0":
                        self.current_text = clipboard_text
                    else:
                        self.current_text = self.current_text + clipboard_text

                    self.display.setText(self.current_text)
                    self.undo.append(self.current_text)
                    self.redo.clear()

                    # Optional auto-enter after paste (configurable)
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
            # --- 5. Normal Keys (Numbers & Operators) ---
            # If "0" is shown, replace it (unless adding a decimal point)
            if self.current_text == "0" and value != ".":
                self.current_text = ""

            if len(self.undo) >= 2:
                print(self.current_text)
                if self.undo[-2] == "⏎" and self.setting_value_list["show_equation"] == True:
                    self.display.setText(self.current_text)

            self.current_text += str(value)
            self.display.setText(self.current_text)

        # --- 6. Cleanup & State Update ---
        self.update_font_size_display()  # Adjust font size

        # Save the new state to the undo stack
        if value != '↶' and value != '↷' and value != '📋' and value != '📑':
            self.undo.append(self.current_text)
            self.redo.clear()  # Clear redo stack on new action

        print(f"The key '{value}' was pressed.")

    def update_font_size_display(self):
        # --- Dynamic Font Resizing for Display ---
        self.current_text = self.display.text()
        MAX_FONT_SIZE = 60
        MIN_FONT_SIZE = 10

        self.display.setText(self.current_text)

        font = self.display.font()
        aktuelle_groesse = font.pointSize()
        fm = QtGui.QFontMetrics(font)

        # Calculate available width inside the QLineEdit
        r_margin = self.display.textMargins().right()
        l_margin = self.display.textMargins().left()
        padding = l_margin + r_margin + 5
        verfuegbare_breite = self.display.width() - padding

        text_breite = fm.horizontalAdvance(self.current_text)

        # --- Shrink font if too big ---
        while text_breite > verfuegbare_breite and aktuelle_groesse >= MIN_FONT_SIZE:
            aktuelle_groesse -= 0.01
            font.setPointSize(aktuelle_groesse)
            fm = QtGui.QFontMetrics(font)
            text_breite = fm.horizontalAdvance(self.current_text)

        # --- Grow font if too small ---
        temp_size = aktuelle_groesse
        while temp_size <= MAX_FONT_SIZE:
            temp_size += 0.01
            font.setPointSize(temp_size)
            fm_temp = QtGui.QFontMetrics(font)
            text_breite_temp = fm_temp.horizontalAdvance(self.current_text)
            if text_breite_temp <= verfuegbare_breite:
                aktuelle_groesse = temp_size  # This font size fits
            else:
                temp_size -= 0.01  # The last one was too big
                break

        # Apply the final calculated font size
        font.setPointSize(aktuelle_groesse)
        self.display.setFont(font)

    def update_return_button(self):
        # --- Visual Feedback for Calculation ---
        return_button = self.button_objects.get('⏎')
        if not return_button:
            return

        # Change button to "X" and red to show it's busy
        if self.thread_active == True:
            return_button.setStyleSheet("background-color: #FF0000; color: white; font-weight: bold;")
            return_button.setText("X")
        # Change back to "⏎" and blue when idle
        elif self.thread_active == False:
            return_button.setStyleSheet("background-color: #007bff; color: white; font-weight: bold;")
            return_button.setText("⏎")
        return_button.update()

    def update_darkmode(self):
        # --- Apply Dark/Light Mode to all buttons ---
        if self.setting_value_list["darkmode"] == True:
            for text, button in self.button_objects.items():
                if text != '⏎':  # Don't override the special "Enter" button style
                    button.setStyleSheet("background-color: #121212; color: white; font-weight: bold;")
                    button.update()
                if text == '⏎':
                    # Re-apply the correct "Enter" button style (blue or red)
                    self.update_return_button()

            # Set window and display background
            self.setStyleSheet(f"background-color: #121212;")
            self.display.setStyleSheet("background-color: #121212; color: white; font-weight: bold;")

        elif self.setting_value_list["darkmode"] == False:
            # --- Apply Light Mode ---
            for text, button in self.button_objects.items():
                if text != '⏎':
                    button.setStyleSheet("font-weight: normal;")  # Revert to default
                    button.update()
                if text == '⏎':
                    # Re-apply the correct "Enter" button style (blue or red)
                    self.update_return_button()

            # Revert window and display to default
            self.setStyleSheet("")
            self.display.setStyleSheet("font-weight: bold;")

    def open_settings(self):
        # --- Open Settings Dialog ---
        settings_dialog = SettingsDialog(self)
        settings_dialog.exec()  # "exec" makes the dialog modal (blocks main window)

        # --- Reload settings after dialog closes ---
        # This ensures changes (like darkmode) are applied
        self.setting_value_list = config_manager.load_setting_value("all")
        self.update_darkmode()

    def get_message_box_stylesheet(self):
        # --- Error Box Styling ---
        # Provides a matching stylesheet for error boxes in dark mode
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
            return ""  # Use default stylesheet in light mode

    def Calc_result(self, ergebnis, equation):
        # --- 1. Handle Calculation Result ---
        # This function is called by the Worker's "job_finished" signal
        self.received_result = True
        self.thread_active = False  # Thread is no longer active

        if equation.endswith('=') and self.setting_value_list["show_equation"] == True:
            # New: store the equation (without trailing '=') for subsequent UI features
            self.equation = equation[:-1]

        print(ergebnis)  # Log the raw result
        self.update_return_button()  # Change "X" back to "⏎"

        # --- 2. Handle MathError Object ---
        # If the worker sent back a MathError object...
        if isinstance(ergebnis, E.MathError):
            error_obj = ergebnis

            # --- 2a. Build Error Dialog ---
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

            # --- 2b. Reset Display ---
            # Show the original (failed) equation
            self.display.setText(equation)
            self.update_font_size_display()
            return  # Stop here

        # --- 3. Handle Successful Result (String) ---
        math_engine_output = ergebnis.strip()
        final_display_text = ""

        show_equation_setting = self.setting_value_list["show_equation"]

        # --- 4. Result Formatting Logic ---
        # This block decides *how* to show the result

        # --- 4a. Boolean Result (e.g., "5=5") ---
        if (math_engine_output == "= True" or math_engine_output == "= False") and show_equation_setting == True:
            math_engine_output = math_engine_output[math_engine_output.index("=") + 1:]
            final_display_text = f"{equation} | {math_engine_output}"
        elif (math_engine_output == "= True" or math_engine_output == "= False") and show_equation_setting == False:
            math_engine_output = math_engine_output[math_engine_output.index("=") + 1:]
            final_display_text = f"{math_engine_output}"

        # --- 4b. Solver or Calculation Result (Show Equation = ON) ---
        elif show_equation_setting == True:
            is_solver_result = math_engine_output.startswith("x =") or math_engine_output.startswith("x \u2248")
            if is_solver_result:
                final_display_text = f"{equation} | {math_engine_output}"  # e.g., "5x=10 | x = 2"
            else:
                clean_result = math_engine_output
                # Strip the prefix (= or ≈) from the engine output
                if clean_result.startswith("=") or clean_result.startswith("\u2248"):
                    clean_result = clean_result[1:].strip()

                # Re-add the correct prefix *after* the equation
                if math_engine_output.startswith("\u2248"):
                    final_display_text = f"{equation} {math_engine_output}"  # e.g., "1/3 ≈ 0.33"
                else:
                    final_display_text = f"{equation} = {clean_result}"  # e.g., "5+5 = 10"

        # --- 4c. Solver or Calculation Result (Show Equation = OFF) ---
        elif show_equation_setting == False:
            is_solver_result = math_engine_output.startswith("x =") or math_engine_output.startswith("x \u2248")
            if is_solver_result:
                final_display_text = f"{equation} | {math_engine_output}"  # Still show equation for solver
            else:
                clean_result = math_engine_output
                # Just show the result
                if math_engine_output.startswith("\u2248"):
                    final_display_text = f"{clean_result}"  # e.g., "≈ 0.33"
                else:
                    final_display_text = f"{clean_result}"  # e.g., "10"
        else:
            final_display_text = math_engine_output  # Fallback

        # --- 5. Update Display and Undo Stack ---
        self.display.setText(final_display_text)

        # Add the result to the undo stack
        if final_display_text != self.undo[-1]:
            self.undo.append('⏎')  # Add a "marker" to show this was a calculation
            self.undo.append(final_display_text)
            self.redo.clear()  # Clear redo stack

        self.update_font_size_display()

        print("undo: " + str(self.undo))
        print("redo: " + str(self.redo))
        self.previous_equation = equation  # Remember this equation


def main():
    # --- Main Application Entry Point ---
    app = QtWidgets.QApplication()
    window = CalculatorPrototype()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    # --- Start the app if this file is run directly ---
    app = QtWidgets.QApplication()
    window = CalculatorPrototype()
    window.show()
    sys.exit(app.exec())
