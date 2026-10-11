with expected as (
    select count(*) as row_count
    from {{ ref('stg_operational__workout_sets') }} as workout_sets
    inner join {{ ref('stg_operational__workout_sessions') }} as sessions
        on workout_sets.session_id = sessions.session_id
    inner join {{ ref('stg_operational__exercises') }} as exercises
        on workout_sets.exercise_id = exercises.exercise_id
    where
        workout_sets.set_status = 'performed'
        and sessions.session_status = 'completed'
        and exercises.measurement_type = 'weight_reps'
),

actual as (
    select count(*) as row_count from {{ ref('fct_workout_sets') }}
)

select expected.row_count
from expected cross join actual
where expected.row_count != actual.row_count
