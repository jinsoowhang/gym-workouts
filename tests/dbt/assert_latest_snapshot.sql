select workout_sets.snapshot_id
from {{ ref('stg_operational__workout_sets') }} as workout_sets
inner join {{ source('operational', 'raw_snapshot_manifest') }} as manifest
    on workout_sets.snapshot_id = manifest.snapshot_id
where manifest.extracted_at < (
    select max(latest.extracted_at)
    from {{ source('operational', 'raw_snapshot_manifest') }} as latest
)
