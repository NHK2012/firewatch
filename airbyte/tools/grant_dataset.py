#!/usr/bin/env python3
"""Create a BigQuery dataset (if missing) and give one principal access to ONLY that dataset.
Run as the project owner (your own `gcloud auth login`). Safe to re-run."""
import argparse
import os
import subprocess
import sys

from google.cloud import bigquery
from google.oauth2.credentials import Credentials


def gcloud_token():
    r = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True,
                       shell=(os.name == "nt"))   # gcloud is gcloud.cmd on Windows
    if r.returncode or not r.stdout.strip():
        sys.exit("Could not get a token: run `gcloud auth login` first")
    return r.stdout.strip()


def ensure_dataset(bq, project, dataset, location):
    ref = bigquery.Dataset(f"{project}.{dataset}")
    ref.location = location
    ds = bq.create_dataset(ref, exists_ok=True)
    print(f"dataset {project}:{dataset} ready (location {ds.location})")
    if ds.location.upper() != location.upper():
        sys.exit(f"Dataset already exists in {ds.location}, expected {location}")
    return ds


def grant(bq, ds, member, access):
    entries = list(ds.access_entries)
    if any(e.entity_id == member and e.role == access for e in entries):
        print(f"{member} already has {access}")
        return False
    entries.append(bigquery.AccessEntry(access, "userByEmail", member))
    ds.access_entries = entries
    bq.update_dataset(ds, ["access_entries"])
    print(f"granted {access} on {ds.dataset_id} to {member}")
    return True


def main(argv=None, bq=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--member", required=True, help="service-account or user e-mail")
    ap.add_argument("--access", choices=["READER", "WRITER"], default="WRITER")
    ap.add_argument("--location", default="US")
    a = ap.parse_args(argv)
    bq = bq or bigquery.Client(project=a.project, credentials=Credentials(gcloud_token()))
    ds = ensure_dataset(bq, a.project, a.dataset, a.location)
    grant(bq, ds, a.member, a.access)
    kind = "serviceAccount" if a.member.endswith("gserviceaccount.com") else "user"
    print("\nAlso needed ONCE at project level (query/load jobs):")
    print(f"  gcloud projects add-iam-policy-binding {a.project} "
          f"--member={kind}:{a.member} --role=roles/bigquery.jobUser --condition=None")


if __name__ == "__main__":
    main()