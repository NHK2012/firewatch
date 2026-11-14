with grid_cells as (
    select distinct
        grid_cell_id,
        grid_lat,
        grid_lon
    from {{ ref('int_fire_observations') }}
),

ranked_region_matches as (
    select
        grid_cells.grid_cell_id,
        grid_cells.grid_lat,
        grid_cells.grid_lon,
        region_bounds.region_name,
        row_number() over (
            partition by grid_cells.grid_cell_id
            order by region_bounds.priority asc, region_bounds.region_name asc
        ) as region_rank
    from grid_cells
    left join {{ ref('region_bounds') }} as region_bounds
        on grid_cells.grid_lat + 0.5
            between region_bounds.min_lat and region_bounds.max_lat
        and grid_cells.grid_lon + 0.5
            between region_bounds.min_lon and region_bounds.max_lon
)

select
    grid_cell_id,
    grid_lat,
    grid_lon,
    coalesce(region_name, 'Unclassified') as region_name
from ranked_region_matches
where region_rank = 1
