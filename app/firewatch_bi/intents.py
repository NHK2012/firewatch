from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pandas as pd

UNKNOWN_QUESTION = (
    "I couldn't identify that question. Please try one of the supported "
    "FireWatch analytics questions."
)

DAILY_SQL = """
SELECT
  acq_date,
  total_detections,
  reliable_detections,
  non_reliable_detections,
  daytime_detections,
  nighttime_detections,
  average_frp,
  maximum_frp,
  seven_day_avg_detections
FROM `firewatch-de.firewatch_marts.mart_daily_fire_activity`
ORDER BY acq_date
"""

MONTHLY_SQL = """
SELECT
  month_id,
  month_start,
  total_detections,
  reliable_detections,
  non_reliable_detections,
  daytime_detections,
  nighttime_detections,
  average_frp,
  maximum_frp
FROM `firewatch-de.firewatch_marts.mart_monthly_fire_activity`
ORDER BY month_start
"""

REGIONAL_SQL = """
SELECT
  region_name,
  total_detections,
  reliable_detections,
  non_reliable_detections,
  reliable_percentage,
  daytime_detections,
  nighttime_detections,
  average_frp,
  maximum_frp
FROM `firewatch-de.firewatch_marts.mart_regional_fire_activity`
ORDER BY total_detections DESC
LIMIT @row_limit
"""

INTENSITY_SQL = """
SELECT
  intensity_category,
  total_detections,
  reliable_detections,
  non_reliable_detections,
  average_frp,
  maximum_frp
FROM `firewatch-de.firewatch_marts.mart_fire_intensity`
ORDER BY
  CASE intensity_category
    WHEN 'Low' THEN 1
    WHEN 'Moderate' THEN 2
    WHEN 'High' THEN 3
    ELSE 4
  END
"""

ANOMALIES_SQL = """
SELECT
  acq_date,
  acq_time,
  region_name,
  latitude,
  longitude,
  frp,
  confidence,
  satellite,
  anomaly_threshold
FROM `firewatch-de.firewatch_marts.mart_fire_anomalies`
ORDER BY frp DESC, acq_date DESC, acq_time DESC
LIMIT @row_limit
"""

OVERALL_SQL = """
WITH activity AS (
  SELECT
    SUM(total_detections) AS total_detections,
    SUM(reliable_detections) AS reliable_detections,
    SUM(non_reliable_detections) AS non_reliable_detections,
    SUM(daytime_detections) AS daytime_detections,
    SUM(nighttime_detections) AS nighttime_detections,
    MIN(acq_date) AS first_date,
    MAX(acq_date) AS latest_date
  FROM `firewatch-de.firewatch_marts.mart_daily_fire_activity`
),
intensity AS (
  SELECT
    SUM(IF(intensity_category = 'High', total_detections, 0))
      AS high_intensity_detections
  FROM `firewatch-de.firewatch_marts.mart_fire_intensity`
)
SELECT * FROM activity CROSS JOIN intensity
"""

RELIABILITY_SQL = """
SELECT
  SUM(total_detections) AS total_detections,
  SUM(reliable_detections) AS reliable_detections,
  SUM(non_reliable_detections) AS non_reliable_detections,
  SAFE_DIVIDE(
    SUM(reliable_detections) * 100.0,
    SUM(total_detections)
  ) AS reliable_percentage
FROM `firewatch-de.firewatch_marts.mart_daily_fire_activity`
"""

DAY_NIGHT_SQL = """
SELECT
  SUM(total_detections) AS total_detections,
  SUM(daytime_detections) AS daytime_detections,
  SUM(nighttime_detections) AS nighttime_detections,
  SUM(
    total_detections - daytime_detections - nighttime_detections
  ) AS other_daypart_detections
FROM `firewatch-de.firewatch_marts.mart_daily_fire_activity`
"""


@dataclass(frozen=True)
class IntentSpec:
    key: str
    label: str
    sql: str
    parameters: tuple[tuple[str, str, str | int | float], ...] = ()


INTENTS = {
    "overall": IntentSpec("overall", "Overall detection statistics", OVERALL_SQL),
    "daily": IntentSpec("daily", "Daily activity", DAILY_SQL),
    "monthly": IntentSpec("monthly", "Monthly activity", MONTHLY_SQL),
    "regional": IntentSpec(
        "regional",
        "Regional activity",
        REGIONAL_SQL,
        (("row_limit", "INT64", 12),),
    ),
    "intensity": IntentSpec("intensity", "Fire intensity", INTENSITY_SQL),
    "anomalies": IntentSpec(
        "anomalies",
        "High-FRP anomalies",
        ANOMALIES_SQL,
        (("row_limit", "INT64", 20),),
    ),
    "reliability": IntentSpec(
        "reliability", "Confidence and reliability", RELIABILITY_SQL
    ),
    "day_night": IntentSpec("day_night", "Day versus night", DAY_NIGHT_SQL),
}

