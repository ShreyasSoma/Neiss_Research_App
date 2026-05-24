"""
proportions.py
--------------
Helper functions for Wilson confidence intervals, age group breakdowns,
and key-proportion summary tables.

All functions are pure pandas / scipy — no database calls, no Streamlit.
They accept a DataFrame that has already been fetched by the calling module.

Wilson interval formula reference:
    Wilson (1927) "Probable inference, the law of succession, and statistical
    inference". Journal of the American Statistical Association.
"""

import math
import pandas as pd
import numpy as np
from scipy.stats import chi2_contingency, norm


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — Wilson confidence interval primitives
# ─────────────────────────────────────────────────────────────────────────────

def wilson_ci(k, n, confidence=0.95):
    """
    Compute Wilson score 95% CI for a proportion k/n.

    Parameters
    ----------
    k : int   Number of successes (events).
    n : int   Total observations.
    confidence : float  Confidence level (default 0.95).

    Returns
    -------
    (low, high) as floats in [0, 1], or (None, None) if n == 0.

    The Wilson interval is preferred over the normal-approximation (Wald)
    interval for proportions near 0 or 1 and for small samples.
    """
    if n == 0:
        return None, None

    z = norm.ppf(1 - (1 - confidence) / 2)   # 1.96 for 95%
    p_hat = k / n
    denom = 1 + z**2 / n
    centre = (p_hat + z**2 / (2 * n)) / denom
    spread = (z * math.sqrt(p_hat * (1 - p_hat) / n + z**2 / (4 * n**2))) / denom

    low  = max(0.0, centre - spread)
    high = min(1.0, centre + spread)
    return low, high


def format_proportion(k, n):
    """
    Return a display string like  "42.1% (95% CI 39.8–44.4)"
    or "N/A" if n == 0.

    k and n must be integers (or castable to int).
    """
    k = int(k)
    n = int(n)

    if n == 0:
        return "N/A"

    pct  = k / n * 100
    low, high = wilson_ci(k, n)

    # Convert CI bounds to percentage
    low_pct  = low  * 100
    high_pct = high * 100

    return f"{pct:.1f}% (95% CI {low_pct:.1f}–{high_pct:.1f})"


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — Age group breakdown table
# ─────────────────────────────────────────────────────────────────────────────

# Four standard age groups used throughout the app.
# Defined once here so they're easy to update in the future.
AGE_GROUPS = [
    ("Pediatric (<18)",    lambda s: s < 18),
    ("Young adult (18–34)", lambda s: (s >= 18) & (s <= 34)),
    ("Middle adult (35–64)", lambda s: (s >= 35) & (s <= 64)),
    ("Older adult (65+)",  lambda s: s >= 65),
]


def age_group_table(df, label, age_col=None, weight_col=None):
    """
    Build an age group breakdown table for one cohort DataFrame.

    Parameters
    ----------
    df         : pd.DataFrame  The filtered cohort.
    label      : str           Cohort name, used in the 'Cohort' column.
    age_col    : str or None   Name of the age column; auto-detected if None.
    weight_col : str or None   Name of the weight column for national estimates;
                               omitted if None.

    Returns
    -------
    pd.DataFrame with columns:
        Age Group | n | % (95% CI) | Weighted estimate (optional)

    Returns an empty-safe DataFrame (all zeros/N/A) when df is empty or
    when the age column cannot be found.
    """
    # ---- resolve column names ----
    if age_col is None:
        age_col = _find_col_in_df(df, ["age"])

    # Build numeric age series; coerce non-numeric to NaN
    if age_col and age_col in df.columns:
        age_series = pd.to_numeric(df[age_col], errors="coerce")
    else:
        age_series = pd.Series(dtype=float)

    n_total = len(df)
    has_weight = weight_col and weight_col in df.columns

    rows = []
    for group_name, condition in AGE_GROUPS:
        if len(age_series) > 0:
            mask = condition(age_series)
            n_group = int(mask.sum())
        else:
            n_group = 0

        pct_ci_str = format_proportion(n_group, n_total)

        row = {
            "Age Group":   group_name,
            "n":           n_group,
            "% (95% CI)":  pct_ci_str,
        }

        if has_weight:
            # sum weights for cases in this age group
            if len(age_series) > 0:
                w_sum = pd.to_numeric(
                    df.loc[mask, weight_col], errors="coerce"
                ).sum()
                row["Weighted estimate"] = round(w_sum) if not pd.isna(w_sum) else None
            else:
                row["Weighted estimate"] = None

        rows.append(row)

    # Add a totals row
    total_pct_ci = format_proportion(n_total, n_total) if n_total > 0 else "N/A"
    total_row = {
        "Age Group":  "Total",
        "n":          n_total,
        "% (95% CI)": total_pct_ci,
    }
    if has_weight:
        total_row["Weighted estimate"] = (
            round(pd.to_numeric(df[weight_col], errors="coerce").sum())
            if n_total > 0 else None
        )
    rows.append(total_row)

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — Key proportion summary table (with Wilson CIs)
# ─────────────────────────────────────────────────────────────────────────────

