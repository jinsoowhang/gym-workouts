from alembic import context

from gym_workouts import models  # noqa: F401
from gym_workouts.config import Settings
from gym_workouts.database import Base, create_database

path = context.config.attributes.get("database_path") or Settings.from_env().database_path
engine, _factory = create_database(path)
try:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
finally:
    engine.dispose()
