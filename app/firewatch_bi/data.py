from __future__ import annotations

import logging
import os
from pathlib import Path
import re

import streamlit as st
from google.api_core.exceptions import GoogleAPIError
from google.auth.exceptions import DefaultCredentialsError, GoogleAuthError
from google.cloud import bigquery
from google.oauth2 import service_account
from streamlit.errors import StreamlitSecretNotFoundError

from .intents import INTENTS

PROJECT_ID = os.getenv("FIREWATCH_PROJECT", "firewatch-de")
MAXIMUM_BYTES_BILLED = 5_000_000_000
QUERY_LOCATION = "US"
APPROVED_SQL = frozenset(intent.sql for intent in INTENTS.values())

_LOGGER = logging.getLogger(__name__)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class DataAccessError(RuntimeError):
    """A safe, user-facing failure while accessing the BigQuery marts."""


def _validate_query(
    sql: str,
    parameters: tuple[tuple[str, str, str | int | float], ...],
) -> None:
    if sql not in APPROVED_SQL or not re.match(r"\s*(SELECT|WITH)\b", sql, re.IGNORECASE):
        raise DataAccessError(
            "Only predefined, read-only FireWatch queries against approved marts can run."
        )

    uses_row_limit = "@row_limit" in sql
    valid_row_limit = (
        len(parameters) == 1
        and parameters[0][0:2] == ("row_limit", "INT64")
        and isinstance(parameters[0][2], int)
        and not isinstance(parameters[0][2], bool)
        and 1 <= parameters[0][2] <= 100
    )
    if uses_row_limit != bool(parameters) or (parameters and not valid_row_limit):
        raise DataAccessError("The fixed FireWatch query parameters are invalid.")


def _credentials() -> service_account.Credentials | None:
    try:
        secret_account = st.secrets.get("gcp_service_account")
    except (KeyError, StreamlitSecretNotFoundError):
        secret_account = None

    if secret_account:
        return service_account.Credentials.from_service_account_info(
            dict(secret_account)
        )

    configured_keyfile = (
        os.getenv("FIREWATCH_APP_KEYFILE")
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    )
    keyfile = (
        Path(configured_keyfile).expanduser()
        if configured_keyfile
        else _PROJECT_ROOT / "keys" / "sa-app.json"
    )
    if keyfile.is_file():
        return service_account.Credentials.from_service_account_file(str(keyfile))

    return None


@st.cache_resource
def get_bigquery_client() -> bigquery.Client:
    try:
        credentials = _credentials()
        return bigquery.Client(project=PROJECT_ID, credentials=credentials)
    except (DefaultCredentialsError, GoogleAuthError, OSError, ValueError) as exc:
        _LOGGER.warning("FireWatch BigQuery authentication failed (%s)", type(exc).__name__)
        raise DataAccessError(
            "FireWatch could not authenticate to BigQuery. Configure the "
            "sa-app credentials or application default credentials, then retry."
        ) from exc


@st.cache_data(ttl=300, show_spinner=False)
def query_mart(
    sql: str,
    parameters: tuple[tuple[str, str, str | int | float], ...] = (),
):
    """Execute an application-owned query against the analytics marts."""
    _validate_query(sql, parameters)
    try:
        job_config = bigquery.QueryJobConfig(
            maximum_bytes_billed=MAXIMUM_BYTES_BILLED,
            use_query_cache=True,
            query_parameters=[
                bigquery.ScalarQueryParameter(name, type_name, value)
                for name, type_name, value in parameters
            ],
        )
        job = get_bigquery_client().query(
            sql,
            job_config=job_config,
            location=QUERY_LOCATION,
        )
        return job.to_dataframe(create_bqstorage_client=False)
    except (GoogleAPIError, GoogleAuthError) as exc:
        _LOGGER.warning("FireWatch mart query failed (%s)", type(exc).__name__)
        raise DataAccessError(
            "The analytics mart could not be queried. Check BigQuery access and "
            "billing, then retry."
        ) from exc
