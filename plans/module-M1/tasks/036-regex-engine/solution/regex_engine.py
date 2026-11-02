class _Parser:
    def __init__(self, pattern: str) -> None:
        self.pattern = pattern
        self.pos = 0

    def peek(self) -> str:
        if self.pos >= len(self.pattern):
            return ""
        return self.pattern[self.pos]

    def parse(self):
        node = self.alt()
        if self.pos != len(self.pattern):
            raise ValueError("unexpected ')'")
        return node

    def alt(self):
        branches = [self.concat()]
        while self.peek() == "|":
            self.pos += 1
            branches.append(self.concat())
        if len(branches) == 1:
            return branches[0]
        return ("alt", branches)

    def concat(self):
        nodes = []
        while self.pos < len(self.pattern) and self.peek() not in "|)":
            nodes.append(self.repeat())
        if not nodes:
            raise ValueError("empty branch")
        if len(nodes) == 1:
            return nodes[0]
        return ("concat", nodes)

    def repeat(self):
        node = self.atom()
        quantifier = self.peek()
        if quantifier in ("*", "+", "?"):
            self.pos += 1
            if self.peek() in ("*", "+", "?"):
                raise ValueError("double quantifier")
            if quantifier == "*":
                return ("repeat", node, 0, None)
            if quantifier == "+":
                return ("repeat", node, 1, None)
            return ("repeat", node, 0, 1)
        return node

    def atom(self):
        char = self.peek()
        if not char:
            raise ValueError("unexpected end of pattern")
        if char == "(":
            self.pos += 1
            node = self.alt()
            if self.peek() != ")":
                raise ValueError("missing ')'")
            self.pos += 1
            return node
        if char == "[":
            return self.char_class()
        if char == ".":
            self.pos += 1
            return ("any",)
        if char == "^":
            self.pos += 1
            return ("start",)
        if char == "$":
            self.pos += 1
            return ("end",)
        if char == "\\":
            self.pos += 1
            escape = self.peek()
            if not escape:
                raise ValueError("dangling escape")
            self.pos += 1
            if escape == "d":
                return ("class", set("0123456789"), False)
            if escape == "w":
                return (
                    "class",
                    set(
                        "abcdefghijklmnopqrstuvwxyz"
                        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                        "0123456789_"
                    ),
                    False,
                )
            if escape == "s":
                return ("class", set(" \t\n\r\f\v"), False)
            if escape in ".\\|()[]*+?^$":
                return ("char", escape)
            raise ValueError("invalid escape: \\" + escape)
        if char in "*+?":
            raise ValueError("dangling quantifier")
        if char == ")":
            raise ValueError("unexpected ')'")
        self.pos += 1
        return ("char", char)

    def char_class(self):
        self.pos += 1
        negated = False
        if self.peek() == "^":
            negated = True
            self.pos += 1
        chars = set()
        first = True
        while True:
            char = self.peek()
            if not char:
                raise ValueError("unterminated character class")
            if char == "]" and not first:
                self.pos += 1
                break
            first = False
            if char == "\\":
                self.pos += 1
                escape = self.peek()
                if not escape:
                    raise ValueError("dangling escape")
                self.pos += 1
                if escape == "d":
                    chars.update("0123456789")
                elif escape == "w":
                    chars.update(
                        "abcdefghijklmnopqrstuvwxyz"
                        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                        "0123456789_"
                    )
                elif escape == "s":
                    chars.update(" \t\n\r\f\v")
                elif escape in "\\]-^":
                    chars.add(escape)
                else:
                    raise ValueError("invalid escape: \\" + escape)
                continue
            self.pos += 1
            if (
                self.peek() == "-"
                and self.pos + 1 < len(self.pattern)
                and self.pattern[self.pos + 1] != "]"
            ):
                self.pos += 1
                end = self.peek()
                if not end or end == "]":
                    raise ValueError("invalid range")
                if end == "\\":
                    raise ValueError("escaped range end is not supported")
                self.pos += 1
                if ord(char) > ord(end):
                    raise ValueError("invalid range")
                chars.update(chr(code) for code in range(ord(char), ord(end) + 1))
            else:
                chars.add(char)
        if not chars:
            raise ValueError("empty character class")
        return ("class", chars, negated)


def _repeat(node, text: str, pos: int, minimum: int, maximum):
    if maximum is None or maximum > 0:
        for next_pos in _match(node, text, pos):
            if next_pos == pos:
                continue
            yield from _repeat(
                node,
                text,
                next_pos,
                max(0, minimum - 1),
                None if maximum is None else maximum - 1,
            )
    if minimum == 0:
        yield pos


def _match(node, text: str, pos: int):
    kind = node[0]
    if kind == "char":
        if pos < len(text) and text[pos] == node[1]:
            yield pos + 1
    elif kind == "any":
        if pos < len(text) and text[pos] != "\n":
            yield pos + 1
    elif kind == "class":
        if pos < len(text) and ((text[pos] in node[1]) != node[2]):
            yield pos + 1
    elif kind == "start":
        if pos == 0:
            yield pos
    elif kind == "end":
        if pos == len(text):
            yield pos
    elif kind == "concat":
        positions = [pos]
        for child in node[1]:
            next_positions = []
            for current in positions:
                next_positions.extend(_match(child, text, current))
            positions = next_positions
            if not positions:
                return
        yield from positions
    elif kind == "alt":
        for branch in node[1]:
            yield from _match(branch, text, pos)
    elif kind == "repeat":
        yield from _repeat(node[1], text, pos, node[2], node[3])
    else:
        raise ValueError("unknown node")


def fullmatch(pattern: str, text: str) -> bool:
    if not isinstance(pattern, str) or not isinstance(text, str):
        raise ValueError("pattern and text must be strings")
    node = _Parser(pattern).parse()
    return any(end == len(text) for end in _match(node, text, 0))
