# MathEngine.py
"""""
Core calculation engine for the Advanced Python Calculator.

Pipeline
--------
1) Tokenizer: converts a raw input string into a flat list of tokens.
2) Parser (AST): builds an Abstract Syntax Tree (recursive-descent, precedence aware).
3) Evaluator / Solver:
   - Evaluate pure numeric expressions
   - Solve linear equations with a single variable (e.g. 'x')
4) Formatter: renders results using Decimal/Fraction and user preferences.
"""""

import sys
from decimal import Decimal, getcontext, Overflow
import fractions
import inspect

from . import config_manager as config_manager
from . import ScientificEngine
from . import error as E

# Debug toggle for optional prints in this module
debug = True

# Supported operators / functions (kept as simple lists for quick membership checks)
Operations = ["+","-","*","/","=","^"]
Science_Operations = ["sin","cos","tan","10^x","log","e^", "π", "√"]

# Global Decimal precision used by this module (UI may also enforce this before calls)
getcontext().prec = 50


# -----------------------------
# Utilities / small helpers
# -----------------------------

def get_line_number():
    """Return the caller line number (small debug helper)."""
    return inspect.currentframe().f_back.f_lineno


def isInt(zahl):
    """Return True if the given string can be parsed as int; else False."""
    try:
        x = int(zahl)
        return True
    except ValueError:
        return False

def isfloat(zahl):
    """Return True if the given string can be parsed as float; else False.
    Note: tokenization may probe with float; evaluation uses Decimal.
    """
    try:
        x = float(zahl)
        return True
    except ValueError:
        return False


def isScOp(zahl):
    """Return index of a known scientific operation or -1 if unknown."""
    try:
        return Science_Operations.index(zahl)
    except ValueError:
        return -1


def isOp(zahl):
    """Return index of a known basic operator or -1 if unknown."""
    try:
        return Operations.index(zahl)
    except ValueError:
        return -1


def isolate_bracket(problem, b_anfang):
    """Return substring from the opening '(' at/after b_anfang up to its matching ')'.

    This walks forward and counts parentheses depth; raises on missing '('.
    Returns:
        (substring_including_brackets, position_after_closing_paren)
    """
    start = b_anfang
    start_klammer_index = problem.find('(', start)
    if start_klammer_index == -1:
        raise E.SyntaxError(f"Multiple missing opening parentheses after function name.", code="3000")
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


# -----------------------------
# AST node types
# -----------------------------

class Number:
    """AST node for numeric literal backed by Decimal."""
    def __init__(self, value):
        # Always normalize input to Decimal via string to avoid float artifacts
        if not isinstance(value, Decimal):
            value = str(value)
        self.value = Decimal(value)

    def evaluate(self):
        """Return Decimal value for this literal."""
        return self.value

    def collect_term(self, var_name):
        """Return (factor_of_var, constant) for linear collection."""
        return (0, self.value)

    def __repr__(self):
        # Helpful for debugging/printing the AST
        try:
            display_value = self.value.to_normal_string()
        except AttributeError:
            # Fallback for older Decimal versions
            display_value = str(self.value)
        return f"Number({display_value})"


class Variable:
    """AST node representing a single symbolic variable (e.g. 'var0')."""
    def __init__(self, name):
        self.name = name

    def evaluate(self):
        """Variables cannot be directly evaluated without solving."""
        raise E.SolverError(f"Non linear problem.", code="3005")

    def collect_term(self, var_name):
        """Return (1, 0) if this variable matches var_name; else error."""
        if self.name == var_name:
            return (1, 0)
        else:
            # Only one variable supported in the linear solver
            raise E.SolverError(f"Multiple variables found: {self.name}", code="3002")
            return (0, 0)

    def __repr__(self):
        return f"Variable('{self.name}')"


