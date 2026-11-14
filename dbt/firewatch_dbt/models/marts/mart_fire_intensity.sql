{{ config(materialized='table') }}

with classified_observations as (
    select
        case
            when frp is null then 'Unknown'
            when frp < {{ var('frp_moderate_min') }} then 'Low'
            when frp < {{ var('frp_high_min') }} then 'Moderate'
            else 'High'
        end as intensity_category,
        frp,
        is_reliable
    from {{ ref('int_fire_observations') }}
)

select
    intensity_category,
    count(*) as total_detections,
    countif(coalesce(is_reliable, false)) as reliable_detections,
    countif(not coalesce(is_reliable, false)) as non_reliable_detections,
    avg(frp) as average_frp,
    max(frp) as maximum_frp
from classified_observations
group by intensity_category
