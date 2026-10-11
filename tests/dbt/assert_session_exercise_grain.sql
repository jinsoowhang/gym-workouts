select
    session_id,
    exercise_id
from {{ ref('int_session_exercise_metrics') }}
group by session_id, exercise_id
having count(*) > 1
