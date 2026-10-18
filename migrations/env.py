from alembic import context

from gym_workouts import models  # noqa: F401
from gym_workouts.config import Settings
from gym_workouts.database import Base, create_database

path = context.config.attributes.get("database_path") or Settings.from_env().database_path
engine, _factory = create_database(path)
try:
    with engine.connect() as connection:
        # SQLite table rebuilds must retain references from sets and publication rows.
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            compare_type=True,
            transactional_ddl=True,
        )
        with context.begin_transaction():
            connection.exec_driver_sql("BEGIN")
            context.run_migrations()
            if connection.exec_driver_sql("PRAGMA foreign_key_check").first():
                raise ValueError("Migration would leave invalid foreign keys")
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
finally:
    engine.dispose()
