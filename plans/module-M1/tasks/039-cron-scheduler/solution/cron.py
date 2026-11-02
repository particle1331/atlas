from datetime import datetime, timedelta


MONTHS = {
    name: index
    for index, name in enumerate(
        "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1
    )
}
DAYS = {
    name: index
    for index, name in enumerate("SUN MON TUE WED THU FRI SAT".split(), 0)
}


def _value(token: str, low: int, high: int, names: dict[str, int] | None) -> int:
    token = token.upper()
    if names is not None and token in names:
        return names[token]
    try:
        value = int(token)
    except ValueError:
        raise ValueError(f"invalid value: {token}") from None
    if not low <= value <= high:
        raise ValueError(f"value out of range: {token}")
    return value


def _parse_field(
    field: str, low: int, high: int, names: dict[str, int] | None = None
) -> set[int]:
    values = set()
    for part in field.split(","):
        if not part:
            raise ValueError("empty field part")
        step = 1
        if "/" in part:
            base, step_text = part.split("/", 1)
            if not step_text.isdigit() or int(step_text) <= 0:
                raise ValueError("invalid step")
            step = int(step_text)
        else:
            base = part
        if base == "*":
            first, last = low, high
        elif "-" in base:
            first_text, last_text = base.split("-", 1)
            first = _value(first_text, low, high, names)
            last = _value(last_text, low, high, names)
        else:
            first = last = _value(base, low, high, names)
        if first > last:
            raise ValueError("range start is greater than range end")
        values.update(range(first, last + 1, step))
    return values


def next_runs(expression: str, start: datetime, count: int) -> list[datetime]:
    if not isinstance(count, int) or count <= 0:
        raise ValueError("count must be positive")
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError("expected five fields")
    minutes = _parse_field(fields[0], 0, 59)
    hours = _parse_field(fields[1], 0, 23)
    days_of_month = _parse_field(fields[2], 1, 31)
    months = _parse_field(fields[3], 1, 12, MONTHS)
    days_of_week = _parse_field(fields[4], 0, 7, DAYS)
    days_of_week = {0 if day == 7 else day for day in days_of_week}
    dom_any = fields[2] == "*"
    dow_any = fields[4] == "*"

    current = start.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = start + timedelta(days=366 * 5)
    results = []
    while len(results) < count and current <= limit:
        if (
            current.minute not in minutes
            or current.hour not in hours
            or current.month not in months
        ):
            current += timedelta(minutes=1)
            continue
        dom_match = current.day in days_of_month
        cron_dow = (current.weekday() + 1) % 7
        dow_match = cron_dow in days_of_week
        if dom_any and dow_any:
            day_match = True
        elif dom_any:
            day_match = dow_match
        elif dow_any:
            day_match = dom_match
        else:
            day_match = dom_match or dow_match
        if day_match:
            results.append(current)
        current += timedelta(minutes=1)
    if len(results) < count:
        raise ValueError("no matching time found")
    return results
