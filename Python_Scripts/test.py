import inspect


def get_line_number():
    """Gibt die Zeilennummer des Aufrufers zurück."""
    # inspect.currentframe() liefert das Frame-Objekt des aktuellen Aufrufs (der Funktion get_line_number).
    # .f_back greift auf das Frame-Objekt des Aufrufers (die Zeile, in der get_line_number aufgerufen wurde) zu.
    # .f_lineno ist die Zeilennummer in der Quelldatei.

    # Eine häufig verwendete, knappe Methode:
    return inspect.currentframe().f_back.f_lineno


def print_with_line(message):
    """Gibt eine Nachricht zusammen mit der Zeilennummer aus, von der aus die Funktion aufgerufen wurde."""
    line_num = get_line_number()
    print(f"[Zeile {line_num}] {message}")


# --- Beispiel ---

print_with_line("Starte Skript")  # Zeilennummer wird hier ermittelt

a = 10
b = 20

print_with_line(f"Die Summe ist: {a + b}")  # Und hier