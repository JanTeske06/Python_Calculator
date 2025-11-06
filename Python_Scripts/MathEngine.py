# MathEngine.py
import sys
import math
from PySide6 import QtWidgets
from PySide6.QtCore import Qt
import sys
import os
from pathlib import Path
import time
import pickle
import base64
import configparser
from decimal import Decimal
import fractions
import inspect
import error as E  # Imports Error.py
import json

import config_manager as config_manager
import ScientificEngine

debug = 0

rounding = False
cas = False
var_counter = 0
var_list = []
global_subprocess = None
python_interpreter = sys.executable
Operations = ["+","-","*","/","=","^"]
Science_Operations = ["sin","cos","tan","10^x","log","e^", "π", "√"]
config_man = str(Path(__file__).resolve().parent / "config_manager.py")
config = Path(__file__).resolve().parent.parent / "config.ini"





def get_line_number():
    return inspect.currentframe().f_back.f_lineno


def isInt(zahl):
    try:
        x = int(zahl)
        return True
    except ValueError:
        return False

def isfloat(zahl):
    try:
        x = float(zahl)
        return True
    except ValueError:
        return False


def isScOp(zahl):
    try:
        return Science_Operations.index(zahl)
    except ValueError:
        return -1


def isOp(zahl):
    try:
        return Operations.index(zahl)
    except ValueError:
        return -1


def isolate_bracket(problem, b_anfang):
    start = b_anfang
    start_klammer_index = problem.find('(', start)
    if start_klammer_index == -1:
        raise SyntaxError("3000 Fehlende öffnende Klammer nach Funktionsnamen.") #3000
    b = start_klammer_index + 1
    bracket_count = 1
    while bracket_count != 0 and b < len(problem):
        if problem[b] == '(':
            bracket_count += 1
        elif problem[b] == ')':
            bracket_count -= 1
        b += 1
    ergebnis = problem[start:b]
    return (ergebnis, b)

class Number:
    def __init__(self, value):
        self.value = Decimal(value)

    def evaluate(self):
        return self.value

    def collect_term(self, var_name):
        return (0, self.value)

    def __repr__(self):
        return f"Nummer({self.value})"


class Variable:
    def __init__(self, name):
        self.name = name

    def evaluate(self):
        raise SyntaxError("3001 Fehlender Solver.") #3001

    def collect_term(self, var_name):
        if self.name == var_name:
            return (1, 0)
        else:
            raise ValueError(f"3002 Mehrere Variablen gefunden: {self.name}") #3002
            return (0, 0)

    def __repr__(self):
        return f"Variable('{self.name}')"


class BinOp:
    def __init__(self, left, operator, right):
        self.left = left
        self.operator = operator
        self.right = right

    def evaluate(self):
        left_value = self.left.evaluate()
        right_value = self.right.evaluate()

        if self.operator == '+':
            return left_value + right_value
        elif self.operator == '-':
            return left_value - right_value
        elif self.operator == '*':
            return left_value * right_value
        elif self.operator == '^':
            return left_value ** right_value
        elif self.operator == '/':
            if right_value == 0:
                raise ZeroDivisionError("3003 Teilen durch Null") #3003
            return left_value / right_value
        elif self.operator == '=':
            return left_value == right_value
        else:
            raise ValueError(f"3004Unbekannter Operator: {self.operator}") #3004

    def collect_term(self, var_name):
        (left_faktor, left_konstante) = self.left.collect_term(var_name)
        (right_faktor, right_konstante) = self.right.collect_term(var_name)

        if self.operator == '+':
            result_faktor = left_faktor + right_faktor
            result_konstante = left_konstante + right_konstante
            return (result_faktor, result_konstante)

        elif self.operator == '-':
            result_faktor = left_faktor - right_faktor
            result_konstante = left_konstante - right_konstante
            return (result_faktor, result_konstante)

        elif self.operator == '*':
            if left_faktor != 0 and right_faktor != 0:
                raise SyntaxError("3005 x^x Fehler.") #3005

            elif left_faktor == 0:
                result_faktor = left_konstante * right_faktor
                result_konstante = left_konstante * right_konstante
                return (result_faktor, result_konstante)

            elif right_faktor == 0:
                result_faktor = right_konstante * left_faktor
                result_konstante = right_konstante * left_konstante
                return (result_faktor, result_konstante)

            elif left_faktor == 0 and right_faktor == 0:
                result_faktor = 0
                result_konstante = right_konstante * left_konstante
                return (result_faktor, result_konstante)


        elif self.operator == '/':
            if right_faktor != 0:
                raise ValueError("3006 Nicht lineare Gleichung. (Teilen durch x)") #3006
            elif right_konstante == 0:
                raise ZeroDivisionError("3003 Solver: Teilen durch Null") # 3003
            else:
                result_faktor = left_faktor / right_konstante
                result_konstante = left_konstante / right_konstante
                return (result_faktor, result_konstante)




        elif self.operator == '^':
            raise ValueError("3007 Potenzen werden vom linearen Solver nicht unterstützt.") #3007


        elif self.operator == '=':
            raise ValueError("3720 Sollte nicht passieren: '=' innerhalb von collect_terms") #3720

        else:
            raise ValueError(f"3004 Unbekannter Operator: {self.operator}") #3004

    def __repr__(self):
        return f"BinOp({self.operator!r}, left={self.left}, right={self.right})"



