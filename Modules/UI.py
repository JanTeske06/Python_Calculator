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

    keyboard_controller = Controller()
    return keyboard_controller.shift_pressed


class Worker(QObject):
    """""

    This Class is always a seperat thread, responsible for transmitting the problem to MathEngine.py
    and emits a Signal when the calculations are done / failed back to the Calculator UI for processing

    """""

    job_finished = Signal(object, str, int)

    def __init__(self, problem):
        super().__init__()
        self.data = problem  # Renamed from 'self.daten' for clarity

    def run_Calc(self):

        try:
            # --- 1. Start Calculation ---
            # This is the call to the "engine". It runs in the separate thread.
            result, mode = MathEngine.calculate(self.data)

            # --- 2. Send Success Signal ---
            # Emits the result back to the UI thread (connected to Calc_result)
            self.job_finished.emit(result, self.data, mode)

        except E.MathError as e:
            # --- 3. Send Math Error Signal ---
            # Found a known, handled error (e.g., "Division by zero")
            self.job_finished.emit(e, self.data, 0)

        except Exception as e:
            # --- 4. Send Critical Error Signal ---
            # Found an unexpected crash we didn't plan for (e.g., a bug in the code)
            critical_error = E.MathError(
                message=f"Unexpected crash: {e}",
                code="9999",
                equation=self.data  # Fixed typo from self.daten
            )
            self.job_finished.emit(critical_error, self.data, 0)


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
            saved_settings = config_manager.save_setting(setting_value_list)

            if saved_settings != {}:
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
        self.ans = ""   # Stores last result
        self.calculator_result = ""
        self.display_results = ""
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
            equal_button = self.button_objects.get("=")
            if paste_button:
                paste_button.setText('📑')

            if equal_button:
                equal_button.setText("Ans")
        else:
            paste_button = self.button_objects.get('📋')
            equal_button = self.button_objects.get("=")
            if paste_button:
                paste_button.setText('📋')

            if equal_button:
                equal_button.setText("=")

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

    def handle_button_press(self, value):
        if value == "=" or value == "Ans":
            if self.shift_is_held:
                value = "Ans"
            else:
                value = "="



        if value == "<":
            if len(self.undo) >= 2:
                if self.setting_value_list["show_equation"] == True  and self.undo[-2] == "⏎":
                    self.display_text = self.equation
                elif  self.setting_value_list["show_equation"] == False and self.undo[-2] == "⏎":
                    if "True" in self.display_text or "False" in self.display_text:
                        self.display_text = "0"
                    else:
                        self.display_text = self.calculator_result
                else:
                    self.display_text = self.display_text[:-1]
            else:
                self.display_text = self.display_text[:-1]

            if self.display_text == "":
                self.display_text = "0"

        elif value == "C":
            self.display_text = "0"

        elif value == '↶':
            # --- Undo Key ---
            if len(self.undo) >= 2 and self.undo[-2] == '⏎':
                # Special case: Undo a calculation (pops 2 items: result and '⏎')
                self.redo.append(self.undo.pop())
                self.redo.append(self.undo.pop())
                self.display_text = self.undo[-1]
            elif len(self.undo) > 1:
                # Normal undo (pops 1 item)
                self.redo.append(self.undo.pop())
                self.display_text = self.undo[-1]

        elif value == '↷':
            # --- Redo Key ---
            if len(self.redo) >= 2 and self.redo[-1] == '⏎':
                # Special case: Redo a calculation (appends 2 items)
                self.undo.append(self.redo.pop())
                self.undo.append(self.redo.pop())
                self.display_text = self.undo[-1]
            elif len(self.redo) > 0:
                # Normal redo (appends 1 item)
                self.undo.append(self.redo.pop())
                self.display_text = self.undo[-1]
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
                        self.display_text = clipboard_text
                    else:
                        self.display_text = self.display_text + clipboard_text

                    self.display.setText(self.display_text)
                    self.undo.append(self.display_text)
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
                            worker_instance = Worker(self.display_text)
                            my_thread = threading.Thread(target=worker_instance.run_Calc)
                            my_thread.start()
                            worker_instance.job_finished.connect(self.Calc_result)
            self.update_font_size_display()
            return



        elif (value == '⚙️'):
            # --- Settings Key ---
            return  # Logic is handled by self.open_settings, connected in __init__

        elif value == '⏎':
            if len(self.undo) >= 2:
                if self.undo[-2] == "⏎":
                    return


            if "Ans" in self.display_text:
                if self.calculator_result == "":
                    raise E.CalculationError("No Value in ANS", code = "4003")
                self.display_text = self.display_text.replace("Ans", self.calculator_result)

            # --- 4. Start Worker Thread ---
            # We give the calculation job to the Worker to keep the UI from freezing
            self.display.setText("...")  # Show "..." to indicate loading
            return_button = self.button_objects['⏎']
            QtWidgets.QApplication.processEvents()  # Force UI update *before* starting thread


            # --- Start Thread ---
            worker_instance = Worker(self.display_text)
            my_thread = threading.Thread(target=worker_instance.run_Calc)
            my_thread.start()

            # Connect the worker's "finished" signal to our result handler
            worker_instance.job_finished.connect(self.Calc_result)
            return  # IMPORTANT: Stop function here. Result will arrive via signal.

        else:


            if len(self.undo) >= 2:
                if self.setting_value_list["show_equation"] == True and self.undo[-2] == "⏎" and "=" in self.equation:
                    self.display_text = self.equation

                elif self.setting_value_list["show_equation"] == True and self.undo[-2] == "⏎" and not "=" in self.equation:
                    self.display_text = self.calculator_result

                elif self.setting_value_list["show_equation"] == True and self.undo[-2] == "⏎":
                    if "True" in self.calculator_result or "False" in self.calculator_result:
                        self.display_text = self.equation
                    else:
                        self.display_text = self.equation

                elif self.setting_value_list["show_equation"] == False and self.undo[-2] == "⏎":
                    if "True" in self.calculator_result or "False" in self.calculator_result:
                        self.display_text = "0"
                    else:
                        self.display_text = self.calculator_result
                else:
                    pass
            if self.display_text == "0":
                self.display_text = ""
            self.display_text += value

        if value != '↶' and value != '↷' and value != '📋' and value != '📑':
            self.undo.append(self.display_text)
            self.redo.clear()

        self.display.setText(self.display_text)

        self.update_font_size_display()




    def update_font_size_display(self):
        # --- Dynamic Font Resizing for Display ---
        self.current_text = self.display.text()
        MAX_FONT_SIZE = 60
        MIN_FONT_SIZE = 10

        self.display.setText(self.current_text)

        font = self.display.font()
        current_size = font.pointSize()
        fm = QtGui.QFontMetrics(font)

        # Calculate available width inside the QLineEdit
        r_margin = self.display.textMargins().right()
        l_margin = self.display.textMargins().left()
        padding = l_margin + r_margin + 5
        available_width = self.display.width() - padding

        text_width = fm.horizontalAdvance(self.current_text)

        # --- Shrink font if too big ---
        while text_width > available_width and current_size >= MIN_FONT_SIZE:
            current_size -= 0.01
            font.setPointSize(current_size)
            fm = QtGui.QFontMetrics(font)
            text_width = fm.horizontalAdvance(self.current_text)

        # --- Grow font if too small ---
        temp_size = current_size
        while temp_size <= MAX_FONT_SIZE:
            temp_size += 0.01
            font.setPointSize(temp_size)
            fm_temp = QtGui.QFontMetrics(font)
            text_width_temp = fm_temp.horizontalAdvance(self.current_text)
            if text_width_temp <= available_width:
                current_size = temp_size  # This font size fits
            else:
                temp_size -= 0.01  # The last one was too big
                break

        # Apply the final calculated font size
        font.setPointSize(current_size)
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





    def Calc_result(self, result, equation, mode):
        # Mode:
        # 1. Variable and Rounding
        # 2. Varbiable and no Rounding
        # 3. No Variable but rounding
        # 4. No Variable, No rounding
        self.received_result = True
        self.thread_active = False  # Thread is no longer active

        self.update_return_button()
        if isinstance(result, E.MathError):
            error_obj = result
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

        math_engine_output = result.strip()
        self.ans = math_engine_output
        self.calculator_result = math_engine_output

        show_equation_setting = self.setting_value_list["show_equation"]
        approx_sign = "\u2248"  # "≈"

        if not show_equation_setting:
            # Fall 0: Wenn 'show_equation_setting' FALSE ist, zeigen wir NUR das Ergebnis.
            # Der Modus ist in diesem Fall für die Anzeige irrelevant.
            if mode == 1:
                final_display_text = f"x {approx_sign} {math_engine_output}"
            elif mode == 2:
                final_display_text = f"x = {math_engine_output}"
            elif mode == 3:
                final_display_text = f"{approx_sign} {math_engine_output}"
            elif mode == 4:
                final_display_text = f"= {math_engine_output}"


        elif show_equation_setting == True:
            # Fall 1: Variable UND Rundung (e.g., Solver-Ergebnis mit ≈)
            if mode == 1:
                # Variable und Rundung. Gehen wir von einer Solver-Ausgabe aus (z.B. "x ≈ 1.23").
                # Zeige die Gleichung, gefolgt von der Lösung (Solver trennt man oft mit |).
                final_display_text = f"{equation} | x {approx_sign} {math_engine_output}"

            # Fall 2: Variable und KEINE Rundung (e.g., Solver-Ergebnis mit =)
            elif mode == 2:
                # Variable und keine Rundung. Gehen wir von einer Solver-Ausgabe aus (z.B. "x = 2").
                final_display_text = f"{equation} | x = {math_engine_output}"

            # Fall 3: KEINE Variable, ABER Rundung (e.g., "sqrt(2) ≈ 1.414...")
            elif mode == 3:
                # Keine Variable, aber Rundung. Die MathEngine hat ein ≈ geliefert.
                final_display_text = f"{equation} {approx_sign} {math_engine_output}"

            # Fall 4: KEINE Variable, KEINE Rundung (e.g., "5+5 = 10")
            elif mode == 4 and not "=" in equation:
                # Keine Variable, keine Rundung. Die MathEngine hat ein = geliefert.
                final_display_text = f"{equation} = {math_engine_output}"

            elif mode == 4 and "=" in equation:
                # Keine Variable, keine Rundung. Die MathEngine hat ein = geliefert.
                final_display_text = f"{equation} | {math_engine_output}"
        else:
            # Fallback, sollte niemals eintreten
            final_display_text = math_engine_output





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