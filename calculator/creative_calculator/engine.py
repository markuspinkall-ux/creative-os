"""Rechenwerk des Creative Calculator.

Rechnet exakt mit Dezimalzahlen (0,1 + 0,2 = 0,3 – nicht 0,30000000004),
deutsch mit Komma, Punkt vor Strich, Klammern, Prozent wie bei Windows:
  200 + 10 %  = 220        (10 % von 200 dazu)
  200 × 10 %  = 20
  50 %        = 0,5
Kein eval(): ein eigener kleiner Parser, damit nur gerechnet wird.
"""

from decimal import Decimal, DivisionByZero, InvalidOperation, Overflow, getcontext

getcontext().prec = 34

OPS = {"+": "+", "-": "-", "−": "-", "*": "*", "×": "*", "x": "*", "/": "/", "÷": "/", ":": "/"}


class CalcError(Exception):
    pass


def tokenize(text):
    tokens, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace() or c == "'" or c == " ":
            i += 1
            continue
        if c.isdigit() or c in ",.":
            j, seen_comma = i, False
            while j < n and (text[j].isdigit() or text[j] in ",." or text[j] == " "):
                if text[j] in ",.":
                    if seen_comma:
                        raise CalcError("Zahl mit zwei Kommas")
                    seen_comma = True
                j += 1
            raw = text[i:j].replace(" ", "").replace(",", ".")
            if raw == ".":
                raise CalcError("Komma ohne Zahl")
            tokens.append(("num", Decimal(raw)))
            i = j
            continue
        if c in OPS:
            tokens.append(("op", OPS[c]))
        elif c in "()%":
            tokens.append((c, c))
        elif c == "^":
            tokens.append(("op", "^"))
        elif c == "√":
            tokens.append(("sqrt", c))
        else:
            raise CalcError(f"Unbekanntes Zeichen „{c}“")
        i += 1
    return tokens


class Parser:
    def __init__(self, tokens, partial=False):
        self.t, self.i, self.partial = tokens, 0, partial

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def parse(self):
        if not self.t:
            raise CalcError("leer")
        value = self.expr()
        if self.i < len(self.t):
            raise CalcError("Ausdruck unvollständig")
        return value

    # expr := term (('+'|'-') term ['%'])*
    def expr(self):
        left = self.term()
        while self.peek() in (("op", "+"), ("op", "-")):
            op = self.take()[1]
            right, percent = self.term(percent_aware=True)
            if percent:                                     # 200 + 10 % → 200 + 20
                right = left * right / 100
            left = left + right if op == "+" else left - right
        return left

    # term := power (('*'|'/') power)*
    def term(self, percent_aware=False):
        value, percent = self.power()
        while self.peek() in (("op", "*"), ("op", "/")):
            op = self.take()[1]
            right, p2 = self.power()
            if p2:
                right = right / 100
            if op == "*":
                value = value * right
            else:
                if right == 0:
                    raise CalcError("Teilen durch 0 geht nicht")
                value = value / right
            percent = False
        if percent_aware:
            return value, percent
        return value / 100 if percent else value

    # power := unary ['^' power] ['%']
    def power(self):
        base = self.unary()
        if self.peek() == ("op", "^"):
            self.take()
            exp, p = self.power()
            if p:
                exp = exp / 100
            try:
                if exp == exp.to_integral_value() and abs(exp) <= 10000:
                    base = base ** int(exp)
                else:
                    if base < 0:
                        raise CalcError("Ungültige Eingabe")
                    base = Decimal(float(base) ** float(exp))
            except (Overflow, OverflowError):
                raise CalcError("Zahl zu groß")
        percent = False
        if self.peek()[0] == "%":
            self.take()
            percent = True
        return base, percent

    def unary(self):
        tok = self.peek()
        if tok == ("op", "-"):
            self.take()
            v, p = self.power()
            return -(v / 100 if p else v)
        if tok == ("op", "+"):
            self.take()
            v, p = self.power()
            return v / 100 if p else v
        if tok[0] == "sqrt":
            self.take()
            v, p = self.power()
            v = v / 100 if p else v
            if v < 0:
                raise CalcError("Wurzel aus einer negativen Zahl geht nicht")
            return v.sqrt()
        return self.atom()

    def atom(self):
        kind, val = self.take()
        if kind == "num":
            return val
        if kind == "(":
            v = self.expr()
            if self.peek()[0] == ")":
                self.take()
            elif not self.partial:
                raise CalcError("Klammer nicht geschlossen")
            return v
        raise CalcError("Ausdruck unvollständig")


def evaluate(text, partial=False):
    """Rechnet `text` aus. partial=True: offene Klammern sind erlaubt (Vorschau)."""
    try:
        return Parser(tokenize(text), partial=partial).parse()
    except (DivisionByZero, ZeroDivisionError):
        raise CalcError("Teilen durch 0 geht nicht")
    except (InvalidOperation, Overflow, OverflowError):
        raise CalcError("Ungültige Eingabe")
    except RecursionError:
        raise CalcError("Zu viele Klammern")


def format_number(value, group=True):
    """Deutsche Schreibweise: 1 234 567,89 – lange Zahlen wissenschaftlich."""
    if value.is_nan() or value.is_infinite():
        return "Fehler"
    q = value.normalize()
    if q == 0:
        return "0"
    if abs(q) >= Decimal("1e16") or abs(q) < Decimal("1e-10"):
        s = f"{q:.10E}"
        mant, exp = s.split("E")
        mant = mant.rstrip("0").rstrip(".").replace(".", ",")
        return f"{mant} × 10^{int(exp)}".replace("-", "−")
    q = q.quantize(Decimal(1).scaleb(-max(0, min(14, 15 - q.adjusted() - 1)))) if q.adjusted() < 15 else q
    s = format(q.normalize(), "f")
    sign = "−" if s.startswith("-") else ""
    s = s.lstrip("-")
    whole, _, frac = s.partition(".")
    if group and len(whole) > 4:
        parts = []
        while len(whole) > 3:
            parts.insert(0, whole[-3:])
            whole = whole[:-3]
        parts.insert(0, whole)
        whole = " ".join(parts)          # schmales Leerzeichen als Tausender-Trenner
    frac = frac.rstrip("0")
    return sign + whole + ("," + frac if frac else "")