def translator(problem):
    var_counter = 0
    var_list = [None] * len(problem)
    full_problem = []
    b = 0

    while b < len(problem):

        current_char = problem[b]

        if isInt(current_char) or(b>= 0 and current_char == "."):
            str_number = current_char
            hat_schon_komma = False

            while (b + 1 <len(problem)) and (isInt(problem[b + 1]) or problem[b + 1] == "."):
                if problem[b + 1] == ".":
                    if hat_schon_komma:
                        raise SyntaxError("3008 Doppeltes Kommazeichen.") #3008
                    hat_schon_komma = True

                b += 1
                str_number += problem[b]

            if isfloat(str_number) or isInt(str_number):
                #full_problem.append(float(str_number))
                full_problem.append(Decimal(str_number))

        elif isOp(current_char) != -1:
            full_problem.append(current_char)

        elif current_char == " ":
            pass

        elif current_char == "(":
            full_problem.append("(")

        elif current_char == "≈":
            full_problem.append("=")

        elif current_char == ")":
            full_problem.append(")")

        elif current_char == ",":
            full_problem.append(",")

        # elif(current_char) in Science_Operations:
        #     full_problem.append(ScienceCalculator(current_char))

        elif ((((current_char) == 's' or (current_char) == 'c' or (current_char) == 't' or (
        current_char) == 'l') and len(problem) - b >= 5) or
              (current_char == '√' and len(problem) - b >= 2) or
              (current_char == 'e' and len(problem) - b >= 3)):

            if(current_char == '√' and problem[b+1] == '('):
                full_problem.append('√')
                full_problem.append('(')
                b=b+1
            elif(current_char == 'e' and problem[b+1] == '^'and problem[b+2] == '('):
                full_problem.append('e^')
                full_problem.append('(')
                b=b+2

            elif (current_char in ['s', 'c', 't', 'l'] and len(problem) >= 3):
                if len(problem) - b >= 4 and problem[b:b + 3] in ['sin', 'cos', 'tan', 'log']:
                    if problem[b + 3] == '(':
                        full_problem.append(problem[b:b + 3])
                        full_problem.append('(')
                        b += 3
                    else:
                        raise ValueError(
                            f"3010 Fehlende Klammer nach: '{problem[b:b + 3]}'")
                elif len(problem) - b == 3 and problem[b:b + 3] in ['sin', 'cos', 'tan', 'log']:
                    raise ValueError(
                        f"3023 Fehlende Klammer nach: '{problem[b:b + 3]}'")




        elif current_char == 'π':
            ergebnis_string = ScientificEngine.isPi(str(current_char))

            try:
                berechneter_wert = Decimal(ergebnis_string)
                full_problem.append(berechneter_wert)
            except ValueError:
                raise ValueError(f"3219 Fehler bei Konstante π: {ergebnis_string}") #3219


        else:
            if current_char in var_list:
                full_problem.append("var" + str(var_list.index(current_char)))
            else:
                full_problem.append("var" + str(var_counter))
                var_list[var_counter] = current_char
                var_counter += 1

        b = b + 1

    b = 0
    while b < len(full_problem):

        if b + 1 < len(full_problem):

            aktuelles_element = full_problem[b]
            nachfolger = full_problem[b + 1]
            einfuegen_noetig = False

            ist_funktionsname = isScOp(nachfolger) != -1
            ist_zahl_oder_variable = isinstance(aktuelles_element, (int, float, Decimal)) or ("var" in str(aktuelles_element) and
                                                                                              isinstance(aktuelles_element, str))
            ist_klammer_oder_nachfolger = (nachfolger == '(' or ("var" in str(nachfolger) and isinstance(nachfolger, str)) or
                                           isinstance(nachfolger, (int, float, Decimal)) or ist_funktionsname)
            ist_kein_operator = aktuelles_element not in Operations and nachfolger not in Operations

            if (ist_zahl_oder_variable or aktuelles_element == ')') and \
                    (ist_klammer_oder_nachfolger or nachfolger == '(') and \
                    ist_kein_operator:

                if aktuelles_element in ['*', '+', '-', '/'] or nachfolger in ['*', '+', '-', '/']:
                    einfuegen_noetig = False
                elif aktuelles_element == ')' and nachfolger == '(':
                    einfuegen_noetig = True
                elif aktuelles_element != '(' and nachfolger != ')':
                    einfuegen_noetig = True

            if einfuegen_noetig:
                full_problem.insert(b + 1, '*')

        b += 1



    return full_problem, var_counter


