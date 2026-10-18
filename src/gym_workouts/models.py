from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gym_workouts.database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str | None] = mapped_column(String, unique=True)
    google_subject: Mapped[str | None] = mapped_column(String, unique=True)
    vault_owner: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    __table_args__ = (
        Index(
            "uq_users_vault_owner", "vault_owner", unique=True, sqlite_where=text("vault_owner = 1")
        ),
    )


class Exercise(Base):
    __tablename__ = "exercises"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    measurement_type: Mapped[str] = mapped_column(String, default="weight_reps")
    __table_args__ = (CheckConstraint("measurement_type IN ('weight_reps', 'activity')"),)


class RoutineSet(Base):
    __tablename__ = "routine_sets"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    routine: Mapped[str] = mapped_column(String)
    position: Mapped[int] = mapped_column(Integer)
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id"))
    occurrence: Mapped[int] = mapped_column(Integer)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    reps: Mapped[int | None] = mapped_column(Integer)
    exercise: Mapped[Exercise] = relationship()
    __table_args__ = (
        UniqueConstraint("user_id", "routine", "position"),
        CheckConstraint("routine IN ('A', 'B')"),
        CheckConstraint("weight IS NULL OR weight >= 0"),
        CheckConstraint("reps IS NULL OR reps >= 0"),
    )


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    routine: Mapped[str] = mapped_column(String)
    session_date: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="draft")
    revision: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    therapy_areas: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_at: Mapped[str] = mapped_column(String)
    completed_at: Mapped[str | None] = mapped_column(String)
    source_path: Mapped[str | None] = mapped_column(String, unique=True)
    rows: Mapped[list[WorkoutSet]] = relationship(
        back_populates="session", order_by="WorkoutSet.position", cascade="all, delete-orphan"
    )
    __table_args__ = (
        CheckConstraint("routine IN ('A', 'B')"),
        CheckConstraint("status IN ('draft', 'finalizing', 'completed', 'discarded', 'review')"),
    )


class WorkoutSet(Base):
    __tablename__ = "workout_sets"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("workout_sessions.id"))
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id"))
    template_key: Mapped[str | None] = mapped_column(String)
    position: Mapped[int] = mapped_column(Integer)
    occurrence: Mapped[int] = mapped_column(Integer)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    reps: Mapped[int | None] = mapped_column(Integer)
    default_weight: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    default_reps: Mapped[int | None] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String, default="pending")
    previous_state: Mapped[str | None] = mapped_column(String)
    activity_area: Mapped[str] = mapped_column(Text, default="", server_default="")
    default_source: Mapped[str] = mapped_column(String, default="Template")
    session: Mapped[WorkoutSession] = relationship(back_populates="rows")
    exercise: Mapped[Exercise] = relationship()
    __table_args__ = (
        UniqueConstraint("session_id", "position"),
        CheckConstraint("state IN ('pending', 'performed', 'skipped', 'removed', 'unknown')"),
        CheckConstraint("weight IS NULL OR weight >= 0"),
        CheckConstraint("reps IS NULL OR reps >= 0"),
    )


class ImportBatch(Base):
    __tablename__ = "import_batches"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    imported_at: Mapped[str] = mapped_column(String)
    report: Mapped[str] = mapped_column(Text)


class SourceRecord(Base):
    __tablename__ = "source_records"
    path: Mapped[str] = mapped_column(String, primary_key=True)
    checksum: Mapped[str] = mapped_column(String)
    original_text: Mapped[str] = mapped_column(Text)
    issues: Mapped[str] = mapped_column(Text, default="[]")
    batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"))


class VaultWrite(Base):
    __tablename__ = "vault_writes"
    session_id: Mapped[str] = mapped_column(ForeignKey("workout_sessions.id"), primary_key=True)
    target_name: Mapped[str] = mapped_column(String, unique=True)
    content: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (CheckConstraint("status IN ('pending', 'saved', 'failed')"),)


class LoginSession(Base):
    __tablename__ = "login_sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    subject: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String)
    expires_at: Mapped[int] = mapped_column(Integer, index=True)
