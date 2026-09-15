"""Interactive input primitives for the CLI: prompt-until-valid parsing and
the small family of `_read_*` helpers built on it.

No `argparse` and no domain logic - these just turn a `read` callable (real
`input`, or a test fake) plus a prompt string into a parsed value, retrying
on `ValueError`. `_prompt_until_valid`'s retry message is the only direct
output here; it goes through the injected `emit` (default `print`), so the
shipped behavior is byte-identical to printing.
"""

from collections.abc import Callable
from pathlib import Path

ReadFn = Callable[[str], str]

NICKNAME_PROMPT = "Nick Name / Reference (optional - press Enter to skip): "


def _prompt_until_valid[T](
    read: ReadFn,
    prompt: str,
    parse: Callable[[str], T],
    label: str,
    emit: Callable[[str], None] = print,
) -> T:
    while True:
        raw = read(prompt)
        try:
            return parse(raw)
        except ValueError:
            emit(f"'{raw}' is not a valid {label}. Please try again.")


def _confirm(read: ReadFn, message: str) -> bool:
    response = read(message)
    return response.strip().lower() == "y"


def _read_float(read: ReadFn, prompt: str) -> float:
    return _prompt_until_valid(read, prompt, float, "number")


def _read_optional_float(read: ReadFn, prompt: str) -> float | None:
    def parse(raw: str) -> float | None:
        return None if not raw.strip() else float(raw)

    return _prompt_until_valid(read, prompt, parse, "number")


def _require_positive(value: float) -> float:
    if value <= 0:
        raise ValueError("must be greater than 0")
    return value


def _read_positive_float(read: ReadFn, prompt: str) -> float:
    """Like `_read_float`, but re-prompts (via the same retry loop) on a
    non-positive value too, not just an unparseable one - see issue #22:
    a sign-typo'd negative weight must never silently reach domain-object
    construction, where `__post_init__` would raise past this point with no
    handler to catch it."""

    def parse(raw: str) -> float:
        return _require_positive(float(raw))

    return _prompt_until_valid(read, prompt, parse, "number")


def _read_optional_positive_float(read: ReadFn, prompt: str) -> float | None:
    """Like `_read_optional_float`, but a provided (non-blank) value must
    also be positive - see `_read_positive_float`."""

    def parse(raw: str) -> float | None:
        return None if not raw.strip() else _require_positive(float(raw))

    return _prompt_until_valid(read, prompt, parse, "number")


def _read_optional_str(read: ReadFn, prompt: str) -> str | None:
    stripped = read(prompt).strip()
    return stripped if stripped else None


def _read_optional_str_with_default(
    read: ReadFn, prompt: str, current: str | None
) -> str | None:
    stripped = read(prompt).strip()
    return stripped if stripped else current


def _read_float_with_default(read: ReadFn, prompt: str, current: float) -> float:
    def parse(raw: str) -> float:
        return current if not raw.strip() else float(raw)

    return _prompt_until_valid(read, prompt, parse, "number")


def _read_positive_float_with_default(
    read: ReadFn, prompt: str, current: float
) -> float:
    """Like `_read_float_with_default`, but a typed (non-blank) value must
    also be positive - see `_read_positive_float`. `current` itself is
    trusted (it came from an already-validated profile), so keeping it via
    blank input never re-triggers the check."""

    def parse(raw: str) -> float:
        return current if not raw.strip() else _require_positive(float(raw))

    return _prompt_until_valid(read, prompt, parse, "number")


def _read_optional_float_with_default(
    read: ReadFn, prompt: str, current: float | None
) -> float | None:
    def parse(raw: str) -> float | None:
        stripped = raw.strip()
        if not stripped:
            return current
        if stripped.lower() == "none":
            return None
        return float(stripped)

    return _prompt_until_valid(read, prompt, parse, "number")


def _read_optional_positive_float_with_default(
    read: ReadFn, prompt: str, current: float | None
) -> float | None:
    """Like `_read_optional_float_with_default`, but a typed (non-blank,
    non-'none') value must also be positive - see
    `_read_positive_float_with_default`."""

    def parse(raw: str) -> float | None:
        stripped = raw.strip()
        if not stripped:
            return current
        if stripped.lower() == "none":
            return None
        return _require_positive(float(stripped))

    return _prompt_until_valid(read, prompt, parse, "number")


def _read_int(read: ReadFn, prompt: str) -> int:
    return _prompt_until_valid(read, prompt, int, "whole number")


def _read_int_with_default(read: ReadFn, prompt: str, current: int) -> int:
    def parse(raw: str) -> int:
        return current if not raw.strip() else int(raw)

    return _prompt_until_valid(read, prompt, parse, "whole number")


def _require_at_least_one(value: int) -> int:
    if value < 1:
        raise ValueError("must be at least 1")
    return value


def _read_positive_int(read: ReadFn, prompt: str) -> int:
    """Like `_read_int`, but re-prompts on a value below 1 too - see
    `_read_positive_float` (used for `TrailerProfile.axle_count`, which
    `__post_init__` requires to be at least 1)."""

    def parse(raw: str) -> int:
        return _require_at_least_one(int(raw))

    return _prompt_until_valid(read, prompt, parse, "whole number")


def _read_positive_int_with_default(read: ReadFn, prompt: str, current: int) -> int:
    def parse(raw: str) -> int:
        return current if not raw.strip() else _require_at_least_one(int(raw))

    return _prompt_until_valid(read, prompt, parse, "whole number")


def _read_photo_path(read: ReadFn, prompt: str) -> Path:
    return Path(read(prompt))