class BinOp:
    """AST node for a binary operation: left <operator> right."""
    def __init__(self, left, operator, right):
        self.left = left
        self.operator = operator
        self.right = right

    def evaluate(self):
        """Evaluate numeric subtree and apply the binary operator."""
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
                raise E.CalculationError("Division by zero", code = "3003")
            return left_value / right_value
        elif self.operator == '=':
            # Equality is evaluated to a boolean (used for "= True/False" responses)
            return left_value == right_value
        else:
            raise E.CalculationError(f"Unknown operator: {self.operator}", code="3004")

    def collect_term(self, var_name):
        """Collect linear terms on this subtree into (factor_of_var, constant).

        Only linear combinations are allowed; non-linear forms raise Solver/Syntax errors.
        """
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
            # Only constant * (A*x + B) is allowed. (A*x + B)*(C*x + D) would be non-linear.
            if left_faktor != 0 and right_faktor != 0:
                raise E.SyntaxError("x^x Error.", code = "3005")

            elif left_faktor == 0:
                # B * (C*x + D) = (B*C)*x + (B*D)
                result_faktor = left_konstante * right_faktor
                result_konstante = left_konstante * right_konstante
                return (result_faktor, result_konstante)

            elif right_faktor == 0:
                # (A*x + B) * D = (A*D)*x + (B*D)
                result_faktor = right_konstante * left_faktor
                result_konstante = right_konstante * left_konstante
                return (result_faktor, result_konstante)

            elif left_faktor == 0 and right_faktor == 0:
                # Pure constant multiplication
                result_faktor = 0
                result_konstante = right_konstante * left_konstante
                return (result_faktor, result_konstante)

        elif self.operator == '/':
            # (A*x + B) / D is allowed; division by (C*x + D) is non-linear
            if right_faktor != 0:
                raise E.SolverError("Non-linear equation. (Division by x)", code = "3006")
            elif right_konstante == 0:
                raise E.SolverError("Solver: Division by zero", code="3003")
            else:
                # (A*x + B) / D = (A/D)*x + (B/D)
                result_faktor = left_faktor / right_konstante
                result_konstante = left_konstante / right_konstante
                return (result_faktor, result_konstante)

        elif self.operator == '^':
            # Powers generate non-linear terms (e.g., x^2)
            raise E.SolverError("Powers are not supported by the linear solver.", code = "3007")

        elif self.operator == '=':
            # '=' only belongs at the root for solving; not inside collection
            raise E.SolverError("Should not happen: '=' inside collect_terms", code="3720")

        else:
            raise E.CalculationError(f"Unknown operator: {self.operator}", code = "3004")

    def __repr__(self):
        return f"BinOp({self.operator!r}, left={self.left}, right={self.right})"


# -----------------------------
# Tokenizer
# -----------------------------

def translator(problem):
    """Convert raw input string into a token list (numbers, ops, parens, variables, functions).

    Notes:
    - Inserts implicit multiplication where needed (e.g., '5x' -> '5', '*', 'var0').
    - Maps '≈' to '=' so the rest of the pipeline can handle equality uniformly.
    """
    var_counter = 0
    var_list = [None] * len(problem)  # Track seen variable symbols → var0, var1, ...
    full_problem = []
    b = 0

    while b < len(problem):
        current_char = problem[b]

        # --- Numbers: digits and decimal separator ---
        if isInt(current_char) or (b >= 0 and current_char == "."):
            str_number = current_char
            hat_schon_komma = False  # Only one dot allowed in a numeric literal

            while (b + 1 < len(problem)) and (isInt(problem[b + 1]) or problem[b + 1] == "."):
                if problem[b + 1] == ".":
                    if hat_schon_komma:
                        raise E.SyntaxError("Double comma sign.", code = "3008" )
                    hat_schon_komma = True

                b += 1
                str_number += problem[b]

            # Store as Decimal to keep high precision downstream
            if isfloat(str_number) or isInt(str_number):
                full_problem.append(Decimal(str_number))

        # --- Operators ---
        elif isOp(current_char) != -1:
            full_problem.append(current_char)

        # --- Whitespace (ignored) ---
        elif current_char == " ":
            pass

        # --- Parentheses ---
        elif current_char == "(":
            full_problem.append("(")
        elif current_char == "≈":  # treat as equality
            full_problem.append("=")
        elif current_char == ")":
            full_problem.append(")")
        elif current_char == ",":
            full_problem.append(",")

        # --- Scientific functions and special forms: sin(, cos(, tan(, log(, √(, e^( ---
        elif ((((current_char) == 's' or (current_char) == 'c' or (current_char) == 't' or (
        current_char) == 'l') and len(problem) - b >= 5) or
              (current_char == '√' and len(problem) - b >= 2) or
              (current_char == 'e' and len(problem) - b >= 3)):

            if (current_char == '√' and problem[b+1] == '('):
                full_problem.append('√')
                full_problem.append('(')
                b = b + 1
            elif (current_char == 'e' and problem[b+1] == '^' and problem[b+2] == '('):
                full_problem.append('e^')
                full_problem.append('(')
                b = b + 2

            elif (current_char in ['s', 'c', 't', 'l'] and len(problem) >= 3):
                # Validate presence of opening parenthesis after function name
                if len(problem) - b >= 4 and problem[b:b + 3] in ['sin', 'cos', 'tan', 'log']:
                    if problem[b + 3] == '(':
                        full_problem.append(problem[b:b + 3])
                        full_problem.append('(')
                        b += 3
                    else:
                        raise E.CalculationError(f"Missing parenthesis after: '{problem[b:b + 3]}", code = "3010")
                elif len(problem) - b == 3 and problem[b:b + 3] in ['sin', 'cos', 'tan', 'log']:
                    # Function name at end without '('
                    raise E.CalculationError(f"Missing parenthesis after: '{problem[b:b + 3]}", code="3023")

        # --- Constant π ---
        elif current_char == 'π':
            ergebnis_string = ScientificEngine.isPi(str(current_char))
            try:
                berechneter_wert = Decimal(ergebnis_string)
                full_problem.append(berechneter_wert)
            except ValueError:
                raise E.CalculationError(f"Error with constant π:{ergebnis_string}", code = "3219")

        # --- Variables (fallback) ---
        else:
            # Map each new variable symbol to var{n} to keep internal representation uniform
            if current_char in var_list:
                full_problem.append("var" + str(var_list.index(current_char)))
            else:
                full_problem.append("var" + str(var_counter))
                var_list[var_counter] = current_char
                var_counter += 1

        b = b + 1

    # --- Implicit multiplication pass ---
    # Insert '*' between adjacent tokens that imply multiplication:
    # number/variable/')' followed by '(' / number / variable / function name
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