def ast(received_string):

    analysed, var_counter = translator(received_string)

    if analysed and analysed[0] == "=" and not "var0" in analysed:
        analysed.pop(0)
        if global_subprocess == "0":
            print("Gleichheitszeichen am Anfang entfernt.")

    if analysed and analysed[-1] == "="and not "var0" in analysed:
        analysed.pop()
        if global_subprocess == "0":
            print("Gleichheitszeichen am Ende entfernt.")

    if  ((analysed and analysed[-1] == "=") or (analysed and analysed[0] == "=")) and "var0" in analysed:
        raise ValueError(f"3025 {received_string}")


    if global_subprocess == "0":
        print(analysed)


    def parse_factor(tokens):
        token = tokens.pop(0)
        if token == "(":
            baum_in_der_klammer = parse_sum(tokens)

            if not tokens or tokens.pop(0) != ')':
                raise SyntaxError("3009 Fehlende schließende Klammer ')'") #3009

            return baum_in_der_klammer

        elif token in Science_Operations:

            if token == 'π':
                ergebnis = ScientificEngine.isPi(token)

                try:
                    berechneter_wert = Decimal(ergebnis)
                    return Number(berechneter_wert)
                except ValueError:
                    raise SyntaxError(f"3219 Fehler bei Konstante π: {ergebnis}") #3219

            else:
                if not tokens or tokens.pop(0) != '(':
                    raise SyntaxError(f"3010 Fehlende öffnende Klammer nach Funktion {token}") #3010

                argument_baum = parse_sum(tokens)

                if token == 'log' and tokens and tokens[0] == ',':
                    tokens.pop(0)
                    basis_baum = parse_sum(tokens)
                    if not tokens or tokens.pop(0) != ')':
                        raise SyntaxError(f"3009 Fehlende schließende Klammer nach Logarithmusbasis.") #3009
                    argument_wert = argument_baum.evaluate()
                    basis_wert = basis_baum.evaluate()
                    ScienceOp = f"{token}({argument_wert},{basis_wert})"
                else:
                    if not tokens or tokens.pop(0) != ')':
                        raise SyntaxError(f"3009 Fehlende schließende Klammer nach Funktion '{token}'") #3009

                    argument_wert = argument_baum.evaluate()
                    ScienceOp = f"{token}({argument_wert})"
                ergebnis_string = ScientificEngine.unknown_function(ScienceOp)
                try:
                    berechneter_wert = float(ergebnis_string)
                    return Number(berechneter_wert)
                except ValueError:
                    raise SyntaxError(f"3218 Fehler bei wissenschaftlicher Funktion: {ergebnis_string}") #3218

        elif isinstance(token, Decimal):
            return Number(token)
        elif isInt(token):
            return Number(token)

        elif isfloat(token):
            return Number(token)

        elif "var" in str(token):
            return Variable(token)

        else:
            raise SyntaxError(f"3012 Unerwartetes Token: {token}") #3012


    def parse_unary(tokens):
            if tokens and tokens[0] in ('+', '-'):
                operator = tokens.pop(0)
                operand = parse_unary(tokens)

                if operator == '-':
                    if isinstance(operand, Number):
                        return Number(-operand.evaluate())
                    return BinOp(Number(0.0), '-', operand)
                else:
                    return operand
            return parse_power(tokens)

    def parse_power(tokens):
        aktueller_baum = parse_factor(tokens)
        while tokens and tokens[0] in ("^"):
            operator = tokens.pop(0)
            rechtes_teil = parse_unary(tokens)
            if not isinstance(aktueller_baum, Variable) and not isinstance(rechtes_teil, Variable):
                basis = aktueller_baum.evaluate()
                exponent = rechtes_teil.evaluate()
                ergebnis = basis ** exponent
                aktueller_baum = Number(ergebnis)
            else:
                aktueller_baum = BinOp(aktueller_baum, operator, rechtes_teil)
        return aktueller_baum


    def parse_term(tokens):

        aktueller_baum = parse_unary(tokens)
        while tokens and tokens[0] in ("*","/"):
            operator = tokens.pop(0)
            rechtes_teil = parse_unary(tokens)
            aktueller_baum = BinOp(aktueller_baum, operator, rechtes_teil)

        return aktueller_baum



    def parse_sum(tokens):

        aktueller_baum = parse_term(tokens)

        while tokens and tokens[0] in ("+", "-"):

            operator = tokens.pop(0)
            if debug == 1:
                print("Currently at:" + str(operator) + "in parse_sum")
            rechte_seite = parse_term(tokens)
            aktueller_baum = BinOp(aktueller_baum, operator, rechte_seite)

        return aktueller_baum

    def parse_gleichung(tokens):
        linke_seite = parse_sum(tokens)
        if tokens and tokens[0] == "=":
            operator = tokens.pop(0)
            rechte_seite = parse_sum(tokens)

            return BinOp(linke_seite, operator, rechte_seite)
        return linke_seite

    finaler_baum = parse_gleichung(analysed)

    if isinstance(finaler_baum, BinOp) and finaler_baum.operator == '=' and var_counter <= 1:
        cas = True


    if global_subprocess == "0":
        print("Finaler AST:")
        print(finaler_baum)

    cas = locals().get('cas', False)



    return finaler_baum, cas, var_counter


