{{ config(materialized='table') }}

with monthly_activity as (
    select
        date_trunc(acq_date, month) as month_start,
        count(*) as total_detections,
        countif(coalesce(is_reliable, false)) as reliable_detections,
        countif(not coalesce(is_reliable, false)) as non_reliable_detections,
        countif(daynight = 'D') as daytime_detections,
        countif(daynight = 'N') as nighttime_detections,
        avg(frp) as average_frp,
        max(frp) as maximum_frp
    from {{ ref('int_fire_observations') }}
    group by month_start
)

select
    format_date('%Y-%m', month_start) as month_id,
    month_start,
    total_detections,
    reliable_detections,
    non_reliable_detections,
    daytime_detections,
    nighttime_detections,
    average_frp,
    maximum_frp
from monthly_activity