# -----------------------------
# Parser (recursive descent)
# -----------------------------

def ast(received_string, settings):
    """Parse a token stream into an AST.
    Implements precedence via nested functions: factor → unary → power → term → sum → equation.
    """
    analysed, var_counter = translator(received_string)

    # Normalize spurious leading/trailing '=' if there's no variable; keep equations intact
    if analysed and analysed[0] == "=" and not "var0" in analysed:
        analysed.pop(0)
        if debug == True:
            print("Equals sign removed at the beginning.")

    if analysed and analysed[-1] == "=" and not "var0" in analysed:
        analysed.pop()
        if debug == True:
            print("Equals sign removed at the end.")

    # Check if the first character is Division / Multiplication
    if analysed and (analysed[0] == "*" or analysed[0] == "/"):
        raise E.CalculationError("Missing Number.", code = "3028")

    if analysed:
        b = 0

        while b < len(analysed)-1:

            # Case 1: '=' follows directly after an operator
            # Example: "+=" or "*=" → invalid, missing number before '='
            if (len(analysed) != b + 1) and (analysed[b + 1] == "=" and (analysed[b] in Operations)) and (settings["allow_augmented_assignment"] == False):
                raise E.CalculationError("Missing Number before '='.", code="3028")

            elif((len(analysed) != b + 1 or len(analysed) != b + 2 ) and (analysed[b + 1] == "=" and (analysed[b] in Operations)) and (settings["allow_augmented_assignment"] == True) and not "var0" in analysed):
                    analysed.insert(b, ")")
                    analysed.insert(0, "(")
                    analysed.pop(b+3)

            elif ((len(analysed) != b + 1 or len(analysed) != b + 2) and (
                    analysed[b + 1] == "=" and (analysed[b] in Operations)) and (
                          settings["allow_augmented_assignment"] == True) and "var0" in analysed):
                raise E.CalculationError("Augmented assignment not allowed with variables.", code="3030")
            # Case 2: '=' precedes an operator
            # Example: "=+" or "=*" → invalid, missing number after '='
            elif (b > 0) and (analysed[b + 1] == "=" and (analysed[b] in Operations)):
                raise E.CalculationError("Missing Number after '='.", code="3028")

            elif analysed[-1] in Operations:
                raise E.CalculationError(f"Missing Number after {analysed[-1]}", code="3029")

            elif (analysed[b] in Operations and (analysed[b + 1] == "=" and (settings["allow_augmented_assignment"] == False))) and not "var0" in analysed:
                raise E.CalculationError(f"Missing Number after {analysed[b]}", code="3029")


            b += 1



    # '=' at start/end while a variable exists → malformed equation
    if  ((analysed and analysed[-1] == "=") or (analysed and analysed[0] == "=")) and "var0" in analysed:
        raise E.CalculationError(f"{received_string}", code = "3025")

    if debug == True:
        print(analysed)

    # ---- Parsing functions in precedence order ----

    def parse_factor(tokens):
        """Numbers, variables, sub-expressions in '()', and scientific functions."""
        if len(tokens) > 0:
            token = tokens.pop(0)

        else:
            raise E.CalculationError(f"Missing Number.", code = "3027")

        # Parenthesized sub-expression
        if token == "(":
            baum_in_der_klammer = parse_sum(tokens)
            if not tokens or tokens.pop(0) != ')':
                raise E.SyntaxError("Missing closing parenthesis ')'", code = "3009")
            return baum_in_der_klammer

        # Scientific functions / constants
        elif token in Science_Operations:

            if token == 'π':
                ergebnis = ScientificEngine.isPi(token)
                try:
                    berechneter_wert = Decimal(ergebnis)
                    return Number(berechneter_wert)
                except ValueError:
                    raise E.SyntaxError(f"Error with constant π: {ergebnis}", code = "3219")

            else:
                # function must be followed by '('
                if not tokens or tokens.pop(0) != '(':
                    raise E.SyntaxError(f"Missing opening parenthesis after function {token}", code = "3010")

                argument_baum = parse_sum(tokens)

                # Special case: log(number, base)
                if token == 'log' and tokens and tokens[0] == ',':
                    tokens.pop(0)
                    basis_baum = parse_sum(tokens)
                    if not tokens or tokens.pop(0) != ')':
                        raise E.SyntaxError(f"Missing closing parenthesis after logarithm base.", code = "3009")
                    argument_wert = argument_baum.evaluate()
                    basis_wert = basis_baum.evaluate()
                    ScienceOp = f"{token}({argument_wert},{basis_wert})"
                else:
                    if not tokens or tokens.pop(0) != ')':
                        raise E.SyntaxError(f"Missing closing parenthesis after function '{token}'", code = "3009")
                    argument_wert = argument_baum.evaluate()
                    ScienceOp = f"{token}({argument_wert})"

                # Delegate to scientific engine; keep result as-is for Number()
                ergebnis_string = ScientificEngine.unknown_function(ScienceOp)
                try:
                    # berechneter_wert = fractions.Fraction(ergebnis_string)  # original idea (not used)
                    berechneter_wert = ergebnis_string
                    return Number(berechneter_wert)
                except ValueError:
                    raise E.SyntaxError(f"Error in scientific function: {ergebnis_string}", code = "3218")

        # Literals / variables
        elif isinstance(token, Decimal):
            return Number(token)
        elif isInt(token):
            return Number(token)
        elif isfloat(token):
            return Number(token)
        elif "var" in str(token):
            return Variable(token)
        else:
            raise E.SyntaxError(f"Unexpected token: {token}", code = "3012")

    def parse_unary(tokens):
        """Handle leading '+'/'-' (unary minus becomes 0 - operand)."""
        if tokens and tokens[0] in ('+', '-'):
            operator = tokens.pop(0)
            operand = parse_unary(tokens)

            if operator == '-':
                # Optimize for literal: -Number → Number(-value)
                if isinstance(operand, Number):
                    return Number(-operand.evaluate())
                return BinOp(Number('0'), '-', operand)
            else:
                return operand
        return parse_power(tokens)

    def parse_power(tokens):
        """Exponentiation '^' (handled before * and +)."""
        aktueller_baum = parse_factor(tokens)
        while tokens and tokens[0] in ("^"):
            operator = tokens.pop(0)
            rechtes_teil = parse_unary(tokens)
            if not isinstance(aktueller_baum, Variable) and not isinstance(rechtes_teil, Variable):
                # Pre-evaluate when both sides are numeric
                basis = aktueller_baum.evaluate()
                exponent = rechtes_teil.evaluate()
                ergebnis = basis ** exponent
                aktueller_baum = Number(ergebnis)
            else:
                # Keep as symbolic BinOp otherwise
                aktueller_baum = BinOp(aktueller_baum, operator, rechtes_teil)
        return aktueller_baum

    def parse_term(tokens):
        """Multiplication and division."""
        aktueller_baum = parse_unary(tokens)
        while tokens and tokens[0] in ("*","/"):
            operator = tokens.pop(0)
            rechtes_teil = parse_unary(tokens)
            aktueller_baum = BinOp(aktueller_baum, operator, rechtes_teil)
        return aktueller_baum

    def parse_sum(tokens):
        """Addition and subtraction."""
        aktueller_baum = parse_term(tokens)
        while tokens and tokens[0] in ("+", "-"):
            operator = tokens.pop(0)
            if debug == True:
                print("Currently at:" + str(operator) + "in parse_sum")
            rechte_seite = parse_term(tokens)
            aktueller_baum = BinOp(aktueller_baum, operator, rechte_seite)
        return aktueller_baum

    def parse_gleichung(tokens):
        """Optional '=' at the top level: build BinOp('=') when present."""
        linke_seite = parse_sum(tokens)
        if tokens and tokens[0] == "=":
            operator = tokens.pop(0)
            rechte_seite = parse_sum(tokens)
            return BinOp(linke_seite, operator, rechte_seite)
        return linke_seite

    # Build the final AST
    finaler_baum = parse_gleichung(analysed)

    # Decide if this is a CAS-style equation with <= 1 variable
    if isinstance(finaler_baum, BinOp) and finaler_baum.operator == '=' and var_counter <= 1:
        cas = True

    if debug == True:
        print("Final AST:")
        print(finaler_baum)

    # `cas` may or may not be set above; default to False
    cas = locals().get('cas', False)

    return finaler_baum, cas, var_counter


