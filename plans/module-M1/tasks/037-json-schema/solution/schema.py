import re


def _type_matches(value, name: str) -> bool:
    if name == "object":
        return isinstance(value, dict)
    if name == "array":
        return isinstance(value, list)
    if name == "string":
        return isinstance(value, str)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "null":
        return value is None
    raise ValueError(f"unknown type: {name}")


def _key_path(path: str, key: str) -> str:
    if path == "$":
        return f"$.{key}"
    return f"{path}.{key}"


def _index_path(path: str, index: int) -> str:
    return f"{path}[{index}]"


def validate(instance, schema, path: str = "$") -> list[str]:
    if not isinstance(schema, dict):
        raise ValueError("schema must be an object")
    errors = []

    if "type" in schema:
        types = schema["type"]
        if isinstance(types, str):
            types = [types]
        if not any(_type_matches(instance, name) for name in types):
            return [f"{path}: type"]

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: enum")

    if isinstance(instance, dict):
        if any(key not in instance for key in schema.get("required", [])):
            errors.append(f"{path}: required")
        properties = schema.get("properties", {})
        for key, subschema in properties.items():
            if key in instance:
                errors.extend(
                    validate(instance[key], subschema, _key_path(path, key))
                )
        additional = schema.get("additionalProperties", True)
        extras = [key for key in instance if key not in properties]
        if additional is False and extras:
            errors.append(f"{path}: additionalProperties")
        elif isinstance(additional, dict):
            for key in extras:
                errors.extend(
                    validate(instance[key], additional, _key_path(path, key))
                )

    if isinstance(instance, list) and "items" in schema:
        for index, item in enumerate(instance):
            errors.extend(
                validate(item, schema["items"], _index_path(path, index))
            )

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: minLength")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: maxLength")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            errors.append(f"{path}: pattern")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: minimum")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: maximum")

    for subschema in schema.get("allOf", []):
        errors.extend(validate(instance, subschema, path))

    if "anyOf" in schema:
        if not any(
            not validate(instance, subschema, path)
            for subschema in schema["anyOf"]
        ):
            errors.append(f"{path}: anyOf")

    if "oneOf" in schema:
        matches = sum(
            1
            for subschema in schema["oneOf"]
            if not validate(instance, subschema, path)
        )
        if matches != 1:
            errors.append(f"{path}: oneOf")

    return sorted(errors)
