from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

NAVY = "#0b1520"
IVORY = "#f4f0e7"
ORANGE = "#f07a3f"
AMBER = "#f4bd63"
TEAL = "#65c2b5"
MUTED = "#93a5b2"
GRID = "#536575"

_INTENSITY_COLORS = {
    "Low": TEAL,
    "Moderate": AMBER,
    "High": ORANGE,
    "Unknown": MUTED,
}


def _count(value: object) -> int:
    if value is None or pd.isna(value):
        return 0
    return int(value)


def _base_figure(height: int = 350) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(
        height=height,
        paper_bgcolor=NAVY,
        plot_bgcolor=NAVY,
        font={"family": "Inter, Segoe UI, sans-serif", "color": IVORY, "size": 12},
        margin={"l": 96, "r": 32, "t": 64, "b": 76},
        legend={
            "orientation": "h",
            "y": 1.12,
            "x": 0,
            "font": {"color": IVORY},
        },
        title={"font": {"color": IVORY}},
        hoverlabel={"bgcolor": "#132332", "font_color": IVORY},
    )
    figure.update_xaxes(
        gridcolor=GRID,
        zerolinecolor=GRID,
        linecolor=GRID,
        tickfont={"color": IVORY, "size": 14},
        title_font={"color": IVORY},
        automargin=True,
    )
    figure.update_yaxes(
        gridcolor=GRID,
        zerolinecolor=GRID,
        linecolor=GRID,
        tickfont={"color": IVORY, "size": 14},
        title_font={"color": IVORY},
        title_standoff=12,
        automargin=True,
    )
    return figure


def daily_figure(data: pd.DataFrame) -> go.Figure:
    frame = data.sort_values("acq_date")
    figure = _base_figure(390)
    figure.add_trace(
        go.Scatter(
            x=frame["acq_date"],
            y=frame["total_detections"],
            mode="lines",
            name="Detections",
            line={"color": ORANGE, "width": 2.5},
            fill="tozeroy",
            fillcolor="rgba(240, 122, 63, 0.10)",
            hovertemplate="%{x|%b %d, %Y}<br>%{y:,.0f} detections<extra></extra>",
        )
    )
    if "seven_day_avg_detections" in frame:
        figure.add_trace(
            go.Scatter(
                x=frame["acq_date"],
                y=frame["seven_day_avg_detections"],
                mode="lines",
                name="7 observed-day average",
                line={"color": TEAL, "width": 2, "dash": "dot"},
                hovertemplate="%{x|%b %d, %Y}<br>%{y:,.0f} average<extra></extra>",
            )
        )
    figure.update_layout(
        title={"text": "Daily detection signal", "font": {"color": IVORY}},
        yaxis_title="Detections",
        legend={
            "orientation": "h",
            "x": 0.5,
            "xanchor": "center",
            "y": -0.28,
            "font": {"color": IVORY},
        },
        margin={"l": 96, "r": 32, "t": 64, "b": 108},
    )
    figure.update_xaxes(title=None)
    return figure