def proportion_summary_table(df, label,
                              age_col=None, sex_col=None,
                              diagnosis_col=None, disposition_col=None,
                              body_part_col=None):
    """
    Compute Wilson 95% CIs for key NEISS proportions and return a
    display-ready DataFrame.

    Proportions included (only those whose required column exists):
        % Male                (sex == 1)
        % Female              (sex == 2)
        % Pediatric           (age < 18)
        % Adult               (age >= 18)
        Hospital admission    (disposition == 4)
        Fracture              (diagnosis == 57)
        Concussion            (diagnosis == 52)
        Head/neck injury      (body_part in {75,76,89,88,94})
        Upper extremity injury(body_part in {30,32,33,34,80,82,92})
        Lower extremity injury(body_part in {35,36,37,81,83,93})

    Parameters
    ----------
    df            : pd.DataFrame
    label         : str   Cohort label shown in the table header.
    *_col args    : str or None  Column names; auto-detected from df if None.

    Returns
    -------
    pd.DataFrame with columns:
        Proportion | n | N | % (95% CI)
    """
    # Resolve columns
    if age_col       is None: age_col       = _find_col_in_df(df, ["age"])
    if sex_col       is None: sex_col       = _find_col_in_df(df, ["sex"])
    if diagnosis_col is None: diagnosis_col = _find_col_in_df(df, ["diagnosis", "diag"])
    if disposition_col is None:
        disposition_col = _find_col_in_df(df, ["disposition", "disp"])
    if body_part_col is None:
        body_part_col = _find_col_in_df(
            df, ["body_part", "bodypart", "body_part_1", "bodypart_1"]
        )

    n_total = len(df)
    rows = []

    # Helper: add one row given a boolean mask Series
    def _add(prop_name, mask_series):
        k = int(mask_series.sum())
        rows.append({
            "Proportion":  prop_name,
            "n":           k,
            "N":           n_total,
            "% (95% CI)":  format_proportion(k, n_total),
        })

    # Sex proportions
    if sex_col and sex_col in df.columns:
        sex_num = pd.to_numeric(df[sex_col], errors="coerce")
        _add("% Male",   sex_num == 1)
        _add("% Female", sex_num == 2)

    # Age proportions
    if age_col and age_col in df.columns:
        age_num = pd.to_numeric(df[age_col], errors="coerce")
        _add("% Pediatric (<18)", age_num < 18)
        _add("% Adult (≥18)",     age_num >= 18)

    # Disposition proportions
    if disposition_col and disposition_col in df.columns:
        disp_num = pd.to_numeric(df[disposition_col], errors="coerce")
        _add("Hospital admission", disp_num == 4)

    # Diagnosis proportions
    if diagnosis_col and diagnosis_col in df.columns:
        dx_num = pd.to_numeric(df[diagnosis_col], errors="coerce")
        _add("Fracture",            dx_num == 57)
        _add("Concussion",          dx_num == 52)

    # Body part proportions
    if body_part_col and body_part_col in df.columns:
        bp_num = pd.to_numeric(df[body_part_col], errors="coerce")
        _add("Head/neck injury",       bp_num.isin([75, 76, 89, 88, 94]))
        _add("Upper extremity injury", bp_num.isin([30, 32, 33, 34, 80, 82, 92]))
        _add("Lower extremity injury", bp_num.isin([35, 36, 37, 81, 83, 93]))

    if not rows:
        return pd.DataFrame(columns=["Proportion", "n", "N", "% (95% CI)"])

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — Comparative age group table (two groups side by side)
# ─────────────────────────────────────────────────────────────────────────────