# -----------------------------
# Linear solver (one variable)
# -----------------------------

def solve(baum, var_name):
    """Solve (A*x + B) = (C*x + D) for x, or detect no/inf. solutions."""
    if not isinstance(baum, BinOp) or baum.operator != '=':
        raise E.SolverError("No valid equation to solve.", code = "3012")
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


# -----------------------------
# Result formatting
# -----------------------------

def cleanup(ergebnis):
    """Format a numeric result as Fraction or Decimal depending on settings.

    Returns:
        (rendered_value, rounding_flag)
    where rounding_flag indicates whether Decimal rounding occurred.
    """
    rounding = locals().get('rounding', False)

    target_decimals = config_manager.load_setting_value("decimal_places")
    target_fractions = config_manager.load_setting_value("fractions")

    # Try Fraction rendering if enabled and the result is Decimal
    if target_fractions == True and isinstance(ergebnis, Decimal):
        try:
            bruch_ergebnis = fractions.Fraction.from_decimal(ergebnis)
            gekuerzter_bruch = bruch_ergebnis.limit_denominator(100000)
            zaehler = gekuerzter_bruch.numerator
            nenner = gekuerzter_bruch.denominator
            if abs(zaehler) > nenner:
                # Mixed fraction form (e.g., 3/2 -> "1 1/2")
                ganzzahl = zaehler // nenner
                rest_zaehler = zaehler % nenner

                if rest_zaehler == 0:
                    return str(ganzzahl), rounding
                else:
                    # Adjust for negatives so that the remainder part is positive
                    if ganzzahl < 0 and rest_zaehler > 0:
                        ganzzahl += 1
                        rest_zaehler = abs(nenner - rest_zaehler)
                    return f"{ganzzahl} {rest_zaehler}/{nenner}", rounding

            return str(gekuerzter_bruch), rounding

        except Exception as e:
            # Surface as CalculationError (preserves UI error handling)
            raise E.CalculationError(f"Warning: Fraction conversion failed: {e}", code = "3024")

    if isinstance(ergebnis, Decimal):

        # --- Smarter Rounding Logic ---
        #
        # Handles rounding for Decimal results with dynamic precision.
        # Integers are returned as-is (just normalized),
        # while non-integers are rounded to 'target_decimals'.
        #
        # A temporary precision boost (prec=128) prevents
        # Decimal.InvalidOperation during quantize() for long or repeating numbers.
        # After rounding, precision is reset to the global standard (50).
        #

        if ergebnis % 1 == 0:
            # Integer result – return normalized without rounding
            return ergebnis.normalize(), rounding
        else:
            # Non-integer result (e.g. 1/3 or repeating decimals)
            getcontext().prec = 128  # Prevent quantize overflow

            if target_decimals >= 0:
                rundungs_muster = Decimal('1e-' + str(target_decimals))
            else:
                rundungs_muster = Decimal('1')

            gerundetes_ergebnis = ergebnis.quantize(rundungs_muster)
            getcontext().prec = 50  # Restore standard precision

            if gerundetes_ergebnis != ergebnis:
                rounding = True

            return gerundetes_ergebnis.normalize(), rounding


    # Legacy float/int handling (in case evaluation produced non-Decimal)
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

    # Fallback: unknown type, return as-is
    return ergebnis, rounding


