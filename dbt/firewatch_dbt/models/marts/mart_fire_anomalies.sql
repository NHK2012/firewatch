{% set percentile_fraction = (var('anomaly_percentile') | float) / 100 %}

{{ config(materialized='table') }}

with percentile_values as (
    select
        percentile_cont(frp, {{ percentile_fraction }}) over () as anomaly_threshold
    from {{ ref('int_fire_observations') }}
    where frp is not null
),

anomaly_threshold as (
    select max(anomaly_threshold) as anomaly_threshold
    from percentile_values
)

select
    observations.observation_key,
    observations.acq_date,
    observations.acq_time,
    observations.latitude,
    observations.longitude,
    observations.grid_cell_id,
    grid_cells.region_name,
    observations.frp,
    observations.confidence,
    observations.satellite,
    anomaly_threshold.anomaly_threshold
from {{ ref('int_fire_observations') }} as observations
cross join anomaly_threshold
left join {{ ref('dim_grid_cell') }} as grid_cells
    using (grid_cell_id)
where observations.frp is not null
  and observations.frp >= anomaly_threshold.anomaly_threshold
