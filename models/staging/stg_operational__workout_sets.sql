select
    id as set_id,
    session_id,
    exercise_id,
    template_key,
    position as session_position,
    occurrence as exercise_set_number,
    cast(weight as decimal(12, 4)) as weight_lb,
    reps,
    state as set_status,
    default_source,
    snapshot_id,
    extracted_at
from {{ source('operational', 'raw_workout_sets') }}
where snapshot_id = ({{ latest_snapshot() }})
