{{ config(materialized='table') }}

with daily_activity as (
    select
        acq_date,
        count(*) as total_detections,
        countif(coalesce(is_reliable, false)) as reliable_detections,
        countif(not coalesce(is_reliable, false)) as non_reliable_detections,
        countif(daynight = 'D') as daytime_detections,
        countif(daynight = 'N') as nighttime_detections,
        avg(frp) as average_frp,
        max(frp) as maximum_frp
    from {{ ref('int_fire_observations') }}
    group by acq_date
)

select
    acq_date,
    total_detections,
    reliable_detections,
    non_reliable_detections,
    daytime_detections,
    nighttime_detections,
    average_frp,
    maximum_frp,
    avg(total_detections) over (
        order by acq_date
        rows between 6 preceding and current row
    ) as seven_day_avg_detections
from daily_activity
