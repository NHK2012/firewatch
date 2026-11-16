from __future__ import annotations

from html import escape

import streamlit as st

from firewatch_bi.data import DataAccessError, PROJECT_ID, query_mart
from firewatch_bi.intents import (
    ANOMALIES_SQL,
    DAILY_SQL,
    INTENSITY_SQL,
    MONTHLY_SQL,
    REGIONAL_SQL,
    UNKNOWN_QUESTION,
    answer_for,
    route_question,
)
from firewatch_bi.visuals import (
    anomalies_figure,
    daily_figure,
    intensity_figure,
    intent_figure,
    monthly_figure,
    regional_figure,
    day_night_figure,
    reliability_figure,
)

REGION_PARAMETERS = (("row_limit", "INT64", 12),)
EXPLORER_ANOMALY_PARAMETERS = (("row_limit", "INT64", 100),)

EXAMPLE_QUESTIONS = (
    "How many fire detections are recorded?",
    "Show me daily fire activity.",
    "How has activity changed month by month?",
    "Which regions have the highest fire activity?",
    "Show the distribution of fire intensity.",
    "Show the highest FRP anomalies.",
    "How many detections are reliable?",
    "Are there more daytime or nighttime detections?",
)


def apply_visual_identity() -> None:
    st.markdown(
        """
        <style>
        :root {
            --fw-bg: #0b1520;
            --fw-panel: #111f2b;
            --fw-ivory: #f4f0e7;
            --fw-muted: #93a5b2;
            --fw-orange: #f07a3f;
            --fw-teal: #65c2b5;
            --fw-rule: rgba(147, 165, 178, 0.20);
        }
        [data-testid="stAppViewContainer"] {
            background: var(--fw-bg);
            color: var(--fw-ivory);
        }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stSidebar"] {
            background: #0e1b27;
            border-right: 1px solid var(--fw-rule);
        }
        [data-testid="stSidebar"] > div:first-child { padding-top: 1.2rem; }
        .block-container {
            max-width: 1480px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        h1, h2, h3 { color: var(--fw-ivory); letter-spacing: -0.035em; }
        h1 { font-size: clamp(2.4rem, 5vw, 4.1rem) !important; }
        h2 { font-size: 1.55rem !important; }
        p, label, [data-testid="stMarkdownContainer"] {
            color: var(--fw-ivory);
        }
        .fw-eyebrow, .fw-kicker {
            color: var(--fw-teal);
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.16em;
            text-transform: uppercase;
        }
        .fw-deck {
            color: #b7c3ca;
            font-size: 1.02rem;
            max-width: 780px;
            line-height: 1.65;
        }
        .fw-rule {
            border: 0;
            border-top: 1px solid var(--fw-rule);
            margin: 1.3rem 0 1.7rem;
        }
        .fw-sidebar-mark {
            color: var(--fw-orange);
            font-size: 0.76rem;
            font-weight: 800;
            letter-spacing: 0.2em;
            text-transform: uppercase;
        }
        .fw-note {
            color: var(--fw-muted);
            font-size: 0.82rem;
            line-height: 1.55;
        }
        [data-testid="stMetric"] {
            border-top: 2px solid var(--fw-orange);
            padding: 0.8rem 0.2rem 0.6rem;
        }
        [data-testid="stMetricLabel"] p {
            color: var(--fw-muted);
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }
        [data-testid="stMetricValue"] {
            color: var(--fw-ivory);
            font-variant-numeric: tabular-nums;
        }
        [data-testid="stPlotlyChart"] {
            border-bottom: 1px solid var(--fw-rule);
            padding-bottom: 0.6rem;
        }
        div[data-testid="stButton"] > button {
            border: 1px solid var(--fw-rule);
            border-radius: 4px;
            background: #132332;
            color: var(--fw-ivory);
            text-align: left;
            min-height: 2.8rem;
        }
        div[data-testid="stButton"] > button:hover {
            border-color: var(--fw-orange);
            color: #ffd1ad;
        }
        div[data-testid="stChatInput"] {
            border-color: var(--fw-teal);
        }
        @media (max-width: 720px) {
            .block-container { padding: 1.2rem 1rem 2rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def load_data(
    sql: str,
    label: str,
    parameters: tuple[tuple[str, str, str | int | float], ...] = (),
):
    try:
        with st.spinner(f"Reading {label} from BigQuery..."):
            return query_mart(sql, parameters)
    except DataAccessError as error:
        st.warning(f"{label} is temporarily unavailable. {error}")
        return None


def format_count(value: object) -> str:
    if value is None:
        return "--"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError, OverflowError):
        return "--"


def render_empty(label: str) -> None:
    st.info(f"No {label.lower()} are available in the current analytics mart.")


def render_overview() -> None:
    st.markdown('<div class="fw-kicker">01 / Current signal</div>', unsafe_allow_html=True)
    daily = load_data(DAILY_SQL, "daily activity")
    regional = load_data(REGIONAL_SQL, "regional activity", REGION_PARAMETERS)
    intensity = load_data(INTENSITY_SQL, "intensity distribution")

    if daily is None and regional is None and intensity is None:
        st.info("The live overview will appear when FireWatch can reach BigQuery.")
        return

    total = int(daily["total_detections"].sum()) if daily is not None and not daily.empty else None
    reliable = int(daily["reliable_detections"].sum()) if daily is not None and not daily.empty else None
    high_intensity = None
    if intensity is not None and not intensity.empty:
        high_rows = intensity.loc[intensity["intensity_category"] == "High", "total_detections"]
        high_intensity = int(high_rows.sum())
    classified_regions = None
    if regional is not None and not regional.empty:
        classified_regions = int((regional["region_name"] != "Unclassified").sum())

    latest = daily["acq_date"].max() if daily is not None and not daily.empty else None
    first = daily["acq_date"].min() if daily is not None and not daily.empty else None
    date_range = (
        f"{first:%b %d, %Y} - {latest:%b %d, %Y}"
        if first is not None and latest is not None
        else "Date range unavailable"
    )

    st.markdown(
        f'<div class="fw-eyebrow">VIIRS S-NPP / Latest available date: '
        f'{latest:%b %d, %Y}</div>'
        if latest is not None
        else '<div class="fw-eyebrow">VIIRS S-NPP / Latest date unavailable</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="fw-note">Detection totals cover the date range represented in '
        "the live daily mart. They are satellite-observed thermal anomalies, "
        "not confirmed wildfires.</p>",
        unsafe_allow_html=True,
    )

    metrics = st.columns(4)
    metrics[0].metric(
        "Active-fire detections",
        format_count(total),
        help=f"Sum of deduplicated daily mart counts for {date_range}.",
    )
    metrics[1].metric(
        "Reliable detections",
        format_count(reliable),
        help="Nominal or high confidence according to the normalized FIRMS confidence field.",
    )
    metrics[2].metric(
        "High-intensity detections",
        format_count(high_intensity),
        help="Project-defined High FRP category (FRP at or above the configured 50 MW threshold).",
    )
    metrics[3].metric(
        "Classified regions",
        format_count(classified_regions),
        help="Distinct region rows excluding the Unclassified bucket.",
    )

    st.markdown('<hr class="fw-rule">', unsafe_allow_html=True)
    st.markdown('<div class="fw-kicker">02 / Activity and geography</div>', unsafe_allow_html=True)
    left, right = st.columns([1.7, 1])
    with left:
        st.subheader("Daily detection activity")
        if daily is None:
            st.caption("Daily activity is unavailable.")
        elif daily.empty:
            render_empty("daily activity")
        else:
            st.plotly_chart(daily_figure(daily), width="stretch", key="overview-daily")
    with right:
        st.subheader("Regional distribution")
        if regional is None:
            st.caption("Regional activity is unavailable.")
        elif regional.empty:
            render_empty("regional activity")
        else:
            st.plotly_chart(
                regional_figure(regional),
                width="stretch",
                key="overview-regions",
            )

    st.markdown('<hr class="fw-rule">', unsafe_allow_html=True)
    st.markdown('<div class="fw-kicker">03 / Detection characteristics</div>', unsafe_allow_html=True)
    left, middle, right = st.columns([1.25, 1, 0.9])
    with left:
        st.subheader("FRP intensity distribution")
        if intensity is None:
            st.caption("Intensity data is unavailable.")
        elif intensity.empty:
            render_empty("intensity data")
        else:
            st.plotly_chart(
                intensity_figure(intensity),
                width="stretch",
                key="overview-intensity",
            )
            st.caption("Project-defined FRP bands, not official NASA fire classes.")
    with middle:
        st.subheader("Day / night activity")
        if daily is None or daily.empty:
            st.caption("Day/night totals are unavailable.")
        else:
            st.plotly_chart(
                day_night_figure(
                    int(daily["daytime_detections"].sum()),
                    int(daily["nighttime_detections"].sum()),
                ),
                width="stretch",
                key="overview-day-night",
            )
    with right:
        st.subheader("Confidence")
        if daily is None or daily.empty:
            st.caption("Confidence totals are unavailable.")
        else:
            st.plotly_chart(
                reliability_figure(
                    int(daily["reliable_detections"].sum()),
                    int(daily["non_reliable_detections"].sum()),
                ),
                width="stretch",
                key="overview-confidence",
            )
    st.caption(f"Observed daily mart coverage: {date_range}.")


def render_explorer() -> None:
    st.markdown('<div class="fw-kicker">04 / Fire activity explorer</div>', unsafe_allow_html=True)
    st.title("Explore the signal")
    st.markdown(
        "Compare activity across observed dates, regions, FRP bands, and high-FRP "
        "records. All views read the published BigQuery marts."
    )
    daily_tab, monthly_tab, regional_tab, intensity_tab, anomaly_tab = st.tabs(
        ["Daily", "Monthly", "Regions", "Intensity", "Anomalies"]
    )

    with daily_tab:
        daily = load_data(DAILY_SQL, "daily activity")
        if daily is None:
            st.caption("Daily activity is unavailable.")
        elif daily.empty:
            render_empty("daily activity")
        else:
            window = st.radio(
                "Observed-date window",
                ["All observed dates", "Last 60", "Last 30"],
                horizontal=True,
                key="explorer-daily-window",
            )
            visible = daily.sort_values("acq_date")
            if window == "Last 60":
                visible = visible.tail(60)
            elif window == "Last 30":
                visible = visible.tail(30)
            st.plotly_chart(
                daily_figure(visible),
                width="stretch",
                key="explorer-daily-chart",
            )
            st.dataframe(visible, hide_index=True, width="stretch")
            st.caption("The rolling average uses up to seven observed dates; missing dates are not filled with zero.")

    with monthly_tab:
        monthly = load_data(MONTHLY_SQL, "monthly activity")
        if monthly is None:
            st.caption("Monthly activity is unavailable.")
        elif monthly.empty:
            render_empty("monthly activity")
        else:
            st.plotly_chart(
                monthly_figure(monthly),
                width="stretch",
                key="explorer-monthly-chart",
            )
            st.dataframe(monthly, hide_index=True, width="stretch")

    with regional_tab:
        regional = load_data(REGIONAL_SQL, "regional activity", REGION_PARAMETERS)
        if regional is None:
            st.caption("Regional activity is unavailable.")
        elif regional.empty:
            render_empty("regional activity")
        else:
            st.plotly_chart(
                regional_figure(regional),
                width="stretch",
                key="explorer-regional-chart",
            )
            st.dataframe(regional, hide_index=True, width="stretch")

    with intensity_tab:
        intensity = load_data(INTENSITY_SQL, "intensity distribution")
        if intensity is None:
            st.caption("Intensity data is unavailable.")
        elif intensity.empty:
            render_empty("intensity data")
        else:
            st.plotly_chart(
                intensity_figure(intensity),
                width="stretch",
                key="explorer-intensity-chart",
            )
            st.dataframe(intensity, hide_index=True, width="stretch")
            st.caption("FRP intensity bands are defined by this project and are not official NASA classifications.")

    with anomaly_tab:
        anomalies = load_data(
            ANOMALIES_SQL,
            "high-FRP anomalies",
            EXPLORER_ANOMALY_PARAMETERS,
        )
        if anomalies is None:
            st.caption("High-FRP anomaly data is unavailable.")
        elif anomalies.empty:
            render_empty("high-FRP anomalies")
        else:
            st.plotly_chart(
                anomalies_figure(anomalies),
                width="stretch",
                key="explorer-anomaly-map",
            )
            st.dataframe(anomalies, hide_index=True, width="stretch")
            st.caption("Showing up to 100 highest-FRP rows. An anomaly is a thermal detection, not a confirmed wildfire.")


def render_conversation_result(message: dict, index: int) -> None:
    if message.get("error"):
        st.warning(message["error"])
    elif message.get("data") is not None:
        data = message["data"]
        if data.empty:
            st.info("The selected mart returned no matching records.")
        else:
            figure = intent_figure(message["intent"], data)
            if figure is not None:
                st.plotly_chart(
                    figure,
                    width="stretch",
                    key=f"conversation-chart-{index}",
                )
            if message["intent"] in {"regional", "anomalies"}:
                st.dataframe(data, hide_index=True, width="stretch")
    if message.get("sql"):
        with st.expander("View executed SQL"):
            st.code(message["sql"], language="sql")
            parameters = message.get("parameters", ())
            if parameters:
                bound_values = ", ".join(f"{name} = {value}" for name, _, value in parameters)
                st.caption(f"Bound parameters: {bound_values}")


def submit_question(question: str) -> None:
    conversation = st.session_state.setdefault("firewatch_conversation", [])
    conversation.append({"role": "user", "content": question})
    intent = route_question(question)
    if intent is None:
        conversation.append({"role": "assistant", "content": UNKNOWN_QUESTION})
        del conversation[:-20]
        return

    try:
        with st.spinner(f"Querying {intent.label.lower()}..."):
            data = query_mart(intent.sql, intent.parameters)
    except DataAccessError as error:
        conversation.append(
            {
                "role": "assistant",
                "content": "I couldn't retrieve that FireWatch result just now.",
                "intent": intent.key,
                "sql": intent.sql,
                "parameters": intent.parameters,
                "error": str(error),
            }
        )
        del conversation[:-20]
        return

    conversation.append(
        {
            "role": "assistant",
            "content": answer_for(intent.key, data),
            "intent": intent.key,
            "sql": intent.sql,
            "parameters": intent.parameters,
            "data": data,
        }
    )
    del conversation[:-20]


def render_conversation() -> None:
    st.markdown('<div class="fw-kicker">05 / Conversational intelligence</div>', unsafe_allow_html=True)
    st.title("Ask FireWatch")
    st.markdown(
        "Ask about the analytics marts in plain language. FireWatch routes only "
        "to its fixed, reviewed query catalogue; your question is never executed as SQL."
    )
    with st.expander("Try a supported question", expanded=True):
        columns = st.columns(4)
        selected_question = None
        for index, example in enumerate(EXAMPLE_QUESTIONS):
            if columns[index % 4].button(
                example,
                key=f"example-question-{index}",
                width="stretch",
            ):
                selected_question = example

    question = st.chat_input("Ask about activity, regions, FRP, confidence, or day/night...")
    submitted = selected_question or question
    if submitted:
        submit_question(submitted)

    conversation = st.session_state.get("firewatch_conversation", [])
    for index, message in enumerate(conversation):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                render_conversation_result(message, index)


def main() -> None:
    apply_visual_identity()
    with st.sidebar:
        st.markdown('<div class="fw-sidebar-mark">FireWatch / VIIRS</div>', unsafe_allow_html=True)
        st.markdown('<p class="fw-note">Active-fire detection intelligence</p>', unsafe_allow_html=True)
        page = st.radio(
            "Navigate",
            ["Overview", "Activity explorer", "Ask FireWatch"],
            label_visibility="collapsed",
        )
        if st.button("Refresh live data", width="stretch"):
            query_mart.clear()
            st.rerun()
        st.markdown('<hr class="fw-rule">', unsafe_allow_html=True)
        st.markdown(
            f'<p class="fw-note"><strong>BigQuery project</strong><br>{escape(PROJECT_ID)}<br><br>'
            "<strong>Data source</strong><br>Published FireWatch analytics marts<br><br>"
            "Detection records indicate thermal anomalies; they do not confirm a wildfire.</p>",
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="fw-eyebrow">Earth observation / Active-fire intelligence</div>',
        unsafe_allow_html=True,
    )
    st.title("FireWatch")
    st.markdown(
        '<p class="fw-deck">Read the changing thermal signal from orbit. Explore '
        "deduplicated VIIRS S-NPP active-fire detections, compare their intensity "
        "and geography, and question the data in natural language.</p>",
        unsafe_allow_html=True,
    )
    if page == "Overview":
        render_overview()
    elif page == "Activity explorer":
        render_explorer()
    else:
        render_conversation()

    st.markdown('<hr class="fw-rule">', unsafe_allow_html=True)
    st.markdown(
        '<p class="fw-note">FireWatch reports satellite active-fire detections. '
        "These thermal anomalies may include agricultural burning, industrial "
        "heat sources, and other events; they are not confirmed wildfire reports.</p>",
        unsafe_allow_html=True,
    )


