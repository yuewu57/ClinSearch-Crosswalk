"""Audit helpers."""


def flatten_audit(flags_by_line: dict[int, list[str]]) -> tuple[str, ...]:
    return tuple(f"line_#{number}:{flag}" for number in sorted(flags_by_line) for flag in flags_by_line[number])
