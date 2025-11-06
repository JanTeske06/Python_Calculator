# ScientificEngine
import math


degree_setting_sincostan = 0  # 0 = number, 1 = degrees







def isPi(problem):
    if problem == "π" or problem.lower() == "pi":
        return math.pi
    else:
        return False


def isSCT(problem):  # Sin / Cos / Tan
    if "sin" in problem or "cos" in problem or "tan" in problem:
        start_index = problem.find('(')
        end_index = problem.find(')')

        if "sin" in problem:
            clean_number = float(problem[start_index + 1: end_index])
            if degree_setting_sincostan == 1:
                clean_number = math.radians(clean_number)
            return math.sin(clean_number)

        elif "cos" in problem:
            clean_number = float(problem[start_index + 1: end_index])
            if degree_setting_sincostan == 1:
                clean_number = math.radians(clean_number)
            return math.cos(clean_number)

        elif "tan" in problem:
            clean_number = float(problem[start_index + 1: end_index])
            if degree_setting_sincostan == 1:
                clean_number = math.radians(clean_number)
            return math.tan(clean_number)



        else:
            print("Error. Sin/Cos/tan wurde erkannt, aber konnte nicht zugeordnet werden.")
    else:
        return False


def isLog(problem):
    if "log" in problem:
        start_index = problem.find('(')
        end_index = problem.find(')')
        if start_index == -1 or end_index == -1 or start_index >= end_index:
            return "FEHLER: Logarithmus-Syntax."

        content = problem[start_index + 1: end_index]

        number = 0.0
        base = 0.0
        ergebnis = "FEHLER: Unbekannter Logarithmusfehler."

        try:
            if "," in content:
                number_str, base_str = content.split(',', 1)
                number = float(number_str.strip())
                base = float(base_str.strip())
            else:
                number = float(content.strip())
                base = 0.0

            if base == 0.0:
                ergebnis = math.log(number)
            else:
                ergebnis = math.log(number, base)

        except ValueError:
            return "FEHLER: Ungültige Zahl oder Basis im Logarithmus."
        except Exception as e:
            return f"FEHLER: Logarithmus-Berechnung: {e}"

        return ergebnis
    else:
        return False


def isE(problem):
    if "e" in problem:
        start_index = problem.find('(')
        end_index = problem.find(')')
        clean_number = problem[start_index + 1: end_index]
        ergebnis = math.exp(float(clean_number))
        return ergebnis
    else:
        return False


def isRoot(problem):
    if "√" in problem:
        start_index = problem.find('(')
        end_index = problem.find(')')
        clean_number = problem[start_index + 1: end_index]
        ergebnis = math.sqrt(float(clean_number))
        return ergebnis
    else:
        return False


def test_main():
    print("Gebe das Problem ein: ")
    received_string = input()

    if received_string == "π" or received_string.lower() == "pi":
            ergebnis = isPi()


    elif "sin" in received_string or "cos" in received_string or "tan" in received_string:
            ergebnis = isSCT(received_string)

    elif "log" in received_string:
            ergebnis = isLog(received_string)

    elif "√" in received_string:
            ergebnis = isRoot(received_string)

    elif "e" in received_string:
            ergebnis = isE(received_string)


    else:
        ergebnis = (f"Error. Konnte keine Operation zuordnen. Received String:" + str(received_string))

    print(ergebnis)


def unknown_function(received_string):

    if received_string == "π" or received_string.lower() == "pi":
        ergebnis = isPi()


    elif "sin" in received_string or "cos" in received_string or "tan" in received_string:
        ergebnis = isSCT(received_string)

    elif "log" in received_string:
        ergebnis = isLog(received_string)

    elif "√" in received_string:
        ergebnis = isRoot(received_string)

    elif "e" in received_string:
        ergebnis = isE(received_string)


    else:
        ergebnis = False

    return  ergebnis



if __name__ == "__main__":
    test_main()
