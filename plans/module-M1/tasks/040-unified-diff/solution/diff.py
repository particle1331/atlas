def _operations(a: list[str], b: list[str]):
    rows = len(a)
    columns = len(b)
    table = [[0] * (columns + 1) for _ in range(rows + 1)]
    for row in range(rows - 1, -1, -1):
        for column in range(columns - 1, -1, -1):
            if a[row] == b[column]:
                table[row][column] = 1 + table[row + 1][column + 1]
            else:
                table[row][column] = max(
                    table[row + 1][column], table[row][column + 1]
                )

    operations = []
    row = column = 0
    while row < rows and column < columns:
        if a[row] == b[column]:
            operations.append((" ", a[row]))
            row += 1
            column += 1
        elif table[row + 1][column] >= table[row][column + 1]:
            operations.append(("-", a[row]))
            row += 1
        else:
            operations.append(("+", b[column]))
            column += 1
    while row < rows:
        operations.append(("-", a[row]))
        row += 1
    while column < columns:
        operations.append(("+", b[column]))
        column += 1
    return operations


def _groups(operations, context: int):
    changes = [
        index for index, (tag, _) in enumerate(operations) if tag != " "
    ]
    if not changes:
        return []
    groups = []
    first = last = changes[0]
    for index in changes[1:]:
        if index - last - 1 > 2 * context:
            groups.append((first, last))
            first = index
        last = index
    groups.append((first, last))
    return [
        (max(0, start - context), min(len(operations), end + context + 1))
        for start, end in groups
    ]


def _counts(operations, start: int, end: int):
    old_before = sum(
        1 for tag, _ in operations[:start] if tag in (" ", "-")
    )
    new_before = sum(
        1 for tag, _ in operations[:start] if tag in (" ", "+")
    )
    old_count = sum(1 for tag, _ in operations[start:end] if tag in (" ", "-"))
    new_count = sum(1 for tag, _ in operations[start:end] if tag in (" ", "+"))
    old_start = old_before + 1 if old_count else old_before
    new_start = new_before + 1 if new_count else new_before
    return old_start, old_count, new_start, new_count


def unified_diff(a: list[str], b: list[str], context: int = 3) -> str:
    if context < 0:
        raise ValueError("context must not be negative")
    operations = _operations(a, b)
    groups = _groups(operations, context)
    if not groups:
        return ""
    lines = ["--- a", "+++ b"]
    for start, end in groups:
        old_start, old_count, new_start, new_count = _counts(
            operations, start, end
        )
        lines.append(
            f"@@ -{old_start},{old_count} +{new_start},{new_count} @@"
        )
        for tag, text in operations[start:end]:
            lines.append(tag + text)
    return "\n".join(lines)
