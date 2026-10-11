select
    workout_sets.set_id,
    workout_sets.session_id,
    workout_sets.exercise_id,
    workout_sets.template_key,
    sessions.routine,
    sessions.session_date,
    workout_sets.session_position,
    workout_sets.exercise_set_number,
    workout_sets.weight_lb,
    workout_sets.reps,
    workout_sets.snapshot_id,
    workout_sets.weight_lb * workout_sets.reps as recorded_load_volume_lb
from {{ ref('stg_operational__workout_sets') }} as workout_sets
inner join {{ ref('stg_operational__workout_sessions') }} as sessions
    on workout_sets.session_id = sessions.session_id
inner join {{ ref('stg_operational__exercises') }} as exercises
    on workout_sets.exercise_id = exercises.exercise_id
where
    sessions.session_status = 'completed'
    and workout_sets.set_status = 'performed'
    and exercises.measurement_type = 'weight_reps'
