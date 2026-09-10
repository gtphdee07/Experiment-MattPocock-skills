"""The wall-clock seam for the services tier.

`iso_now` is the default timestamp source for a recorded Weigh Event
(`cli.run_weigh_event`'s `now` parameter, and `services.record_weigh_event`).
It is a module-level function rather than an inline default so tests and
non-interactive callers can inject a fixed clock.
"""

from datetime import UTC, datetime


def iso_now() -> str:
    return datetime.now(UTC).isoformat()
