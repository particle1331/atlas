def parse_ini(text: str) -> dict[str, dict[str, str]]:
    result = {"DEFAULT": {}}
    current = "DEFAULT"
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("["):
            if not line.endswith("]"):
                raise ValueError(f"malformed section: {raw_line!r}")
            name = line[1:-1].strip()
            if not name:
                raise ValueError("empty section name")
            if name in result and name != "DEFAULT":
                raise ValueError(f"duplicate section: {name}")
            result[name] = {}
            current = name
            continue
        if "=" not in line:
            raise ValueError(f"malformed line: {raw_line!r}")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError("empty key")
        if value.startswith('"'):
            if not value.endswith('"') or len(value) < 2:
                raise ValueError("unterminated quoted value")
            value = value[1:-1]
            chars = []
            index = 0
            escapes = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
            while index < len(value):
                char = value[index]
                if char == "\\":
                    index += 1
                    if index >= len(value) or value[index] not in escapes:
                        raise ValueError("invalid escape")
                    chars.append(escapes[value[index]])
                else:
                    chars.append(char)
                index += 1
            value = "".join(chars)
        else:
            for marker in ("#", ";"):
                if marker in value:
                    value = value.split(marker, 1)[0].rstrip()
        result[current][key] = value
    return result
