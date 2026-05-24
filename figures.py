"""
figures.py
----------
Publication-ready matplotlib figure generators for NEISS Research Studio.

All functions:
- Accept pandas DataFrames already built by the analysis pipeline.
- Return an in-memory BytesIO PNG buffer, or None when data is empty.
- Never raise an exception on missing/empty data — return None instead.
- Use matplotlib Agg backend so they work on servers without a display.

Usage in app.py:
    from figures import fig_trend_line, fig_horizontal_bar, ...
    buf = fig_trend_line(trend_df, ...)
    if buf:
        st.download_button("Download PNG", data=buf, file_name="trend.png", mime="image/png")
"""

import io
import matplotlib
matplotlib.use("Agg")   # must be set before importing pyplot
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import numpy as np


# ── shared style constants ────────────────────────────────────────────────────
_FIGURE_DPI   = 150        # resolution for downloads
_FIGURE_W     = 8          # inches wide
_FIGURE_H     = 5          # inches tall
_BAR_COLOR    = "#2C6FAC"  # single-group bar color (muted blue)
_COLORS_MULTI = [           # two-group palette
    "#2C6FAC",  # muted blue
    "#E07B39",  # muted orange
]
_FONT_TITLE   = 13
_FONT_AXIS    = 10
_FONT_TICK    = 8


