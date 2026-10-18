"""Assign existing sessions and templates to the configured owner."""

from uuid import uuid4

import sqlalchemy as sa
from alembic import context, op

revision = "d1f7a903be42"
down_revision = "c9e42b801d65"
branch_labels = None
depends_on = None


def table_checks(table):
    return {
        "workout_sessions": [
            sa.CheckConstraint("routine IN ('A', 'B')"),
            sa.CheckConstraint(
                "status IN ('draft', 'finalizing', 'completed', 'discarded', 'review')"
            ),
        ],
        "routine_sets": [
            sa.CheckConstraint("routine IN ('A', 'B')"),
            sa.CheckConstraint("weight IS NULL OR weight >= 0"),
            sa.CheckConstraint("reps IS NULL OR reps >= 0"),
        ],
        "login_sessions": [],
    }[table]


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=True, unique=True),
        sa.Column("google_subject", sa.String(), nullable=True, unique=True),
        sa.Column("vault_owner", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.create_index(
        "uq_users_vault_owner",
        "users",
        ["vault_owner"],
        unique=True,
        sqlite_where=sa.text("vault_owner = 1"),
    )
    owner_id = str(uuid4())
    email = context.config.attributes.get("owner_email") or None
    op.get_bind().execute(
        sa.text("INSERT INTO users (id, email, vault_owner) VALUES (:id, :email, 1)"),
        {"id": owner_id, "email": email},
    )
    # Existing cookies must reauthenticate before receiving an account identity.
    op.execute("DELETE FROM login_sessions")
    for table in ("workout_sessions", "routine_sets", "login_sessions"):
        op.add_column(table, sa.Column("user_id", sa.String(), nullable=True))
        op.get_bind().execute(sa.text(f"UPDATE {table} SET user_id = :id"), {"id": owner_id})
        with op.batch_alter_table(
            table,
            naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s_%(column_1_name)s"},
            table_args=table_checks(table),
        ) as batch:
            batch.alter_column("user_id", existing_type=sa.String(), nullable=False)
            batch.create_foreign_key(f"fk_{table}_user_id_users", "users", ["user_id"], ["id"])
            if table == "routine_sets":
                batch.drop_constraint("uq_routine_sets_routine_position", type_="unique")
                batch.create_unique_constraint(
                    "uq_routine_sets_user_routine_position", ["user_id", "routine", "position"]
                )
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])


def downgrade():
    # Removing ownership from a database containing additional users is unsafe.
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT count(*) FROM users")).scalar() != 1:
        raise ValueError("Cannot remove ownership while other users exist")
    op.execute("DELETE FROM login_sessions")
    for table in ("login_sessions", "routine_sets", "workout_sessions"):
        with op.batch_alter_table(table, table_args=table_checks(table)) as batch:
            batch.drop_index(f"ix_{table}_user_id")
            batch.drop_constraint(f"fk_{table}_user_id_users", type_="foreignkey")
            if table == "routine_sets":
                batch.drop_constraint("uq_routine_sets_user_routine_position", type_="unique")
                batch.create_unique_constraint(
                    "uq_routine_sets_routine_position", ["routine", "position"]
                )
            batch.drop_column("user_id")
    op.drop_table("users")
