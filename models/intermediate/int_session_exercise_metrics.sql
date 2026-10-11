select
    session_id,
    exercise_id,
    count(*) as performed_sets,
    sum(reps) as performed_reps,
    sum(recorded_load_volume_lb) as recorded_load_volume_lb
from {{ ref('int_completed_workout_sets') }}
group by session_id, exercise_id
