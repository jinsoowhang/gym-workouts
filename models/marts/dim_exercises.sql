select
    exercise_id,
    exercise_name,
    measurement_type
from {{ ref('stg_operational__exercises') }}