def solve(baum,var_name):
    if not isinstance(baum, BinOp) or baum.operator != '=':
        raise ValueError("3012 Keine gültige Gleichung zum Lösen.") #3012
    (A, B) = baum.left.collect_term(var_name)
    (C, D) = baum.right.collect_term(var_name)
    nenner = A - C
    zaehler = D - B
    if nenner == 0:
        if zaehler == 0:
            return "Inf. Solutions"
        else:
            return "No Solution"
    return zaehler / nenner


def cleanup(ergebnis):
    rounding = locals().get('rounding', False)

    target_decimals = config_manager.load_setting_value("decimal_places")
    target_fractions = config_manager.load_setting_value("fractions")


    if target_fractions == True and isinstance(ergebnis, Decimal):
        try:
            bruch_ergebnis = fractions.Fraction.from_decimal(ergebnis)
            gekuerzter_bruch = bruch_ergebnis.limit_denominator(100000)
            zaehler = gekuerzter_bruch.numerator
            nenner = gekuerzter_bruch.denominator
            if abs(zaehler) > nenner:
                ganzzahl = zaehler // nenner
                rest_zaehler = zaehler % nenner

                if rest_zaehler == 0:
                    return str(ganzzahl), rounding
                else:
                    if ganzzahl < 0 and rest_zaehler > 0:
                        ganzzahl += 1
                        rest_zaehler = abs(nenner - rest_zaehler)
                    return f"{ganzzahl} {rest_zaehler}/{nenner}", rounding

            return str(gekuerzter_bruch), rounding

        except Exception as e:
            raise ValueError(f"3024 Warnung: Bruch-Umwandlung fehlgeschlagen: {e}")
            pass

    if isinstance(ergebnis, Decimal):

        if target_decimals >= 0:
            rundungs_muster = Decimal('1e-' + str(target_decimals))
        else:
            rundungs_muster = Decimal('1')
        gerundetes_ergebnis = ergebnis.quantize(rundungs_muster)
        if gerundetes_ergebnis != ergebnis:
            rounding = True

        return gerundetes_ergebnis.normalize(), rounding


    elif isinstance(ergebnis, (int, float)):
        if ergebnis == int(ergebnis):
            return int(ergebnis), rounding

        else:
            s_ergebnis = str(ergebnis)
            if '.' in s_ergebnis:
                decimal_index = s_ergebnis.find('.')
                actual_decimals = len(s_ergebnis) - decimal_index - 1
                if actual_decimals > target_decimals:
                    rounding = True
                    new_number = round(ergebnis, target_decimals)
                    return new_number, rounding

                return ergebnis, rounding
            return ergebnis, rounding


    return ergebnis, rounding







