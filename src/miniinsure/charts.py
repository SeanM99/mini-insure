"""Plotly chart helpers for MiniInsure Streamlit pages."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def mix_bar(df: pd.DataFrame, column: str, title: str) -> go.Figure:
    """Create a count mix bar chart."""
    counts = df[column].value_counts(normalize=True).rename("share").reset_index()
    counts.columns = [column, "share"]
    figure = px.bar(counts, x=column, y="share", title=title)
    figure.update_yaxes(tickformat=".0%")
    return figure


def exposure_by_year(df: pd.DataFrame) -> go.Figure:
    """Create exposure by underwriting year chart."""
    annual = df.groupby("underwriting_year", as_index=False)["earned_exposure"].sum()
    return px.bar(
        annual,
        x="underwriting_year",
        y="earned_exposure",
        title="Earned Exposure By Underwriting Year",
    )


def premium_by_year(df: pd.DataFrame) -> go.Figure:
    """Create written and earned premium by underwriting year chart."""
    annual = df.groupby("underwriting_year", as_index=False).agg(
        written_premium=("written_premium", "sum"),
        earned_premium=("earned_premium", "sum"),
    )
    melted = annual.melt(
        id_vars="underwriting_year",
        value_vars=["written_premium", "earned_premium"],
        var_name="premium_type",
        value_name="premium",
    )
    return px.bar(
        melted,
        x="underwriting_year",
        y="premium",
        color="premium_type",
        barmode="group",
        title="Written And Earned Premium By Underwriting Year",
    )
