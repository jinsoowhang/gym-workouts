select
    id as exercise_id,
    name as exercise_name,
    measurement_type,
    snapshot_id,
    extracted_at
from {{ source('operational', 'raw_exercises') }}
where snapshot_id = ({{ latest_snapshot() }})
