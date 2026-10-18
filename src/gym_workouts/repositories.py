from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from gym_workouts.models import RoutineSet, WorkoutSession, WorkoutSet


class WorkoutRepository:
    def __init__(self, db, user_id):
        self.db = db
        self.user_id = user_id

    def get(self, session_id: str) -> WorkoutSession:
        workout = self.db.scalar(
            select(WorkoutSession)
            .where(WorkoutSession.id == session_id, WorkoutSession.user_id == self.user_id)
            .options(selectinload(WorkoutSession.rows).selectinload(WorkoutSet.exercise))
        )
        if workout is None:
            raise LookupError("Workout session not found")
        return workout

    def latest_completed(self, routine=None, on_date=None):
        query = select(WorkoutSession).where(
            WorkoutSession.status == "completed", WorkoutSession.user_id == self.user_id
        )
        if routine:
            query = query.where(WorkoutSession.routine == routine)
        if on_date:
            query = query.where(WorkoutSession.session_date == on_date)
        return self.db.scalar(
            query.order_by(
                func.coalesce(WorkoutSession.completed_at, WorkoutSession.session_date).desc(),
                WorkoutSession.created_at.desc(),
            )
            .options(selectinload(WorkoutSession.rows).selectinload(WorkoutSet.exercise))
            .limit(1)
        )

    def active(self):
        return self.db.scalar(
            select(WorkoutSession)
            .where(
                WorkoutSession.status.in_(["draft", "finalizing"]),
                WorkoutSession.user_id == self.user_id,
            )
            .options(selectinload(WorkoutSession.rows).selectinload(WorkoutSet.exercise))
            .order_by(WorkoutSession.created_at.desc())
            .limit(1)
        )

    def template(self, routine):
        return list(
            self.db.scalars(
                select(RoutineSet)
                .where(RoutineSet.routine == routine, RoutineSet.user_id == self.user_id)
                .options(selectinload(RoutineSet.exercise))
                .order_by(RoutineSet.position)
            )
        )
