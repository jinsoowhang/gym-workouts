select
    set_id,
    session_id,
    exercise_id,
    template_key,
    routine,
    session_date,
    session_position,
    exercise_set_number,
    weight_lb,
    reps,
    recorded_load_volume_lb,
    snapshot_id
from {{ ref('int_completed_workout_sets') }}
