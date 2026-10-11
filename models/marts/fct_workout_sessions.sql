with session_totals as (
    select
        session_id,
        sum(performed_sets) as performed_sets,
        sum(performed_reps) as performed_reps,
        sum(recorded_load_volume_lb) as recorded_load_volume_lb
    from {{ ref('int_session_exercise_metrics') }}
    group by session_id
)

select
    sessions.session_id,
    sessions.routine,
    sessions.session_date,
    sessions.source_path,
    sessions.snapshot_id,
    coalesce(totals.performed_sets, 0) as performed_sets,
    coalesce(totals.performed_reps, 0) as performed_reps,
    coalesce(totals.recorded_load_volume_lb, 0) as recorded_load_volume_lb
from {{ ref('stg_operational__workout_sessions') }} as sessions
left join session_totals as totals on sessions.session_id = totals.session_id
where sessions.session_status = 'completed'
