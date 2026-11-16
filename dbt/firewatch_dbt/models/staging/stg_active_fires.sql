with source_data as (
    select
        safe_cast(cast(latitude as string) as float64) as latitude,
        safe_cast(cast(longitude as string) as float64) as longitude,
        safe_cast(cast(bright_ti4 as string) as float64) as bright_ti4,
        safe_cast(cast(bright_ti5 as string) as float64) as bright_ti5,
        safe_cast(cast(scan as string) as float64) as scan,
        safe_cast(cast(track as string) as float64) as track,
        safe_cast(cast(acq_date as string) as date) as acq_date,
        safe_cast(cast(acq_time as string) as int64) as acq_time_hhmm,
        cast(satellite as string) as satellite,
        cast(instrument as string) as instrument,
        cast(confidence as string) as confidence_raw,
        cast(version as string) as version,
        safe_cast(cast(frp as string) as float64) as frp,
        cast(daynight as string) as daynight,
        cast(product as string) as product,
        safe_cast(cast(_airbyte_extracted_at as string) as timestamp)
            as _airbyte_extracted_at
    from {{ source('firewatch_raw', 'active_fire_observations') }}
),

normalized as (
    select
        latitude,
        longitude,
        bright_ti4,
        bright_ti5,
        scan,
        track,
        acq_date,
        safe.parse_time(
            '%H%M',
            lpad(cast(acq_time_hhmm as string), 4, '0')
        ) as acq_time,
        satellite,
        instrument,
        case lower(trim(confidence_raw))
            when 'l' then 'low'
            when 'low' then 'low'
            when 'n' then 'nominal'
            when 'nominal' then 'nominal'
            when 'h' then 'high'
            when 'high' then 'high'
            else null
        end as confidence,
        confidence_raw,
        version,
        frp,
        daynight,
        product,
        _airbyte_extracted_at
    from source_data
)

select
    latitude,
    longitude,
    bright_ti4,
    bright_ti5,
    scan,
    track,
    acq_date,
    acq_time,
    satellite,
    instrument,
    confidence,
    confidence_raw,
    version,
    frp,
    daynight,
    product,
    _airbyte_extracted_at
from normalized
where latitude between -90 and 90
  and longitude between -180 and 180
  and acq_date is not null
  and acq_time is not null
  and confidence is not null
  and (frp is null or frp >= 0)