# -----------------------------
# Public entry point
# -----------------------------

def calculate(problem):
    """Main API: parse → (evaluate | solve | equality-check) → format → render string."""
    # Guard precision locally before each calculation (UI may adjust as well)
    getcontext().prec = 50
    settings = config_manager.load_setting_value("all")
    var_list = []
    try:
        finaler_baum, cas, var_counter = ast(problem, settings)

        # Decide evaluation mode
        if cas and var_counter > 0:
            # Solve linear equation for first variable symbol in the token stream
            var_name_in_ast = "var0"
            ergebnis = solve(finaler_baum, var_name_in_ast)

        elif not cas and var_counter == 0:
            # Pure numeric evaluation
            ergebnis = finaler_baum.evaluate()

        elif cas and var_counter == 0:
            # Pure equality check (no variable): returns "= True/False"
            left_val = finaler_baum.left.evaluate()
            right_val = finaler_baum.right.evaluate()
            ausgabe_string = "True" if left_val == right_val else "False"
            return f"= {ausgabe_string}"

        else:
            # Mixed/invalid states with or without '=' and variables
            if cas:
                raise E.SolverError("The solver was used on a non-equation", code = "3005")
            elif not cas and not "=" in problem:
                raise E.SolverError("No '=' found, although a variable was specified.", code="3012")
            elif cas and "=" in problem and (
                    problem.index("=") == 0 or problem.index("=") == (len(problem) - 1)):
                raise E.SolverError("One of the sides is empty: " + str(problem), code = "3022")
            else:
                raise E.CalculationError("The calculator was called on an equation.", code="3015")

            return  # Unreachable, kept for clarity

        # Render result based on settings (fractions/decimals, rounding flag)
        ergebnis, rounding = cleanup(ergebnis)
        ungefaehr_zeichen = "\u2248"  # "≈"

        # Convert normalized result to string (Decimal supports to_normal_string)
        if isinstance(ergebnis, str) and '/' in ergebnis:
            ausgabe_string = ergebnis
        elif isinstance(ergebnis, Decimal):
            try:
                ausgabe_string = ergebnis.to_normal_string()
            except AttributeError:
                ausgabe_string = str(ergebnis)
        else:
            ausgabe_string = str(ergebnis)

        # Final display formatting
        if cas == True and rounding == True:
            return (f"x {ungefaehr_zeichen} " + ausgabe_string)
        elif cas == True and rounding == False:
            return ("x = " + ausgabe_string)
        elif rounding == True and not cas:
            return (f"{ungefaehr_zeichen} " + ausgabe_string)
        else:
            return ("= " + ausgabe_string)

    # Known numeric overflow
    except Overflow as e:
        raise E.CalculationError(
            message="Number too large (Arithmetic overflow).",
            code="3026",
            equation=problem
        )
    # Re-raise our domain errors after attaching the source equation
    except E.MathError as e:
        e.equation = problem
        raise e
    # Convert unexpected Python exceptions to our unified error type
    except (ValueError, SyntaxError, ZeroDivisionError, TypeError, Exception) as e:
        error_message = str(e).strip()
        parts = error_message.split(maxsplit=1)
        code = "9999"
        message = error_message

        # If an error string already begins with a 4-digit code, respect it
        if parts and parts[0].isdigit() and len(parts[0]) == 4:
            code = parts[0]
            if len(parts) > 1:
                message = parts[1]
        raise E.MathError(message=message, code=code, equation=problem)


def test_main():
    """Simple REPL-like runner for manual testing of the engine."""
    print("Enter the problem: ")
    problem = input()
    ergebnis = calculate(problem)
    print(ergebnis)
    # test_main()  # recursive call disabled


if __name__ == "__main__":
    # Allow running this module directly for quick CLI tests:
    #   python -m Modules.MathEngine   (depending on your package path)
    test_main()
