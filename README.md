# Advanced Python Calculator with Custom Math Engine



### Project Overview

This is a sophisticated, cross-platform desktop calculator built from the ground up in Python. It serves as a comprehensive portfolio piece demonstrating proficiency in GUI development, advanced software architecture, and secure, robust backend implementation.

Unlike simple calculator scripts, this project features a **custom-built mathematical parser and Abstract Syntax Tree (AST) evaluator**, eliminating the use of `eval()` entirely. It also utilizes multi-threading to ensure a fluid, non-blocking user interface.

---

## Key Technical Features

This project was engineered to professional standards, focusing on security, performance, and user experience.

* **Secure Custom Math Engine:**
    The core of the application. Instead of using the insecure `eval()` function, the `MathEngine` implements its own tokenizer, parser, and Abstract Syntax Tree (AST) builder to safely process, interpret, and compute mathematical expressions.

* **Asynchronous & Responsive GUI:**
    All calculations are executed in a separate worker thread (`QObject` worker). This critical design choice ensures the `PySide6` main thread remains unblocked, providing a smooth, responsive user experience that never freezes, even during complex computations.

* **Integrated Linear Equation Solver:**
    The math engine automatically detects expressions containing a variable (e.g., `x`) and an equals sign. It then traverses the AST to algebraically solve for `x`, supporting full linear equations (`5*x + 10 = 2*x - 2`).

* **High-Precision & Fraction Arithmetic:**
    To ensure mathematical accuracy, the engine uses Python's `Decimal` module for all calculations, avoiding common floating-point inaccuracies. It also includes support for `fractions`, displaying results as exact fractions when appropriate.

* **Modern Qt6 Interface (PySide6):**
    The UI is built with `PySide6` (the official Python bindings for Qt 6) and features:
    * A persistent settings dialog to manage application behavior.
    * Full **Dark Mode** support.
    * An intelligently resizing display font that adapts to long inputs and results.
    * User-friendly features like Undo/Redo, clipboard integration, and button-hold detection.

* **Robust Error Handling:**
    A custom-defined hierarchy of `MathError` exceptions (`SyntaxError`, `CalculationError`, `SolverError`) provides clear, user-friendly feedback for invalid syntax, division by zero, or non-linear problems.

* **Configuration Management:**
    User preferences (like dark mode, decimal places) are saved to an external `config.json` file and managed by a dedicated `config_manager` module, demonstrating clean separation of concerns.

---

## Technology Stack

* **GUI:** `PySide6` (Python for Qt 6)
* **Core Logic:** Python 3, `Decimal`, `fractions`, `threading`
* **Utilities:** `pyperclip` (Cross-platform clipboard access), `pynput` (Key listener for modifiers like Shift)
* **Configuration:** `json`

---

## Getting Started

### Prerequisites

* Python 3.7+
* `pip` (Python package installer)

### Installation & Running

1.  **Clone the repository:**
    ```sh
    git clone [https://github.com/JanTeske06/Python_Calculator.git](https://github.com/JanTeske06/Python_Calculator.git)
    cd Python_Calculator
    ```

2.  **Create a virtual environment (Recommended):**
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install the required dependencies:**
    All dependencies are listed in `requirements.txt`.
    ```sh
    pip install -r requirements.txt
    ```

4.  **Run the application:**
    ```sh
    python main.py
    ```

---

## Project Structure

```
Python_calculator/
├── Modules/
│   ├── UI.py               # Main GUI class (PySide6 window, widgets, signals)
│   ├── MathEngine.py       # Core engine (Parser, AST, Solver, Evaluator)
│   ├── ScientificEngine.py # Handlers for sin, cos, log, etc.
│   ├── config_manager.py   # Handles loading/saving settings from JSON
│   └── error.py            # Custom error classes and error message dictionary
├── icons/
│   └── icon.png            # Application icon
├── config.json             # Stores user settings (persistent)
├── ui_strings.json         # String definitions for the settings UI
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
└── README.md               # Readme file
```


## Acknowledgements

* Special thanks to **Julian Theiling** for his dedicated bug testing and valuable feedback during development.
