def parse_csv(text: str) -> list[list[str]]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    rows = []
    row = []
    field = []
    in_quotes = False
    after_quote = False
    index = 0

    def end_field() -> None:
        nonlocal field, after_quote
        row.append("".join(field))
        field = []
        after_quote = False

    def end_row() -> None:
        nonlocal row
        end_field()
        rows.append(row)
        row = []

    while index < len(text):
        char = text[index]
        if in_quotes:
            if char == '"':
                if index + 1 < len(text) and text[index + 1] == '"':
                    field.append('"')
                    index += 1
                else:
                    in_quotes = False
                    after_quote = True
            else:
                field.append(char)
        elif after_quote:
            if char == ",":
                end_field()
            elif char == "\n":
                end_row()
            else:
                raise ValueError("extra characters after closing quote")
        elif char == '"':
            if field:
                raise ValueError("quote inside unquoted field")
            in_quotes = True
        elif char == ",":
            end_field()
        elif char == "\n":
            end_row()
        else:
            field.append(char)
        index += 1

    if in_quotes:
        raise ValueError("unterminated quote")
    if field or row or after_quote:
        end_row()
    return rows
