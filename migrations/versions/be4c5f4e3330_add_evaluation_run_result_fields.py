
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "be4c5f4e3330"
down_revision: Union[str, Sequence[str], None] = "a4c98d5f2e71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "evaluation_runs",
        sa.Column("result", sa.JSON(), nullable=True),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("error_message", sa.String(length=2000), nullable=True),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("evaluation_runs", "completed_at")
    op.drop_column("evaluation_runs", "error_message")
    op.drop_column("evaluation_runs", "result")
