"""make weigh_events.truck_id/trailer_id nullable

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-19

Issue #45 / ADR 0017 (One-Off Truck/Trailer): a Weigh Event's Truck or
Trailer side can now be a One-Off - entered for that single Weigh Event,
never saved as a real Truck/Trailer Profile - instead of always referencing
a saved Profile row. This migration removes only the NOT NULL constraint on
`weigh_events.truck_id`/`trailer_id`; they stay the same plain, FK-less
`Integer` columns `towing_backend.db`'s `weigh_events` Table definition
already describes (see that module's docstring for why there's still no FK
to `truck_profiles`/`trailer_profiles`) - nothing else about this table
changes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "weigh_events", "truck_id", existing_type=sa.Integer(), nullable=True
    )
    op.alter_column(
        "weigh_events", "trailer_id", existing_type=sa.Integer(), nullable=True
    )


def downgrade() -> None:
    op.alter_column(
        "weigh_events", "truck_id", existing_type=sa.Integer(), nullable=False
    )
    op.alter_column(
        "weigh_events", "trailer_id", existing_type=sa.Integer(), nullable=False
    )