def _save_fig(fig):
    """Save a matplotlib figure to an in-memory BytesIO PNG and close it."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=_FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _empty_note(title):
    """Return a simple 'No data' placeholder figure."""
    fig, ax = plt.subplots(figsize=(_FIGURE_W, _FIGURE_H))
    ax.text(
        0.5, 0.5, "No data available",
        ha="center", va="center",
        fontsize=_FONT_TITLE, color="gray",
        transform=ax.transAxes,
    )
    ax.set_title(title, fontsize=_FONT_TITLE)
    ax.axis("off")
    return _save_fig(fig)


# ══════════════════════════════════════════════════════════════════════════════
# 1. Annual trend line
# ══════════════════════════════════════════════════════════════════════════════

def fig_trend_line(trend_df, y_col, title, ylabel, color=_BAR_COLOR, label=None):
    """
    Line chart of an annual metric over years.

    Parameters
    ----------
    trend_df : pd.DataFrame with columns 'year' and y_col.
    y_col    : str  Column to plot on the y-axis.
    title    : str  Chart title.
    ylabel   : str  Y-axis label.
    color    : str  Line colour.
    label    : str or None  Legend label; omitted if None.

    Returns
    -------
    BytesIO PNG buffer or None if data is empty.
    """
    try:
        if trend_df is None or trend_df.empty:
            return _empty_note(title)

        if "year" not in trend_df.columns or y_col not in trend_df.columns:
            return _empty_note(title)

        df = trend_df[["year", y_col]].copy()
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
        df[y_col]  = pd.to_numeric(df[y_col],  errors="coerce")
        df = df.dropna().sort_values("year")

        if df.empty:
            return _empty_note(title)

        fig, ax = plt.subplots(figsize=(_FIGURE_W, _FIGURE_H))

        ax.plot(
            df["year"], df[y_col],
            color=color, linewidth=2, marker="o", markersize=5,
            label=label,
        )

        ax.set_title(title, fontsize=_FONT_TITLE, fontweight="bold", pad=10)
        ax.set_xlabel("Year", fontsize=_FONT_AXIS)
        ax.set_ylabel(ylabel, fontsize=_FONT_AXIS)
        ax.tick_params(axis="both", labelsize=_FONT_TICK)

        # Integer x-axis ticks for years
        ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(
            lambda x, _: f"{x:,.0f}"
        ))

        if label:
            ax.legend(fontsize=_FONT_TICK)

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", linestyle="--", alpha=0.4)

        fig.tight_layout()
        return _save_fig(fig)

    except Exception:
        return None


def fig_two_trend_lines(trend_df1, trend_df2, y_col, title, ylabel,
                        label1="Group 1", label2="Group 2"):
    """
    Overlay two annual trend lines on the same axes.
    Useful for side-by-side group comparison of annual counts.
    Returns BytesIO PNG or None.
    """
    try:
        if (trend_df1 is None or trend_df1.empty) and (trend_df2 is None or trend_df2.empty):
            return _empty_note(title)

        fig, ax = plt.subplots(figsize=(_FIGURE_W, _FIGURE_H))

        for df, label, color in [
            (trend_df1, label1, _COLORS_MULTI[0]),
            (trend_df2, label2, _COLORS_MULTI[1]),
        ]:
            if df is None or df.empty:
                continue
            if "year" not in df.columns or y_col not in df.columns:
                continue
            d = df[["year", y_col]].copy()
            d["year"] = pd.to_numeric(d["year"], errors="coerce")
            d[y_col]  = pd.to_numeric(d[y_col],  errors="coerce")
            d = d.dropna().sort_values("year")
            if not d.empty:
                ax.plot(d["year"], d[y_col], color=color, linewidth=2,
                        marker="o", markersize=5, label=label)

        ax.set_title(title, fontsize=_FONT_TITLE, fontweight="bold", pad=10)
        ax.set_xlabel("Year", fontsize=_FONT_AXIS)
        ax.set_ylabel(ylabel, fontsize=_FONT_AXIS)
        ax.tick_params(axis="both", labelsize=_FONT_TICK)
        ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
        ax.legend(fontsize=_FONT_TICK)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", linestyle="--", alpha=0.4)

        fig.tight_layout()
        return _save_fig(fig)

    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 2. Horizontal bar chart  (diagnoses / body parts / disposition)
# ══════════════════════════════════════════════════════════════════════════════

def fig_horizontal_bar(df, label_col, value_col, title,
                       xlabel="Count", color=_BAR_COLOR, top_n=10):
    """
    Horizontal bar chart for categorical counts (diagnoses, body parts, etc.).

    Parameters
    ----------
    df        : pd.DataFrame
    label_col : str  Column with category labels (e.g. "Diagnosis").
    value_col : str  Column with counts.
    title     : str  Chart title.
    xlabel    : str  X-axis label.
    top_n     : int  Max bars to show.

    Returns
    -------
    BytesIO PNG or None.
    """
    try:
        if df is None or df.empty:
            return _empty_note(title)
        if label_col not in df.columns or value_col not in df.columns:
            return _empty_note(title)

        data = df[[label_col, value_col]].copy()
        data[value_col] = pd.to_numeric(data[value_col], errors="coerce")
        data = data.dropna().head(top_n)

        if data.empty:
            return _empty_note(title)

        # Reverse so longest bar is at top
        data = data.iloc[::-1].reset_index(drop=True)

        # Truncate long labels for readability
        data[label_col] = data[label_col].astype(str).apply(
            lambda s: s[:45] + "…" if len(s) > 45 else s
        )

        fig_h = max(3, len(data) * 0.45 + 1)
        fig, ax = plt.subplots(figsize=(_FIGURE_W, fig_h))

        bars = ax.barh(
            data[label_col], data[value_col],
            color=color, edgecolor="white", linewidth=0.5,
        )

        # Value labels on bars
        for bar in bars:
            w = bar.get_width()
            ax.text(
                w + max(data[value_col]) * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f"{int(w):,}",
                va="center", ha="left", fontsize=_FONT_TICK,
            )

        ax.set_title(title, fontsize=_FONT_TITLE, fontweight="bold", pad=10)
        ax.set_xlabel(xlabel, fontsize=_FONT_AXIS)
        ax.tick_params(axis="both", labelsize=_FONT_TICK)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_xlim(0, max(data[value_col]) * 1.15)

        fig.tight_layout()
        return _save_fig(fig)

    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 3. Grouped bar chart  (two-group comparison of a numeric summary metric)
# ══════════════════════════════════════════════════════════════════════════════

def fig_grouped_bar(summary_df, metric_col, title, ylabel=None,
                    group_col="Group"):
    """
    Side-by-side bar chart comparing a metric between two groups.

    Parameters
    ----------
    summary_df : pd.DataFrame — two-row summary table with a Group column.
    metric_col : str  Column name of the metric to compare.
    title      : str  Chart title.
    ylabel     : str or None  Y-axis label; defaults to metric_col.
    group_col  : str  Column containing group labels.

    Returns
    -------
    BytesIO PNG or None.
    """
    try:
        if summary_df is None or summary_df.empty:
            return _empty_note(title)
        if group_col not in summary_df.columns or metric_col not in summary_df.columns:
            return _empty_note(title)

        data = summary_df[[group_col, metric_col]].copy()
        data[metric_col] = pd.to_numeric(data[metric_col], errors="coerce")
        data = data.dropna()

        if data.empty:
            return _empty_note(title)

        fig, ax = plt.subplots(figsize=(6, 4))

        bars = ax.bar(
            data[group_col], data[metric_col],
            color=_COLORS_MULTI[:len(data)],
            edgecolor="white", linewidth=0.5,
            width=0.5,
        )

        for bar in bars:
            h = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h * 1.01,
                f"{h:,.1f}",
                ha="center", va="bottom", fontsize=_FONT_TICK,
            )

        ax.set_title(title, fontsize=_FONT_TITLE, fontweight="bold", pad=10)
        ax.set_ylabel(ylabel or metric_col, fontsize=_FONT_AXIS)
        ax.tick_params(axis="both", labelsize=_FONT_TICK)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.1f}"))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_ylim(0, max(data[metric_col]) * 1.15)

        fig.tight_layout()
        return _save_fig(fig)

    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 4. Age group bar chart  (single group)
# ══════════════════════════════════════════════════════════════════════════════

def fig_age_groups(age_df, title, color=_BAR_COLOR):
    """
    Bar chart of age group counts from a proportions.age_group_table() result.

    Parameters
    ----------
    age_df : pd.DataFrame with columns 'Age Group' and 'n'.
    title  : str  Chart title.

    Returns
    -------
    BytesIO PNG or None.
    """
    try:
        if age_df is None or age_df.empty:
            return _empty_note(title)
        if "Age Group" not in age_df.columns or "n" not in age_df.columns:
            return _empty_note(title)

        # Exclude the Total row for the bar chart
        data = age_df[age_df["Age Group"] != "Total"].copy()
        data["n"] = pd.to_numeric(data["n"], errors="coerce")
        data = data.dropna()

        if data.empty:
            return _empty_note(title)

        fig, ax = plt.subplots(figsize=(_FIGURE_W, 4))

        bars = ax.bar(
            data["Age Group"], data["n"],
            color=color, edgecolor="white", linewidth=0.5,
        )

        for bar in bars:
            h = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h * 1.01,
                f"{int(h):,}",
                ha="center", va="bottom", fontsize=_FONT_TICK,
            )

        ax.set_title(title, fontsize=_FONT_TITLE, fontweight="bold", pad=10)
        ax.set_xlabel("Age Group", fontsize=_FONT_AXIS)
        ax.set_ylabel("Sample Cases (n)", fontsize=_FONT_AXIS)
        ax.tick_params(axis="x", labelsize=_FONT_TICK, rotation=15)
        ax.tick_params(axis="y", labelsize=_FONT_TICK)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", linestyle="--", alpha=0.4)

        fig.tight_layout()
        return _save_fig(fig)

    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 5. Side-by-side grouped age group chart  (comparative)
# ══════════════════════════════════════════════════════════════════════════════

def fig_age_groups_comparison(age_df1, label1, age_df2, label2, title):
    """
    Grouped bar chart comparing age group distributions between two cohorts.

    Parameters
    ----------
    age_df1/2 : pd.DataFrame from proportions.age_group_table() (each has Age Group, n).
    label1/2  : str  Group names.
    title     : str  Chart title.

    Returns
    -------
    BytesIO PNG or None.
    """
    try:
        if (age_df1 is None or age_df1.empty) and (age_df2 is None or age_df2.empty):
            return _empty_note(title)

        # Standard age group order (excluding Total)
        age_order = [
            "Pediatric (<18)",
            "Young adult (18–34)",
            "Middle adult (35–64)",
            "Older adult (65+)",
        ]

        def _get_counts(df):
            if df is None or df.empty:
                return [0] * len(age_order)
            d = df[df["Age Group"] != "Total"].copy()
            d["n"] = pd.to_numeric(d["n"], errors="coerce").fillna(0)
            counts = []
            for grp in age_order:
                row = d[d["Age Group"] == grp]
                counts.append(int(row["n"].values[0]) if not row.empty else 0)
            return counts

        counts1 = _get_counts(age_df1)
        counts2 = _get_counts(age_df2)

        x = np.arange(len(age_order))
        bar_w = 0.35

        fig, ax = plt.subplots(figsize=(_FIGURE_W + 1, 5))

        b1 = ax.bar(x - bar_w / 2, counts1, bar_w,
                    label=label1, color=_COLORS_MULTI[0], edgecolor="white")
        b2 = ax.bar(x + bar_w / 2, counts2, bar_w,
                    label=label2, color=_COLORS_MULTI[1], edgecolor="white")

        for bar in list(b1) + list(b2):
            h = bar.get_height()
            if h > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    h * 1.01,
                    f"{int(h):,}",
                    ha="center", va="bottom", fontsize=_FONT_TICK,
                )

        ax.set_title(title, fontsize=_FONT_TITLE, fontweight="bold", pad=10)
        ax.set_xticks(x)
        ax.set_xticklabels(age_order, fontsize=_FONT_TICK, rotation=15, ha="right")
        ax.set_ylabel("Sample Cases (n)", fontsize=_FONT_AXIS)
        ax.legend(fontsize=_FONT_TICK)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", linestyle="--", alpha=0.4)

        fig.tight_layout()
        return _save_fig(fig)

    except Exception:
        return None
