"""create truck_profiles and trailer_profiles tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-18

Issue #19's two tables, chained after #18's `accounts`/`garages`/`sessions`
migration rather than starting a separate migration history (Implementation
Decisions: "one migration adding truck_profiles and trailer_profiles,
chained after #18's accounts/garages migration"). Field-for-field matches
`towing_core.models.TruckProfile`/`TrailerProfile` plus the new `garage_id`
FK (Story 19) - see `towing_backend.db`'s `truck_profiles`/`trailer_profiles`
Core `Table` definitions, which this migration's columns mirror exactly.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "truck_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "garage_id",
            sa.Integer(),
            sa.ForeignKey("garages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("gvwr", sa.Float(), nullable=False),
        sa.Column("front_gawr", sa.Float(), nullable=False),
        sa.Column("rear_gawr", sa.Float(), nullable=False),
        sa.Column("gcwr", sa.Float(), nullable=True),
        sa.Column("nickname", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_truck_profiles_garage_id", "truck_profiles", ["garage_id"])

    op.create_table(
        "trailer_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "garage_id",
            sa.Integer(),
            sa.ForeignKey("garages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("gvwr", sa.Float(), nullable=False),
        sa.Column("gawr", sa.Float(), nullable=False),
        sa.Column("axle_count", sa.Integer(), nullable=False),
        sa.Column("uvw", sa.Float(), nullable=True),
        sa.Column("nickname", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_trailer_profiles_garage_id", "trailer_profiles", ["garage_id"])


def downgrade() -> None:
    op.drop_table("trailer_profiles")
    op.drop_table("truck_profiles")
