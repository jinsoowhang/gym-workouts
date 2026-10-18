"""Resolve the existing owner's account without creating public registrations."""

from sqlalchemy import select

from gym_workouts.models import User


def owner_user_id(factory, email=""):
    with factory.begin() as db:
        owner = db.scalars(select(User).where(User.vault_owner.is_(True))).one()
        if email:
            email = email.strip().lower()
            if owner.email is None and owner.google_subject is None:
                owner.email = email
            elif owner.email != email:
                raise ValueError("Configured login does not match the existing workout owner")
        return owner.id
