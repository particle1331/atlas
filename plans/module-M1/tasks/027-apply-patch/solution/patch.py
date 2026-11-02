import re


HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@$")


def apply_patch(original: str, patch: str) -> str:
    lines = patch.splitlines()
    if len(lines) < 3 or not lines[0].startswith("--- ") or not lines[1].startswith("+++ "):
        raise ValueError("malformed patch header")
    hunks = [index for index, line in enumerate(lines) if line.startswith("@@")]
    if len(hunks) != 1:
        raise ValueError("patch must contain exactly one hunk")
    match = HUNK.match(lines[hunks[0]])
    if not match:
        raise ValueError("malformed hunk header")
    old_start = int(match.group(1))
    hunk_lines = lines[hunks[0] + 1 :]
    if not hunk_lines:
        raise ValueError("empty hunk")
    source = original.split("\n")
    position = old_start - 1
    if position < 0 or position > len(source):
        raise ValueError("hunk starts outside the file")
    output = source[:position]
    index = position
    for line in hunk_lines:
        if not line:
            raise ValueError("malformed hunk line")
        tag, text = line[0], line[1:]
        if tag == " ":
            if index >= len(source) or source[index] != text:
                raise ValueError("context mismatch")
            output.append(source[index])
            index += 1
        elif tag == "-":
            if index >= len(source) or source[index] != text:
                raise ValueError("removal mismatch")
            index += 1
        elif tag == "+":
            output.append(text)
        else:
            raise ValueError(f"invalid hunk line: {line!r}")
    output.extend(source[index:])
    return "\n".join(output)
