select
    id as session_id,
    routine,
    cast(session_date as date) as session_date,
    status as session_status,
    revision,
    source_path,
    snapshot_id,
    extracted_at
from {{ source('operational', 'raw_workout_sessions') }}
where snapshot_id = ({{ latest_snapshot() }})