def calculate(problem):
    settings = config_manager.load_setting_value("all")
    try:
        finaler_baum, cas, var_counter = ast(problem)

        if cas and var_counter > 0:
            var_name_in_ast = "var0"
            ergebnis = solve(finaler_baum, var_name_in_ast)


        elif not cas and var_counter == 0:
            ergebnis = finaler_baum.evaluate()


        elif cas and var_counter == 0:
            left_val = finaler_baum.left.evaluate()
            right_val = finaler_baum.right.evaluate()
            if global_subprocess == "0":
                ausgabe = True if left_val == right_val else False
                print(f"{get_line_number()} Das Ergebnis der Gleichung ist: {left_val} = {right_val} -> {ausgabe}")
            else:
                ausgabe_string = True if left_val == right_val else True
                return f"= {ausgabe_string}"
                print(f"= {ausgabe_string}")

            return
        else:
            if cas:
                print("!!ERROR!! 3005 Der Solver wurde auf einer Nicht-Gleichung")  # 3005
            elif not cas and not "=" in problem:
                print("!!ERROR!! 3012 Kein '=' gefunden, obwohl eine Variable angegeben wurde.")  # 3015


            elif cas and "=" in problem and (
                    problem.index("=") == 0 or problem.index("=") == (len(problem) - 1)):
                print("!!ERROR!! 3022 Einer der Seiten ist leer: " + problem)  # 3015


            else:
                print("!!ERROR!! 3015 Der Taschenrechner wurde auf einer Gleichung aufgerufen.")  # 3015

            return

        ergebnis, rounding = cleanup(ergebnis)
        ungefaehr_zeichen = "\u2248"

        if isinstance(ergebnis, str) and '/' in ergebnis:
            ausgabe_string = ergebnis

        elif isinstance(ergebnis, Decimal):
            try:
                ausgabe_string = ergebnis.to_normal_string()
            except AttributeError:
                ausgabe_string = str(ergebnis)
        else:
            ausgabe_string = str(ergebnis)

        if global_subprocess == "0":
            variable_name = var_list[0] if var_list else "Ergebnis"
            if rounding == True and not cas:
                print( str(get_line_number()) + f" Das Ergebnis der Berechnung ist: {variable_name} {ungefaehr_zeichen} {ausgabe_string}")
            else:
                print(str(get_line_number()) + f" Das Ergebnis der Berechnung ist: {variable_name} = {ausgabe_string}")
        elif cas == True and rounding == True:
            return (f"x {ungefaehr_zeichen} " + ausgabe_string)
            print(f"x {ungefaehr_zeichen} " + ausgabe_string)

        elif cas == True and rounding == False:
            print("x = " + ausgabe_string)
            return ("x = " + ausgabe_string)

        elif rounding == True and not cas:
            print(f"{ungefaehr_zeichen} " + ausgabe_string)
            return (f"{ungefaehr_zeichen} " + ausgabe_string)

        else:
            print("= " + ausgabe_string)
            return ("= " + ausgabe_string)



    except (ValueError, SyntaxError, ZeroDivisionError) as e:
        error_message = str(e).strip()
        cleaned_error_message = error_message

        if error_message.lower().startswith("valueerror: "):
            cleaned_error_message = error_message[len("ValueError: "):]
        elif error_message.lower().startswith("syntaxerror: "):
            cleaned_error_message = error_message[len("SyntaxError: "):]

        parts = cleaned_error_message.split(maxsplit=1)

        if parts and parts[0].isdigit() and len(parts[0]) == 4:
            print(f"!!ERROR!! {error_message}")
        else:
            error_type = type(e).__name__
            print(f"!!ERROR!! 9999 UNERWARTETER FEHLER ({error_type}): {error_message}")

    sys.exit(0)

def test_main():
    print("Gebe das Problem ein: ")
    problem = input()
    calculate(problem)
    test_main()


if __name__ == "__main__":
    debug = 0  # 1 = activated, 0 = deactivated
    test_main()

