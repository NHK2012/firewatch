import unittest
import re
from unittest.mock import Mock, patch

import pandas as pd
from google.api_core.exceptions import Forbidden
from google.auth.exceptions import DefaultCredentialsError

from firewatch_bi.data import (
    MAXIMUM_BYTES_BILLED,
    DataAccessError,
    get_bigquery_client,
    query_mart,
)
from firewatch_bi.intents import (
    ANOMALIES_SQL,
    DAILY_SQL,
    INTENTS,
    REGIONAL_SQL,
    UNKNOWN_QUESTION,
    answer_for,
    route_question,
)
from firewatch_bi.visuals import intent_figure


class IntentRoutingTests(unittest.TestCase):
    def test_supported_examples_route_to_their_intents(self):
        examples = {
            "How many fire detections are recorded?": "overall",
            "Show me daily fire activity.": "daily",
            "How has activity changed month by month?": "monthly",
            "Which regions have the highest fire activity?": "regional",
            "Show the distribution of fire intensity.": "intensity",
            "Show the highest FRP anomalies.": "anomalies",
            "How many detections are reliable?": "reliability",
            "Are there more daytime or nighttime detections?": "day_night",
        }
        for question, expected_key in examples.items():
            with self.subTest(question=question):
                result = route_question(question)
                self.assertIsNotNone(result)
                self.assertEqual(result.key, expected_key)

    def test_unrecognized_question_does_not_select_a_query(self):
        self.assertIsNone(route_question("Can you predict tomorrow's weather?"))
        self.assertIn("couldn't identify", UNKNOWN_QUESTION)

    def test_empty_results_have_a_clear_empty_state(self):
        empty = pd.DataFrame()
        self.assertIn("returned no rows", answer_for("daily", empty))
        self.assertIsNone(intent_figure("daily", empty))

    def test_empty_aggregate_results_remain_renderable(self):
        empty_aggregate = pd.DataFrame(
            [
                {
                    "total_detections": pd.NA,
                    "reliable_detections": pd.NA,
                    "non_reliable_detections": pd.NA,
                    "reliable_percentage": pd.NA,
                }
            ]
        )
        self.assertIn("0 of 0 detections", answer_for("reliability", empty_aggregate))
        self.assertIsNotNone(intent_figure("reliability", empty_aggregate))

    def test_authentication_failure_has_a_friendly_message(self):
        get_bigquery_client.clear()
        with (
            patch("firewatch_bi.data._credentials", return_value=None),
            patch(
                "firewatch_bi.data.bigquery.Client",
                side_effect=DefaultCredentialsError("sensitive auth detail"),
            ),
        ):
            with self.assertRaisesRegex(DataAccessError, "could not authenticate"):
                get_bigquery_client()
        get_bigquery_client.clear()

    def test_query_failure_has_a_friendly_message(self):
        query_mart.clear()
        client = Mock()
        client.query.side_effect = Forbidden("private query detail")
        with (
            patch("firewatch_bi.data.get_bigquery_client", return_value=client),
        ):
            with self.assertRaisesRegex(DataAccessError, "analytics mart could not be queried"):
                query_mart(DAILY_SQL)
        query_mart.clear()

    def test_unapproved_sql_and_unsafe_limits_are_rejected(self):
        query_mart.clear()
        with self.assertRaisesRegex(DataAccessError, "predefined, read-only"):
            query_mart("DELETE FROM `firewatch-de.firewatch_marts.mart_daily_fire_activity`")
        with self.assertRaisesRegex(DataAccessError, "predefined, read-only"):
            query_mart("How many fire detections are recorded?")
        with self.assertRaisesRegex(DataAccessError, "parameters are invalid"):
            query_mart(REGIONAL_SQL, (("row_limit", "INT64", 1_000_000),))

    def test_every_query_uses_the_five_gigabyte_cap(self):
        query_mart.clear()
        client = Mock()
        job = Mock()
        job.to_dataframe.return_value = pd.DataFrame([{"ok": True}])
        client.query.return_value = job

        with patch("firewatch_bi.data.get_bigquery_client", return_value=client):
            for intent in INTENTS.values():
                query_mart.clear()
                query_mart(intent.sql, intent.parameters)
                config = client.query.call_args.kwargs["job_config"]
                self.assertEqual(config.maximum_bytes_billed, MAXIMUM_BYTES_BILLED)
            query_mart.clear()
            query_mart(ANOMALIES_SQL, (("row_limit", "INT64", 100),))
            config = client.query.call_args.kwargs["job_config"]
            self.assertEqual(config.maximum_bytes_billed, 5_000_000_000)
        query_mart.clear()

    def test_every_intent_queries_only_the_five_marts(self):
        allowed_marts = {
            "mart_daily_fire_activity",
            "mart_regional_fire_activity",
            "mart_monthly_fire_activity",
            "mart_fire_intensity",
            "mart_fire_anomalies",
        }
        for intent in INTENTS.values():
            referenced = re.findall(r"(?:FROM|JOIN)\s+`([^`]+)`", intent.sql, re.I)
            with self.subTest(intent=intent.key):
                self.assertTrue(referenced)
                self.assertRegex(intent.sql, r"(?is)^\s*(SELECT|WITH)\b")
                self.assertTrue(
                    all(
                        table.startswith("firewatch-de.firewatch_marts.")
                        and table.rsplit(".", 1)[-1] in allowed_marts
                        for table in referenced
                    )
                )


if __name__ == "__main__":
    unittest.main()
