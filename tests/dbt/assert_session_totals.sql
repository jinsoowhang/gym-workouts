with totals as (
    select
        session_id,
        count(*) as performed_sets,
        sum(reps) as performed_reps,
        sum(recorded_load_volume_lb) as recorded_load_volume_lb
    from {{ ref('fct_workout_sets') }}
    group by session_id
)

select sessions.session_id
from {{ ref('fct_workout_sessions') }} as sessions
left join totals on sessions.session_id = totals.session_id
where
    sessions.performed_sets != coalesce(totals.performed_sets, 0)
    or sessions.performed_reps != coalesce(totals.performed_reps, 0)
    or sessions.recorded_load_volume_lb != coalesce(totals.recorded_load_volume_lb, 0)
