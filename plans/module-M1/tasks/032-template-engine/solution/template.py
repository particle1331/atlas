import re


TAG = re.compile(r"\{\{(.*?)\}\}")


def _lookup(path: str, context: dict):
    value = context
    for part in path.split("."):
        part = part.strip()
        if not isinstance(value, dict) or part not in value:
            raise KeyError(path)
        value = value[part]
    return value


def render(template: str, context: dict) -> str:
    if template.count("{{") != template.count("}}"):
        raise ValueError("malformed tag")

    def replace(match):
        body = match.group(1).strip()
        if not body:
            raise ValueError("empty tag")
        parts = [part.strip() for part in body.split("|")]
        if len(parts) > 2 or any(not part for part in parts):
            raise ValueError("malformed tag")
        value = _lookup(parts[0], context)
        if len(parts) == 2:
            if parts[1] == "upper":
                value = str(value).upper()
            elif parts[1] == "lower":
                value = str(value).lower()
            else:
                raise ValueError(f"unknown filter: {parts[1]}")
        return str(value)

    return TAG.sub(replace, template)
