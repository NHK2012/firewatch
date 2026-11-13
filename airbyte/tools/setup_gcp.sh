#!/usr/bin/env bash
# B2 - datasets, service accounts, roles. Run ONCE, from the repo root, after `gcloud auth login`.
# Usage: PROJECT_ID=firewatch-de-xx TEAMMATE_EMAIL=neha@gmail.com bash airbyte/tools/setup_gcp.sh
# Safe to re-run (create commands tolerate "already exists").
set -uo pipefail
: "${PROJECT_ID:?}"; : "${TEAMMATE_EMAIL:?}"
LOC=US

# Pick a working Python (on Windows, python3 is often a Store stub that fails).
PY=""
for c in py python python3; do
  if "$c" -c "import sys" >/dev/null 2>&1; then PY="$c"; break; fi
done
[ -n "$PY" ] || { echo "No working Python found (install Python 3.11/3.12 and tick 'Add to PATH')"; exit 1; }
"$PY" -c "import google.cloud.bigquery" 2>/dev/null || { echo "Run: $PY -m pip install google-cloud-bigquery"; exit 1; }

gcloud config set project "$PROJECT_ID"
# New projects have these APIs off; enabling them avoids interactive prompts below.
gcloud services enable bigquery.googleapis.com iam.googleapis.com cloudresourcemanager.googleapis.com

for ds in firewatch_raw firewatch_staging firewatch_marts; do
  bq --location=$LOC mk --dataset "$PROJECT_ID:$ds" 2>&1 | grep -v "already exists" || true
done

for sa in sa-airbyte sa-dbt sa-app; do
  gcloud iam service-accounts create "$sa" 2>&1 | grep -v "already exists" || true
done
email() { echo "$1@$PROJECT_ID.iam.gserviceaccount.com"; }
grant() { gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="$1" --role="$2" --condition=None >/dev/null; }

# sa-airbyte, sa-dbt: write to datasets + run jobs (guide 3.1 table)
for sa in sa-airbyte sa-dbt; do
  grant "serviceAccount:$(email $sa)" roles/bigquery.dataEditor
  grant "serviceAccount:$(email $sa)" roles/bigquery.jobUser
done
# sa-app: may run query jobs; may READ firewatch_marts only (dataset-level, below)
grant "serviceAccount:$(email sa-app)" roles/bigquery.jobUser
# teammate: query + edit, so both can work
grant "user:$TEAMMATE_EMAIL" roles/bigquery.dataEditor
grant "user:$TEAMMATE_EMAIL" roles/bigquery.jobUser

# dataset-level read-only access for sa-app on marts
TOKEN="$(gcloud auth print-access-token)" "$PY" - "$PROJECT_ID" "$(email sa-app)" <<'PY'
import os, sys
from google.cloud import bigquery
from google.oauth2.credentials import Credentials
project, sa = sys.argv[1], sys.argv[2]
# uses your `gcloud auth login` token, so no separate application-default login is needed
c = bigquery.Client(project=project, credentials=Credentials(os.environ["TOKEN"]))
ds = c.get_dataset(f"{project}.firewatch_marts")
entries = list(ds.access_entries)
if not any(e.entity_id == sa for e in entries):
    entries.append(bigquery.AccessEntry("READER", "userByEmail", sa))
    ds.access_entries = entries
    c.update_dataset(ds, ["access_entries"])
print("sa-app is READER on firewatch_marts")
PY

# keys -> ./keys (git-ignored). Do NOT share over Git, chat screenshots or the report.
mkdir -p keys
for sa in sa-airbyte sa-dbt sa-app; do
  [ -f "keys/$sa.json" ] || gcloud iam service-accounts keys create "keys/$sa.json" --iam-account="$(email $sa)"
done
echo "Done. Send keys/sa-dbt.json and keys/sa-app.json to Neha over a PRIVATE channel only."
echo "Now verify: python airbyte/tools/verify_warehouse.py --check-roles"