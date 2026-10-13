"""Revocable Google login sessions."""

import sqlalchemy as sa
from alembic import op

revision = "4e8cd137ab92"
down_revision = "c6faee5e31e0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "login_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
    )
    op.create_index("ix_login_sessions_expires_at", "login_sessions", ["expires_at"])


def downgrade():
    op.drop_index("ix_login_sessions_expires_at", table_name="login_sessions")
    op.drop_table("login_sessions")
