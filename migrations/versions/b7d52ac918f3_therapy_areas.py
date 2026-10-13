"""Areas recorded for a session's physical therapy."""

import sqlalchemy as sa
from alembic import op

revision = "b7d52ac918f3"
down_revision = "4e8cd137ab92"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "workout_sessions",
        sa.Column("therapy_areas", sa.Text(), nullable=False, server_default=""),
    )


def downgrade():
    op.drop_column("workout_sessions", "therapy_areas")
