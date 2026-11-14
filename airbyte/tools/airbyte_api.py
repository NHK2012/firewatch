#!/usr/bin/env python3
"""Small Airbyte public-API helper for B6/B9 (same calls the DAG makes).

  export AIRBYTE_CLIENT_ID=... AIRBYTE_CLIENT_SECRET=... AIRBYTE_CONNECTION_ID=...
  (the Airflow names AIRFLOW_VAR_AIRBYTE_CLIENT_ID / _CLIENT_SECRET / _CONNECTION_ID also work,
   so you can reuse the values from airflow/.env)
  python airbyte/tools/airbyte_api.py sync     # trigger + wait, prints elapsed time  (timed 5-day test, B9)
  python airbyte/tools/airbyte_api.py reset    # clear synced data + state so a new start_date is re-pulled

From your laptop the API is http://localhost:8000/api/public/v1 (override with AIRBYTE_API_URL).
Confirm field names against the API reference of your Airbyte version if a call is rejected.
"""
import os
import sys
import time

import requests

API = os.environ.get("AIRBYTE_API_URL", "http://localhost:8000/api/public/v1")


def cfg(name):
    """AIRBYTE_<name>, or the same value under the Airflow name AIRFLOW_VAR_AIRBYTE_<name>."""
    v = os.environ.get(f"AIRBYTE_{name}") or os.environ.get(f"AIRFLOW_VAR_AIRBYTE_{name}")
    if not v:
        sys.exit(f"Missing AIRBYTE_{name} (or AIRFLOW_VAR_AIRBYTE_{name}) in the environment")
    return v


def headers():
    r = requests.post(f"{API}/applications/token", timeout=30, json={
        "client_id": cfg("CLIENT_ID"),
        "client_secret": cfg("CLIENT_SECRET"),
        "grant-type": "client_credentials"})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def run(job_type):
    t0 = time.time()
    r = requests.post(f"{API}/jobs", headers=headers(), timeout=30,
                      json={"connectionId": cfg("CONNECTION_ID"), "jobType": job_type})
    if not r.ok:
        sys.exit(f"Airbyte refused the job: HTTP {r.status_code} {r.text[:200]}")
    job_id = r.json()["jobId"]
    while True:
        j = requests.get(f"{API}/jobs/{job_id}", headers=headers(), timeout=30).json()
        print(f"[{time.time() - t0:6.0f}s] job {job_id}: {j['status']}  rows={j.get('rowsSynced', '-')}")
        if j["status"] in ("succeeded", "failed", "cancelled", "incomplete"):
            print(f"Elapsed: {time.time() - t0:.0f} s  ({(time.time() - t0) / 60:.1f} min)")
            sys.exit(0 if j["status"] == "succeeded" else 1)
        time.sleep(15)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "sync":
        run("sync")
    elif cmd == "reset":
        # "reset" exists in all public-API versions; newer ones also accept "clear".
        run("reset")
    else:
        sys.exit(__doc__)
