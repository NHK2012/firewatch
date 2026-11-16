{{ config(
    materialized='table',
    partition_by={
        'field': '_airbyte_extracted_at',
        'data_type': 'timestamp',
        'granularity': 'day'
    },
    cluster_by=['grid_cell_id'],
    partition_expiration_days=59
) }}

with gridded_observations as (
    select
        *,
        cast(floor(latitude) as int64) as grid_lat,
        cast(floor(longitude) as int64) as grid_lon
    from {{ ref('stg_active_fires') }}
),

keyed_observations as (
    select
        *,
        concat(cast(grid_lat as string), '_', cast(grid_lon as string)) as grid_cell_id,
        to_hex(sha256(to_json_string(struct(
            product as product,
            latitude as latitude,
            longitude as longitude,
            bright_ti4 as bright_ti4,
            bright_ti5 as bright_ti5,
            scan as scan,
            track as track,
            acq_date as acq_date,
            acq_time as acq_time,
            satellite as satellite,
            instrument as instrument,
            confidence as confidence,
            confidence_raw as confidence_raw,
            version as version,
            frp as frp,
            daynight as daynight
        )))) as observation_key,
        coalesce(confidence in ('nominal', 'high'), false) as is_reliable
    from gridded_observations
),

deduplicated_observations as (
    select *
    from keyed_observations
    qualify row_number() over (
        partition by observation_key
        order by _airbyte_extracted_at desc
    ) = 1
)

select *
from deduplicated_observations
