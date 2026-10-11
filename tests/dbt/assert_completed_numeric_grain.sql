select facts.set_id
from {{ ref('fct_workout_sets') }} as facts
inner join {{ ref('stg_operational__workout_sets') }} as workout_sets
    on facts.set_id = workout_sets.set_id
inner join {{ ref('stg_operational__workout_sessions') }} as sessions
    on facts.session_id = sessions.session_id
inner join {{ ref('dim_exercises') }} as exercises
    on facts.exercise_id = exercises.exercise_id
where
    workout_sets.set_status != 'performed'
    or sessions.session_status != 'completed'
    or exercises.measurement_type != 'weight_reps'
    or facts.weight_lb < 0
    or facts.reps < 0
    or facts.weight_lb is null
    or facts.reps is null
    or facts.recorded_load_volume_lb != facts.weight_lb * facts.reps
