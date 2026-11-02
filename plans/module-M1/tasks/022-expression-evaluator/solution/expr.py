class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def parse(self) -> float:
        value = self.expr()
        self.ws()
        if self.pos != len(self.text):
            raise ValueError("trailing input")
        return value

    def ws(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def expr(self) -> float:
        value = self.term()
        while True:
            self.ws()
            char = self.peek()
            if char == "+":
                self.pos += 1
                value += self.term()
            elif char == "-":
                self.pos += 1
                value -= self.term()
            else:
                return value

    def term(self) -> float:
        value = self.unary()
        while True:
            self.ws()
            char = self.peek()
            if char == "*":
                self.pos += 1
                value *= self.unary()
            elif char == "/":
                self.pos += 1
                divisor = self.unary()
                if divisor == 0:
                    raise ValueError("division by zero")
                value /= divisor
            elif char == "%":
                self.pos += 1
                divisor = self.unary()
                if divisor == 0:
                    raise ValueError("division by zero")
                value %= divisor
            else:
                return value

    def unary(self) -> float:
        self.ws()
        if self.peek() == "+":
            self.pos += 1
            return self.unary()
        if self.peek() == "-":
            self.pos += 1
            return -self.unary()
        return self.power()

    def power(self) -> float:
        value = self.primary()
        self.ws()
        if self.peek() == "^":
            self.pos += 1
            return value ** self.unary()
        return value

    def primary(self) -> float:
        self.ws()
        if self.peek() == "(":
            self.pos += 1
            value = self.expr()
            self.ws()
            if self.peek() != ")":
                raise ValueError("missing ')'")
            self.pos += 1
            return value
        start = self.pos
        if not self.peek().isdigit():
            raise ValueError("expected a number")
        while self.peek().isdigit():
            self.pos += 1
        if self.peek() == ".":
            self.pos += 1
            if not self.peek().isdigit():
                raise ValueError("invalid number")
            while self.peek().isdigit():
                self.pos += 1
        return float(self.text[start : self.pos])


def evaluate(expr: str) -> float:
    if not isinstance(expr, str) or not expr.strip():
        raise ValueError("empty expression")
    return _Parser(expr).parse()