_ROUTES = (
    ("reliability", re.compile(r"\b(confidence|reliab(?:le|ility)|non[- ]reliable)\b")),
    (
        "day_night",
        re.compile(
            r"\b(daytime|nighttime|diurnal|nocturnal|"
            r"day\s+(?:vs|versus|and|or)\s+night|"
            r"night\s+(?:vs|versus|and|or)\s+day)\b"
        ),
    ),
    (
        "anomalies",
        re.compile(
            r"\b(anomal(?:y|ies)|highest\s+frp|top\s+frp|"
            r"extreme\s+frp|large\s+frp)\b"
        ),
    ),
    ("intensity", re.compile(r"\b(intensity|intensities|low|moderate|high)\b")),
    ("regional", re.compile(r"\b(region|regions|regional|where|area|areas)\b")),
    ("monthly", re.compile(r"\b(month|monthly|month[- ]by[- ]month)\b")),
    (
        "daily",
        re.compile(r"\b(daily|day[- ]by[- ]day|per day|by date|daily activity)\b"),
    ),
    (
        "overall",
        re.compile(
            r"\b(overall|total|all detections|how many|count|statistics|"
            r"summary|overview|fire detections|active fire detections)\b"
        ),
    ),
)


def route_question(question: str) -> IntentSpec | None:
    """Map supported question wording to a fixed, application-owned query."""
    normalized = re.sub(r"\s+", " ", question.casefold()).strip()
    for key, pattern in _ROUTES:
        if pattern.search(normalized):
            return INTENTS[key]
    return None


def _number(value: Any) -> int:
    if value is None or pd.isna(value):
        return 0
    return int(value)


def _decimal(value: Any) -> float:
    if value is None or pd.isna(value):
        return 0.0
    return float(value)


def _date(value: Any) -> str:
    if value is None or pd.isna(value):
        return "the available reporting window"
    return pd.Timestamp(value).strftime("%b %d, %Y")


def answer_for(intent_key: str, data: pd.DataFrame) -> str:
    """Create a concise answer using only values returned by the selected mart."""
    if data.empty:
        return "The selected analytics mart returned no rows for this question."

    if intent_key == "overall":
        row = data.iloc[0]
        return (
            f"The daily mart records {_number(row['total_detections']):,} active-fire "
            f"detections from {_date(row['first_date'])} through "
            f"{_date(row['latest_date'])}. "
            f"{_number(row['high_intensity_detections']):,} are in the "
            "project-defined High FRP category."
        )

    if intent_key == "daily":
        return (
            f"Daily activity spans {_date(data['acq_date'].min())} through "
            f"{_date(data['acq_date'].max())} across {len(data):,} observed dates. "
            "The chart also shows the mart's rolling average over up to seven "
            "observed dates."
        )

    if intent_key == "monthly":
        total = _number(data["total_detections"].sum())
        peak = data.loc[data["total_detections"].idxmax()]
        return (
            f"The monthly mart totals {total:,} detections across {len(data):,} "
            f"months. The highest total is {peak['month_id']} with "
            f"{_number(peak['total_detections']):,} detections."
        )

    if intent_key == "regional":
        lead = data.iloc[0]
        return (
            f"{lead['region_name']} has the most detections among the returned "
            f"regions, with {_number(lead['total_detections']):,}. "
            "The table also compares reliability and day/night activity."
        )

    if intent_key == "intensity":
        distribution = ", ".join(
            f"{row.intensity_category}: {_number(row.total_detections):,}"
            for row in data.itertuples()
        )
        return (
            "The project-defined FRP distribution is "
            f"{distribution}. These categories are not official NASA fire classes."
        )

    if intent_key == "anomalies":
        lead = data.iloc[0]
        return (
            f"The highest returned FRP is {_decimal(lead['frp']):,.1f} MW on "
            f"{_date(lead['acq_date'])}; the mart's threshold is "
            f"{_decimal(lead['anomaly_threshold']):,.1f} MW. These records are "
            "thermal anomalies, not confirmed wildfires."
        )

    if intent_key == "reliability":
        row = data.iloc[0]
        return (
            f"{_number(row['reliable_detections']):,} of "
            f"{_number(row['total_detections']):,} detections are classified as "
            f"reliable ({_decimal(row['reliable_percentage']):.1f}%). "
            f"{_number(row['non_reliable_detections']):,} are non-reliable."
        )

    if intent_key == "day_night":
        row = data.iloc[0]
        daytime = _number(row["daytime_detections"])
        nighttime = _number(row["nighttime_detections"])
        if daytime == nighttime:
            comparison = "Daytime and nighttime totals are equal."
        else:
            lead = "daytime" if daytime > nighttime else "nighttime"
            comparison = f"There are more {lead} detections in the reporting window."
        return (
            f"{daytime:,} detections are marked daytime and {nighttime:,} "
            f"nighttime; {_number(row['other_daypart_detections']):,} have "
            f"another or unspecified daypart. {comparison}"
        )

    return "The selected intent has no answer formatter."
