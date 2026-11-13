# airflow/ (Bhagyashri)

1. Download `docker-compose.yaml` for your Airflow version from the Airflow docs into this folder.
2. Replace `image:` with `build: .`; mount `../dbt` -> `/opt/airflow/dbt` and `./keys` -> `/opt/airflow/keys`.
3. Add env: FIREWATCH_PROJECT, DBT_KEYFILE=/opt/airflow/keys/sa-dbt.json, GOOGLE_APPLICATION_CREDENTIALS,
   AIRFLOW_VAR_FIRMS_API_KEY, AIRFLOW_VAR_AIRBYTE_CONNECTION_ID, AIRFLOW_VAR_AIRBYTE_CLIENT_ID,
   AIRFLOW_VAR_AIRBYTE_CLIENT_SECRET.
4. `mkdir -p dags logs plugins config keys && echo "AIRFLOW_UID=50000" > .env`
5. DAG goes in `dags/firewatch_pipeline.py` (tasks: check source, trigger Airbyte, validate raw,
   dbt seed+run, dbt test, finish).