def monthly_figure(data: pd.DataFrame) -> go.Figure:
    figure = _base_figure()
    figure.add_trace(
        go.Bar(
            x=data["month_id"],
            y=data["total_detections"],
            name="Detections",
            marker_color=ORANGE,
            customdata=data[["reliable_detections", "non_reliable_detections"]],
            hovertemplate=(
                "%{x}<br>%{y:,.0f} detections<br>"
                "Reliable: %{customdata[0]:,.0f}<br>"
                "Non-reliable: %{customdata[1]:,.0f}<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        title={"text": "Monthly activity", "font": {"color": IVORY}},
        yaxis_title="Detections",
        showlegend=False,
    )
    figure.update_xaxes(title=None)
    return figure


def regional_figure(data: pd.DataFrame) -> go.Figure:
    frame = data.sort_values("total_detections", ascending=True)
    figure = _base_figure(max(350, 28 * len(frame) + 70))
    figure.add_trace(
        go.Bar(
            x=frame["total_detections"],
            y=frame["region_name"],
            orientation="h",
            name="Detections",
            marker_color=TEAL,
            customdata=frame[["reliable_percentage"]],
            hovertemplate=(
                "%{y}<br>%{x:,.0f} detections<br>"
                "Reliable: %{customdata[0]:.1f}%<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        title={"text": "Regional detection load", "font": {"color": IVORY}},
        xaxis_title="Detections",
        margin={"l": 205, "r": 32, "t": 64, "b": 76},
        showlegend=False,
    )
    figure.update_yaxes(title=None, gridcolor=NAVY)
    return figure


def intensity_figure(data: pd.DataFrame) -> go.Figure:
    frame = data.copy()
    figure = _base_figure()
    figure.add_trace(
        go.Bar(
            x=frame["intensity_category"],
            y=frame["total_detections"],
            name="Detections",
            marker_color=[
                _INTENSITY_COLORS.get(category, MUTED)
                for category in frame["intensity_category"]
            ],
            customdata=frame[["average_frp", "maximum_frp"]],
            hovertemplate=(
                "%{x}<br>%{y:,.0f} detections<br>"
                "Mean FRP: %{customdata[0]:.1f} MW<br>"
                "Peak FRP: %{customdata[1]:.1f} MW<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        title={"text": "Project-defined FRP bands", "font": {"color": IVORY}},
        yaxis_title="Detections",
        showlegend=False,
    )
    figure.update_xaxes(title=None)
    return figure


def day_night_figure(daytime: int, nighttime: int) -> go.Figure:
    figure = _base_figure(310)
    figure.add_trace(
        go.Pie(
            labels=["Daytime", "Nighttime"],
            values=[daytime, nighttime],
            hole=0.68,
            sort=False,
            marker={"colors": [AMBER, TEAL], "line": {"color": NAVY, "width": 2}},
            textinfo="label+percent",
            textposition="inside",
            textfont={"color": NAVY, "size": 13},
            hovertemplate="%{label}: %{value:,.0f}<extra></extra>",
        )
    )
    figure.update_layout(
        title={"text": "Day / night detections", "font": {"color": IVORY}},
        showlegend=False,
        margin={"l": 32, "r": 32, "t": 56, "b": 32},
    )
    return figure


def reliability_figure(reliable: int, non_reliable: int) -> go.Figure:
    figure = _base_figure(310)
    figure.add_trace(
        go.Pie(
            labels=["Reliable", "Non-reliable"],
            values=[reliable, non_reliable],
            hole=0.68,
            sort=False,
            marker={"colors": [TEAL, ORANGE], "line": {"color": NAVY, "width": 2}},
            textinfo="label+percent",
            textposition="inside",
            textfont={"color": NAVY, "size": 13},
            hovertemplate="%{label}: %{value:,.0f}<extra></extra>",
        )
    )
    figure.update_layout(
        title={"text": "Confidence classification", "font": {"color": IVORY}},
        showlegend=False,
        margin={"l": 32, "r": 32, "t": 56, "b": 32},
    )
    return figure


def anomalies_figure(data: pd.DataFrame) -> go.Figure:
    figure = go.Figure()
    figure.add_trace(
        go.Scattergeo(
            lat=data["latitude"],
            lon=data["longitude"],
            mode="markers",
            text=data["region_name"],
            customdata=data[["frp", "acq_date", "confidence"]],
            marker={
                "size": 8,
                "color": data["frp"],
                "colorscale": [[0, TEAL], [0.55, AMBER], [1, ORANGE]],
                "showscale": True,
                "colorbar": {
                    "title": {"text": "FRP (MW)", "font": {"color": IVORY}},
                    "tickfont": {"color": IVORY},
                },
                "line": {"width": 0.5, "color": NAVY},
                "opacity": 0.86,
            },
            hovertemplate=(
                "%{text}<br>%{customdata[1]|%b %d, %Y}<br>"
                "%{customdata[0]:.1f} MW<br>Confidence: %{customdata[2]}"
                "<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        height=390,
        paper_bgcolor=NAVY,
        plot_bgcolor=NAVY,
        font={"family": "Inter, Segoe UI, sans-serif", "color": IVORY, "size": 12},
        title={"text": "Highest-FRP anomaly locations", "font": {"color": IVORY}},
        margin={"l": 8, "r": 8, "t": 30, "b": 8},
        geo={
            "bgcolor": NAVY,
            "showland": True,
            "landcolor": "#1a2a36",
            "showocean": True,
            "oceancolor": NAVY,
            "showcoastlines": True,
            "coastlinecolor": "#536575",
            "showframe": False,
            "projection_type": "natural earth",
            "lataxis": {"showgrid": False},
            "lonaxis": {"showgrid": False},
        },
    )
    return figure


def intent_figure(intent_key: str, data: pd.DataFrame) -> go.Figure | None:
    if data.empty:
        return None
    if intent_key == "overall":
        row = data.iloc[0]
        return reliability_figure(
            _count(row["reliable_detections"]),
            _count(row["non_reliable_detections"]),
        )
    if intent_key == "daily":
        return daily_figure(data)
    if intent_key == "monthly":
        return monthly_figure(data)
    if intent_key == "regional":
        return regional_figure(data)
    if intent_key == "intensity":
        return intensity_figure(data)
    if intent_key == "anomalies":
        return anomalies_figure(data)
    if intent_key == "reliability":
        row = data.iloc[0]
        return reliability_figure(
            _count(row["reliable_detections"]),
            _count(row["non_reliable_detections"]),
        )
    if intent_key == "day_night":
        row = data.iloc[0]
        return day_night_figure(
            _count(row["daytime_detections"]),
            _count(row["nighttime_detections"]),
        )
    return None
