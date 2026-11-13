# dbt (Neha)

Lineage: source -> stg_active_fires -> int_fire_observations -> dim_grid_cell -> five marts.
Region labels come from the `region_bounds` seed (approximate boxes).

```
export FIREWATCH_PROJECT=<your-project-id>
export DBT_KEYFILE=../../keys/sa-dbt.json
dbt debug --profiles-dir .
dbt seed --profiles-dir . && dbt run --profiles-dir . && dbt test --profiles-dir .
```
While developing on the fixture: `--vars '{raw_dataset: firewatch_raw_sample}'`.
