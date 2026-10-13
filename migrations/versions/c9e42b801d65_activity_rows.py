"""Individual physical therapy areas on session rows."""

import re
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "c9e42b801d65"
down_revision = "b7d52ac918f3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "workout_sets", sa.Column("activity_area", sa.Text(), nullable=False, server_default="")
    )
    connection = op.get_bind()
    sessions = (
        connection.execute(
            sa.text(
                "SELECT id, therapy_areas, status FROM workout_sessions WHERE therapy_areas != ''"
            )
        )
        .mappings()
        .all()
    )
    for session in sessions:
        rows = (
            connection.execute(
                sa.text(
                    "SELECT r.* FROM workout_sets r JOIN exercises e ON e.id = r.exercise_id "
                    "WHERE r.session_id = :id AND e.name = 'physical therapy' ORDER BY r.position"
                ),
                {"id": session["id"]},
            )
            .mappings()
            .all()
        )
        areas = [
            area.strip() for area in re.split(r"[,;]", session["therapy_areas"]) if area.strip()
        ]
        if len(rows) != 1 or not areas:
            continue
        first = dict(rows[0])
        connection.execute(
            sa.text("UPDATE workout_sets SET activity_area = :area WHERE id = :id"),
            {"area": areas[0], "id": first["id"]},
        )
        position = connection.execute(
            sa.text("SELECT max(position) FROM workout_sets WHERE session_id = :id"),
            {"id": session["id"]},
        ).scalar()
        table = sa.table("workout_sets", *(sa.column(key) for key in first))
        for index, area in enumerate(areas[1:], 1):
            extra = first | {
                "id": str(uuid4()),
                "template_key": None,
                "position": position + index,
                "occurrence": first["occurrence"] + index,
                "activity_area": area,
            }
            connection.execute(table.insert().values(**extra))
        if session["status"] == "draft":
            connection.execute(
                sa.text("UPDATE workout_sessions SET revision = revision + 1 WHERE id = :id"),
                {"id": session["id"]},
            )


def downgrade():
    op.drop_column("workout_sets", "activity_area")
