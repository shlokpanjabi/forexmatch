"""allow a waived fee to stand as a fact without an amount

Revision ID: 4c1a2f7b8e93
Revises: 3b5d930889a2
Create Date: 2026-09-08
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "4c1a2f7b8e93"
down_revision: str | None = "3b5d930889a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "fee_has_value_or_is_explicitly_unknown"


def upgrade() -> None:
    op.drop_constraint(CONSTRAINT, "card_fees", type_="check")
    op.create_check_constraint(
        "fee_has_value_or_is_explicitly_unknown",
        "card_fees",
        "amount IS NOT NULL OR percentage IS NOT NULL OR is_unknown = true OR is_waived = true",
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, "card_fees", type_="check")
    op.create_check_constraint(
        "fee_has_value_or_is_explicitly_unknown",
        "card_fees",
        "amount IS NOT NULL OR percentage IS NOT NULL OR is_unknown = true",
    )
