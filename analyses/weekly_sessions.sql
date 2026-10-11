select
    date_trunc('week', session_date) as week_start,
    count(*) as completed_sessions,
    sum(performed_sets) as performed_sets,
    sum(recorded_load_volume_lb) as recorded_load_volume_lb
from {{ ref('fct_workout_sessions') }}
group by date_trunc('week', session_date)
order by week_start
