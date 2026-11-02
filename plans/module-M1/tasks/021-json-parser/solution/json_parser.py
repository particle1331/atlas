class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def parse(self):
        value = self.value()
        self.ws()
        if self.pos != len(self.text):
            raise ValueError("trailing data")
        return value

    def ws(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] in " \t\n\r":
            self.pos += 1

    def peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def expect(self, char: str) -> None:
        if self.peek() != char:
            raise ValueError(f"expected {char!r}")
        self.pos += 1

    def value(self):
        self.ws()
        char = self.peek()
        if char == "{":
            return self.object()
        if char == "[":
            return self.array()
        if char == '"':
            return self.string()
        if char == "t":
            self.literal("true")
            return True
        if char == "f":
            self.literal("false")
            return False
        if char == "n":
            self.literal("null")
            return None
        if char == "-" or char.isdigit():
            return self.number()
        raise ValueError("expected a value")

    def literal(self, word: str) -> None:
        if not self.text.startswith(word, self.pos):
            raise ValueError(f"expected {word}")
        self.pos += len(word)

    def object(self) -> dict:
        result = {}
        self.expect("{")
        self.ws()
        if self.peek() == "}":
            self.pos += 1
            return result
        while True:
            self.ws()
            if self.peek() != '"':
                raise ValueError("expected object key")
            key = self.string()
            self.ws()
            self.expect(":")
            result[key] = self.value()
            self.ws()
            char = self.peek()
            if char == "}":
                self.pos += 1
                return result
            if char != ",":
                raise ValueError("expected ',' or '}'")
            self.pos += 1
            self.ws()
            if self.peek() == "}":
                raise ValueError("trailing comma")

    def array(self) -> list:
        result = []
        self.expect("[")
        self.ws()
        if self.peek() == "]":
            self.pos += 1
            return result
        while True:
            result.append(self.value())
            self.ws()
            char = self.peek()
            if char == "]":
                self.pos += 1
                return result
            if char != ",":
                raise ValueError("expected ',' or ']'")
            self.pos += 1
            self.ws()
            if self.peek() == "]":
                raise ValueError("trailing comma")

    def string(self) -> str:
        self.expect('"')
        chars = []
        while True:
            if self.pos >= len(self.text):
                raise ValueError("unterminated string")
            char = self.text[self.pos]
            self.pos += 1
            if char == '"':
                return "".join(chars)
            if char != "\\":
                chars.append(char)
                continue
            if self.pos >= len(self.text):
                raise ValueError("unterminated escape")
            escape = self.text[self.pos]
            self.pos += 1
            simple = {
                '"': '"', "\\": "\\", "/": "/", "b": "\b",
                "f": "\f", "n": "\n", "r": "\r", "t": "\t",
            }
            if escape in simple:
                chars.append(simple[escape])
            elif escape == "u":
                digits = self.text[self.pos : self.pos + 4]
                if len(digits) != 4 or any(c not in "0123456789abcdefABCDEF" for c in digits):
                    raise ValueError("invalid unicode escape")
                chars.append(chr(int(digits, 16)))
                self.pos += 4
            else:
                raise ValueError("invalid escape")

    def number(self):
        start = self.pos
        if self.peek() == "-":
            self.pos += 1
        if self.peek() == "0":
            self.pos += 1
            if self.peek().isdigit():
                raise ValueError("leading zero")
        elif self.peek().isdigit():
            while self.peek().isdigit():
                self.pos += 1
        else:
            raise ValueError("invalid number")
        is_float = False
        if self.peek() == ".":
            is_float = True
            self.pos += 1
            if not self.peek().isdigit():
                raise ValueError("invalid fraction")
            while self.peek().isdigit():
                self.pos += 1
        if self.peek() and self.peek() in "eE":
            is_float = True
            self.pos += 1
            if self.peek() and self.peek() in "+-":
                self.pos += 1
            if not self.peek().isdigit():
                raise ValueError("invalid exponent")
            while self.peek().isdigit():
                self.pos += 1
        raw = self.text[start : self.pos]
        return float(raw) if is_float else int(raw)


def parse_json(text: str):
    return _Parser(text).parse()