def comparative_age_group_table(df1, label1, df2, label2,
                                 age_col1=None, age_col2=None):
    """
    Build a side-by-side age group comparison table for two cohorts.

    Adds a chi-square p-value across all four age groups (2x4 table) and
    flags small expected cell counts.

    Returns
    -------
    pd.DataFrame with columns:
        Age Group | {label1} n (% 95CI) | {label2} n (% 95CI) | p-value | Warning

    One overall chi-square is run across all four age group cells.
    Individual p-values per row are not included because the test is
    across the full 2×4 table — running four separate 2×2 tests would
    inflate the type-I error rate.
    """
    # Resolve age columns
    if age_col1 is None: age_col1 = _find_col_in_df(df1, ["age"])
    if age_col2 is None: age_col2 = _find_col_in_df(df2, ["age"])

    n1 = len(df1)
    n2 = len(df2)

    if age_col1 and age_col1 in df1.columns:
        age1 = pd.to_numeric(df1[age_col1], errors="coerce")
    else:
        age1 = pd.Series(dtype=float)

    if age_col2 and age_col2 in df2.columns:
        age2 = pd.to_numeric(df2[age_col2], errors="coerce")
    else:
        age2 = pd.Series(dtype=float)

    # Count each age group in each cohort
    counts1 = []
    counts2 = []

    for _, condition in AGE_GROUPS:
        c1 = int(condition(age1).sum()) if len(age1) > 0 else 0
        c2 = int(condition(age2).sum()) if len(age2) > 0 else 0
        counts1.append(c1)
        counts2.append(c2)

    # Overall chi-square across the 2×4 contingency table
    p_value_str = "N/A"
    warning_str = ""

    if n1 > 0 and n2 > 0 and any(c > 0 for c in counts1 + counts2):
        contingency = np.array([counts1, counts2])
        try:
            _, p_val, _, expected = chi2_contingency(contingency)
            p_value_str = _format_p(p_val)

            if (expected < 5).any():
                warning_str = "Expected cell count <5 in at least one cell"
        except Exception:
            p_value_str = "Error"

    # Build display rows
    rows = []
    for i, (group_name, _) in enumerate(AGE_GROUPS):
        c1 = counts1[i]
        c2 = counts2[i]

        rows.append({
            "Age Group":          group_name,
            f"{label1} n (% 95CI)": f"{c1}  {format_proportion(c1, n1)}",
            f"{label2} n (% 95CI)": f"{c2}  {format_proportion(c2, n2)}",
            # Overall p-value shown only on the first row; blank on the rest
            # to avoid repeating it four times
            "Chi-sq p-value": p_value_str if i == 0 else "",
            "Warning":        warning_str if i == 0 else "",
        })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _find_col_in_df(df, candidates):
    """
    Case-insensitive search for a column name in df.
    Returns the actual column name (preserving original case) or None.
    """
    lower_map = {c.lower(): c for c in df.columns}
    for name in candidates:
        if name.lower() in lower_map:
            return lower_map[name.lower()]
    return None


def _format_p(p):
    """Format a p-value float for display."""
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "N/A"
    if p < 0.001:
        return "<0.001"
    return f"{p:.3f}"
