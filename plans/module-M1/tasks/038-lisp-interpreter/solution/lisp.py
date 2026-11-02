class Symbol(str):
    pass


def tokenize(source: str) -> list[str]:
    tokens = []
    index = 0
    while index < len(source):
        char = source[index]
        if char.isspace():
            index += 1
            continue
        if char == ";":
            while index < len(source) and source[index] != "\n":
                index += 1
            continue
        if char in "()'":
            tokens.append(char)
            index += 1
            continue
        end = index
        while (
            end < len(source)
            and not source[end].isspace()
            and source[end] not in "()'"
        ):
            end += 1
        tokens.append(source[index:end])
        index = end
    return tokens


def atom(token: str):
    if token == "#t":
        return True
    if token == "#f":
        return False
    try:
        return int(token)
    except ValueError:
        return Symbol(token)


def parse_all(tokens: list[str]):
    def parse_expr(index: int):
        if index >= len(tokens):
            raise ValueError("unexpected end of input")
        token = tokens[index]
        if token == "(":
            items = []
            index += 1
            while True:
                if index >= len(tokens):
                    raise ValueError("missing ')'")
                if tokens[index] == ")":
                    return items, index + 1
                item, index = parse_expr(index)
                items.append(item)
        if token == ")":
            raise ValueError("unexpected ')'")
        if token == "'":
            item, index = parse_expr(index + 1)
            return [Symbol("quote"), item], index
        return atom(token), index + 1

    expressions = []
    index = 0
    while index < len(tokens):
        expression, index = parse_expr(index)
        expressions.append(expression)
    return expressions


class Env(dict):
    def __init__(self, params=(), args=(), outer=None) -> None:
        super().__init__(zip(params, args))
        self.outer = outer

    def find(self, name):
        if name in self:
            return self
        if self.outer is not None:
            return self.outer.find(name)
        raise ValueError(f"unbound symbol: {name}")

    def lookup(self, name):
        return self.find(name)[name]


def make_lambda(params, body, env):
    def function(*args):
        if len(args) != len(params):
            raise ValueError("wrong number of arguments")
        local = Env(params, args, env)
        result = None
        for expression in body:
            result = evaluate_expression(expression, local)
        return result

    return function


def divide(first, rest):
    value = first
    for item in rest:
        if item == 0:
            raise ValueError("division by zero")
        value /= item
    return value


def subtract(first, rest):
    value = first
    for item in rest:
        value -= item
    return value


def car(items):
    if not items:
        raise ValueError("car of empty list")
    return items[0]


def cdr(items):
    if not items:
        raise ValueError("cdr of empty list")
    return items[1:]


def standard_env() -> Env:
    env = Env()
    env.update(
        {
            "+": lambda *items: sum(items),
            "-": lambda first, *rest: subtract(first, rest),
            "*": lambda *items: __import__("math").prod(items),
            "/": lambda first, *rest: divide(first, rest),
            "<": lambda left, right: left < right,
            "<=": lambda left, right: left <= right,
            "=": lambda left, right: left == right,
            ">": lambda left, right: left > right,
            ">=": lambda left, right: left >= right,
            "list": lambda *items: list(items),
            "car": car,
            "cdr": cdr,
            "cons": lambda item, items: [item] + items,
            "null?": lambda items: items == [],
            "not": lambda value: value is False,
        }
    )
    return env


def evaluate_expression(expression, env):
    if isinstance(expression, Symbol):
        return env.lookup(expression)
    if not isinstance(expression, list):
        return expression
    if not expression:
        raise ValueError("cannot evaluate empty list")
    head = expression[0]
    if head == "quote":
        if len(expression) != 2:
            raise ValueError("quote expects one argument")
        return expression[1]
    if head == "if":
        if len(expression) not in (3, 4):
            raise ValueError("if expects two or three arguments")
        condition = evaluate_expression(expression[1], env)
        if condition is not False:
            return evaluate_expression(expression[2], env)
        if len(expression) == 4:
            return evaluate_expression(expression[3], env)
        return None
    if head == "define":
        if len(expression) < 3:
            raise ValueError("define needs a name and value")
        target = expression[1]
        if isinstance(target, list):
            if not target or not isinstance(target[0], Symbol):
                raise ValueError("bad define target")
            env[target[0]] = make_lambda(target[1:], expression[2:], env)
        else:
            if len(expression) != 3:
                raise ValueError("define expects one value")
            env[target] = evaluate_expression(expression[2], env)
        return None
    if head == "lambda":
        if len(expression) < 3:
            raise ValueError("lambda needs parameters and a body")
        params = expression[1]
        if not isinstance(params, list) or not all(
            isinstance(param, Symbol) for param in params
        ):
            raise ValueError("bad lambda parameters")
        return make_lambda(params, expression[2:], env)
    if head == "let":
        if len(expression) < 3 or not isinstance(expression[1], list):
            raise ValueError("bad let")
        local = Env(outer=env)
        for binding in expression[1]:
            if (
                not isinstance(binding, list)
                or len(binding) != 2
                or not isinstance(binding[0], Symbol)
            ):
                raise ValueError("bad let binding")
            local[binding[0]] = evaluate_expression(binding[1], env)
        result = None
        for body_expression in expression[2:]:
            result = evaluate_expression(body_expression, local)
        return result
    if head == "begin":
        result = None
        for body_expression in expression[1:]:
            result = evaluate_expression(body_expression, env)
        return result

    function = evaluate_expression(head, env)
    arguments = [
        evaluate_expression(argument, env) for argument in expression[1:]
    ]
    if not callable(function):
        raise ValueError("not a function")
    return function(*arguments)


def evaluate(source: str):
    tokens = tokenize(source)
    if not tokens:
        raise ValueError("empty program")
    expressions = parse_all(tokens)
    env = standard_env()
    result = None
    for expression in expressions:
        result = evaluate_expression(expression, env)
    return result
