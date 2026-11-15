# airflow/ (Bhagyashri)

Local Airflow 3 (LocalExecutor) that runs `firewatch_pipeline`: source check -> Airbyte sync ->
raw validation -> `dbt seed && dbt run` -> `dbt test` -> finish.

## Start (first time)
```bash
cd airflow
mkdir -p dags logs plugins config keys           # keys/ is git-ignored
cp .env.example .env                              # fill in values; never commit .env
cp ../keys/sa-dbt.json keys/sa-dbt.json           # or put the key straight into airflow/keys/
docker compose up airflow-init
docker compose up -d --build
# UI: http://localhost:8081  (local demo, no login)
```
Docker Desktop needs **>= 8 GB RAM**. Airbyte must already be running on the same machine (http://localhost:8000);
the DAG reaches it as `host.docker.internal:8000` (`extra_hosts` makes that work on Linux).
Windows: keep `.yaml`/`.sh` files with LF line endings and use forward slashes in mounts.

## Files
| File | Purpose |
| --- | --- |
| `Dockerfile` | Airflow image + `google-cloud-bigquery`, `requests`, and dbt in its own virtualenv (`/home/airflow/dbt-venv`). Tag must match `AIRFLOW_VERSION` of the compose file. |
| `docker-compose.yaml` | postgres + api-server, scheduler, dag-processor, triggerer. Mounts `../dbt` and `./keys`. |
| `.env.example` | Variable names only (project, Airbyte ids, NASA key). |
| `dags/firewatch_pipeline.py` | The DAG (6 tasks). |

## Tasks and failure behaviour
`check_data_source` -> `trigger_airbyte_sync` -> `validate_raw_data` -> `run_dbt_models` -> `run_dbt_tests` -> `pipeline_complete`

- Retries: 2, delay `FIREWATCH_RETRY_DELAY_MIN` (default 5, use 1 for the demo). `catchup=False`, `max_active_runs=1`.
- A failed task leaves everything downstream as `upstream_failed`, so bad data never reaches the marts.
- `validate_raw_data` checks: required columns exist, at least `firewatch_min_rows` (default 1000) rows were loaded today,
  <= 5% invalid coordinates.
- The NASA key is only read from the Airflow Variable `firms_api_key` (masked in logs) and the DAG never prints the URL.

## Failure demo (B10)
1. Wrong key: set `AIRFLOW_VAR_FIRMS_API_KEY=wrong`, `FIREWATCH_RETRY_DELAY_MIN=1`, `docker compose up -d`, trigger the DAG.
   `check_data_source` fails, retries twice, the other five tasks show `upstream_failed`. Copy the log text.
2. Stopped Airbyte: stop the Airbyte containers in Docker Desktop (do not uninstall it), trigger the DAG; `trigger_airbyte_sync` fails and retries.
3. Restore the key / restart Airbyte, trigger again, all six green. **Blur the key in every screenshot.**

## Troubleshooting
| Symptom | Fix |
| --- | --- |
| Task fails "Signature verification failed" | All services must share `AIRFLOW__API_AUTH__JWT_SECRET` (set in the compose file); `docker compose down && up -d`. |
| `KeyError: FIREWATCH_PROJECT` on DAG import | `.env` not filled or not in `airflow/`. |
| Cannot reach Airbyte | Airbyte running? `curl localhost:8000` on the host; on Linux keep `extra_hosts`. |
| dbt `Permission denied` on `target/` | dbt is pointed at `/tmp/dbt_target`; make sure you did not override `DBT_TARGET_PATH`. |
| dbt cannot find profile/keyfile | `keys/sa-dbt.json` must exist in `airflow/keys/`. |
