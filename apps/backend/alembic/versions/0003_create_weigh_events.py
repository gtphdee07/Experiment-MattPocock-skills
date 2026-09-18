"""create weigh_events table

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-18

Issue #21's one new table, chained after #19's `truck_profiles`/
`trailer_profiles` migration rather than starting a separate migration
history (same convention #19 used chaining after #18). Columns mirror
`towing_app.sqlite.SqliteWeighEventStore._COLUMN_DEFS` field-for-field, plus
a `garage_id` FK - see `towing_backend.db`'s `weigh_events` Core `Table`
definition, which this migration's columns mirror exactly. `truck_id`/
`trailer_id` are plain columns with no FK to `truck_profiles`/
`trailer_profiles` - see that module's docstring on the `weigh_events` table
for why (ADR 0004's snapshot-Nickname design already assumes a Weigh Event
survives its Profile being deleted).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "weigh_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "garage_id",
            sa.Integer(),
            sa.ForeignKey("garages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("truck_id", sa.Integer(), nullable=False),
        sa.Column("trailer_id", sa.Integer(), nullable=False),
        sa.Column("steer", sa.Float(), nullable=False),
        sa.Column("drive", sa.Float(), nullable=False),
        sa.Column("trailer_axle", sa.Float(), nullable=False),
        sa.Column("gross", sa.Float(), nullable=False),
        sa.Column("steer_rating", sa.Float(), nullable=False),
        sa.Column("drive_rating", sa.Float(), nullable=False),
        sa.Column("trailer_rating", sa.Float(), nullable=False),
        sa.Column("gvwr_rating", sa.Float(), nullable=False),
        sa.Column("gcwr_rating", sa.Float(), nullable=True),
        sa.Column("timestamp", sa.String(), nullable=False),
        sa.Column("combined_reweigh_reference", sa.String(), nullable=True),
        sa.Column("solo_steer", sa.Float(), nullable=True),
        sa.Column("solo_drive", sa.Float(), nullable=True),
        sa.Column("solo_gross", sa.Float(), nullable=True),
        sa.Column("solo_reweigh_reference", sa.String(), nullable=True),
        sa.Column("trailer_gvwr_rating", sa.Float(), nullable=True),
        sa.Column("time_gap_hours", sa.Float(), nullable=True),
        sa.Column("reused_solo_from_timestamp", sa.String(), nullable=True),
        sa.Column("ticket_timestamp", sa.String(), nullable=True),
        sa.Column("solo_timestamp", sa.String(), nullable=True),
        sa.Column(
            "reused_solo_is_unverified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("truck_nickname", sa.String(), nullable=True),
        sa.Column("trailer_nickname", sa.String(), nullable=True),
    )
    op.create_index("ix_weigh_events_garage_id", "weigh_events", ["garage_id"])


def downgrade() -> None:
    op.drop_table("weigh_events")
