# Set the tag to the SAME version as in docker-compose.yaml (download that file from the Airflow docs)
FROM apache/airflow:3.0.2

USER airflow

RUN pip install --no-cache-dir google-cloud-bigquery requests

# dbt gets its own virtualenv so its dependencies never clash with Airflow's
RUN python -m venv /home/airflow/dbt-venv \
 && /home/airflow/dbt-venv/bin/pip install --no-cache-dir dbt-bigquery
