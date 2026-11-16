{{ config(materialized='table') }}

select
    coalesce(grid_cells.region_name, 'Unclassified') as region_name,
    count(*) as total_detections,
    countif(coalesce(observations.is_reliable, false)) as reliable_detections,
    countif(not coalesce(observations.is_reliable, false)) as non_reliable_detections,
    safe_divide(
        countif(coalesce(observations.is_reliable, false)) * 100.0,
        count(*)
    ) as reliable_percentage,
    countif(observations.daynight = 'D') as daytime_detections,
    countif(observations.daynight = 'N') as nighttime_detections,
    avg(observations.frp) as average_frp,
    max(observations.frp) as maximum_frp,
    avg(observations.latitude) as average_latitude,
    avg(observations.longitude) as average_longitude
from {{ ref('int_fire_observations') }} as observations
left join {{ ref('dim_grid_cell') }} as grid_cells
    using (grid_cell_id)
group by coalesce(grid_cells.region_name, 'Unclassified')
