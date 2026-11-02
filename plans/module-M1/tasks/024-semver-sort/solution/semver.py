import re


PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def _parse(version: str):
    match = PATTERN.match(version)
    if not match:
        raise ValueError(f"invalid version: {version!r}")
    major, minor, patch = (int(match.group(i)) for i in (1, 2, 3))
    prerelease = match.group(4)
    parts = [] if prerelease is None else prerelease.split(".")
    return major, minor, patch, parts


def _compare(left: str, right: str) -> int:
    l_major, l_minor, l_patch, l_pre = _parse(left)
    r_major, r_minor, r_patch, r_pre = _parse(right)
    l_core = (l_major, l_minor, l_patch)
    r_core = (r_major, r_minor, r_patch)
    if l_core != r_core:
        return -1 if l_core < r_core else 1
    if not l_pre and not r_pre:
        return 0
    if not l_pre:
        return 1
    if not r_pre:
        return -1
    for l_part, r_part in zip(l_pre, r_pre):
        if l_part == r_part:
            continue
        l_num = l_part.isdigit()
        r_num = r_part.isdigit()
        if l_num and r_num:
            return -1 if int(l_part) < int(r_part) else 1
        if l_num != r_num:
            return -1 if l_num else 1
        return -1 if l_part < r_part else 1
    if len(l_pre) == len(r_pre):
        return 0
    return -1 if len(l_pre) < len(r_pre) else 1


def sort_versions(versions: list[str]) -> list[str]:
    import functools

    for version in versions:
        _parse(version)
    return sorted(versions, key=functools.cmp_to_key(_compare))
