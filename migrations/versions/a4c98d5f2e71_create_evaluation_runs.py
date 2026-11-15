from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4c98d5f2e71"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_evaluation_runs_status",
        "evaluation_runs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_evaluation_runs_status", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
