import math
import pandas as pd
import numpy as np
from scipy.stats import chi2_contingency, fisher_exact, mannwhitneyu
from analysis import find_column


# ---------------------------------------------------------------------
# HELPER: Safe percent
# ---------------------------------------------------------------------
def safe_percent(numerator, denominator):
    if denominator == 0:
        return None
    return numerator / denominator * 100


# ---------------------------------------------------------------------
# HELPER: Significance stars from p-value
# ---------------------------------------------------------------------
def significance_stars(p):
    """
    Return significance stars based on p-value.
    *** p < 0.001  ** p < 0.01  * p < 0.05  ns p >= 0.05
    """
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "N/A"
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "ns"


# ---------------------------------------------------------------------
# HELPER: Plain-English interpretation
# ---------------------------------------------------------------------
def interpret_result(outcome, g1_label, g1_pct, g2_label, g2_pct, p, rr, rr_low, rr_high):
    """
    Generate a one-sentence plain-English interpretation.
    Used in the Interpretation column of the stats table.
    """
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "Could not be tested."

    sig = p < 0.05

    # Format percentages for readability
    p1 = f"{g1_pct:.1f}%" if g1_pct is not None else "N/A"
    p2 = f"{g2_pct:.1f}%" if g2_pct is not None else "N/A"

    if rr is not None and rr_low is not None and rr_high is not None:
        rr_str = f"RR {rr:.2f} (95% CI {rr_low:.2f}–{rr_high:.2f})"
    else:
        rr_str = None

    if sig:
        direction = "more" if (g1_pct or 0) > (g2_pct or 0) else "less"
        base = (
            f"{outcome} was significantly {direction} common in {g1_label} "
            f"({p1}) than {g2_label} ({p2})."
        )
    else:
        base = (
            f"No significant difference in {outcome} between {g1_label} "
            f"({p1}) and {g2_label} ({p2})."
        )

    if rr_str:
        return f"{base} {rr_str}."
    return base


# ---------------------------------------------------------------------
# HELPER: Odds ratio with 95% CI
# ---------------------------------------------------------------------
def odds_ratio_and_ci(a, b, c, d):
    """
    2x2 table:
                  Outcome yes   Outcome no
    Group 1           a            b
    Group 2           c            d

    Uses Haldane-Anscombe correction if any cell is zero.
    """
    if min(a, b, c, d) == 0:
        a += 0.5
        b += 0.5
        c += 0.5
        d += 0.5

    odds_ratio = (a * d) / (b * c)
    se = math.sqrt((1 / a) + (1 / b) + (1 / c) + (1 / d))
    log_or = math.log(odds_ratio)
    ci_low = math.exp(log_or - 1.96 * se)
    ci_high = math.exp(log_or + 1.96 * se)

    return odds_ratio, ci_low, ci_high


# ---------------------------------------------------------------------
# HELPER: Relative risk with 95% CI
# ---------------------------------------------------------------------
def relative_risk_and_ci(a, b, c, d):
    """
    Relative risk = (a / (a+b)) / (c / (c+d))
    95% CI via log method (Greenland & Rothman formula).
    Applies 0.5 correction if any count is zero.
    """
    if min(a, b, c, d) == 0:
        a += 0.5
        b += 0.5
        c += 0.5
        d += 0.5

    r1 = a / (a + b)   # risk in group 1
    r2 = c / (c + d)   # risk in group 2

    if r2 == 0:
        return None, None, None

    rr = r1 / r2
    # SE of log(RR)
    se_log_rr = math.sqrt((1 / a) - (1 / (a + b)) + (1 / c) - (1 / (c + d)))
    log_rr = math.log(rr)
    ci_low = math.exp(log_rr - 1.96 * se_log_rr)
    ci_high = math.exp(log_rr + 1.96 * se_log_rr)

    return rr, ci_low, ci_high


# ---------------------------------------------------------------------
# CORE: Binary outcome test for one yes/no outcome
# ---------------------------------------------------------------------
def binary_outcome_test(
    group1_df,
    group2_df,
    outcome_name,
    group1_label,
    group2_label,
    condition_function
):
    """
    Run a statistical test for a yes/no outcome between two groups.
    Returns a dict with counts, percentages, OR, RR, CI, p-value,
    significance stars, and plain-English interpretation.
    """
    # Count yes/no in each group
    g1_yes = int(condition_function(group1_df).sum())
    g1_total = len(group1_df)
    g1_no = g1_total - g1_yes

    g2_yes = int(condition_function(group2_df).sum())
    g2_total = len(group2_df)
    g2_no = g2_total - g2_yes

    # Calculate percentages
    g1_pct = safe_percent(g1_yes, g1_total)
    g2_pct = safe_percent(g2_yes, g2_total)

    # Can't run test on empty groups
    if g1_total == 0 or g2_total == 0:
        return {
            "Outcome": outcome_name,
            f"{group1_label} n/N": f"{g1_yes}/{g1_total}",
            f"{group1_label} %": None,
            f"{group2_label} n/N": f"{g2_yes}/{g2_total}",
            f"{group2_label} %": None,
            "Test": "Not run",
            "p-value": None,
            "Sig": "N/A",
            "Odds ratio": None,
            "OR 95% CI": None,
            "Relative risk": None,
            "RR 95% CI": None,
            "Effect size": None,
            "Warnings": "One or both groups are empty.",
            "Interpretation": "Not enough data to run test.",
        }

    # Run chi-square; fall back to Fisher exact if expected counts are small
    table = np.array([
        [g1_yes, g1_no],
        [g2_yes, g2_no],
    ])

    try:
        chi2, chi_p, dof, expected = chi2_contingency(table)

        if (expected < 5).any():
            _, p_value = fisher_exact(table)
            test_name = "Fisher exact"
        else:
            p_value = chi_p
            test_name = "Chi-square"

        # Odds ratio
        odds_ratio, or_low, or_high = odds_ratio_and_ci(g1_yes, g1_no, g2_yes, g2_no)

        # Relative risk
        rr, rr_low, rr_high = relative_risk_and_ci(g1_yes, g1_no, g2_yes, g2_no)

    except Exception:
        p_value = None
        test_name = "Error"
        odds_ratio, or_low, or_high = None, None, None
        rr, rr_low, rr_high = None, None, None

    # Significance stars
    sig = significance_stars(p_value)

    # Plain-English interpretation
    interpretation = interpret_result(
        outcome_name,
        group1_label, g1_pct,
        group2_label, g2_pct,
        p_value, rr, rr_low, rr_high
    )

    # ------------------------------------------------------------------
    # Small-sample warnings
    # Checks (in priority order):
    #   1. Either group total < 20
    #   2. Any 2x2 cell count < 5
    #   3. Zero events in either group (before correction)
    # Multiple warnings are joined with a semicolon.
    # ------------------------------------------------------------------
    warning_parts = []

    if g1_total < 20 or g2_total < 20:
        warning_parts.append(f"Small n (n1={g1_total}, n2={g2_total})")

    # Cell counts use the original uncorrected values
    cell_counts = [g1_yes, g1_no, g2_yes, g2_no]
    if any(c < 5 for c in cell_counts):
        warning_parts.append("Cell count <5")

    if g1_yes == 0 or g2_yes == 0:
        warning_parts.append("Zero events in one group; estimates unreliable")

    warnings_str = "; ".join(warning_parts) if warning_parts else ""

    return {
        "Outcome": outcome_name,
        f"{group1_label} n/N": f"{g1_yes}/{g1_total}",
        f"{group1_label} %": round(g1_pct, 2) if g1_pct is not None else None,
        f"{group2_label} n/N": f"{g2_yes}/{g2_total}",
        f"{group2_label} %": round(g2_pct, 2) if g2_pct is not None else None,
        "Test": test_name,
        "p-value": p_value,
        "Sig": sig,
        "Odds ratio": round(odds_ratio, 2) if odds_ratio is not None else None,
        "OR 95% CI": f"{or_low:.2f}–{or_high:.2f}" if or_low is not None else None,
        "Relative risk": round(rr, 2) if rr is not None else None,
        "RR 95% CI": f"{rr_low:.2f}–{rr_high:.2f}" if rr_low is not None else None,
        # Effect size is blank for binary outcomes (Cramér's V not yet implemented)
        "Effect size": None,
        "Warnings": warnings_str,
        "Interpretation": interpretation,
    }


# ---------------------------------------------------------------------
# CORE: Age distribution test (Mann-Whitney U + rank-biserial r)
# ---------------------------------------------------------------------
def age_distribution_test(group1_df, group2_df, group1_label, group2_label):
    """
    Mann-Whitney U test for age distribution with rank-biserial correlation
    as effect size.

    Rank-biserial r = 1 - (2U) / (n1 * n2)
    Range: -1 to +1. Values near 0 = small effect; ±0.3 moderate; ±0.5 large.
    """
    age_col = find_column(["age"])

    if (
        age_col is None
        or age_col not in group1_df.columns
        or age_col not in group2_df.columns
    ):
        return {
            "Outcome": "Age distribution",
            f"{group1_label} n/N": "N/A",
            f"{group1_label} %": None,
            f"{group2_label} n/N": "N/A",
            f"{group2_label} %": None,
            "Test": "Mann-Whitney U",
            "p-value": None,
            "Sig": "N/A",
            "Odds ratio": None,
            "OR 95% CI": None,
            "Relative risk": None,
            "RR 95% CI": None,
            "Effect size": None,
            "Warnings": "Age column not found.",
            "Interpretation": "Age column not found.",
        }

    g1_age = pd.to_numeric(group1_df[age_col], errors="coerce").dropna()
    g2_age = pd.to_numeric(group2_df[age_col], errors="coerce").dropna()

    if len(g1_age) == 0 or len(g2_age) == 0:
        p_value = None
        r_rb = None
    else:
        stat, p_value = mannwhitneyu(g1_age, g2_age, alternative="two-sided")

        # Rank-biserial correlation
        n1, n2 = len(g1_age), len(g2_age)
        r_rb = 1 - (2 * stat) / (n1 * n2)

    sig = significance_stars(p_value)

    # Interpretation for age
    if p_value is not None:
        sig_word = "significantly" if p_value < 0.05 else "not significantly"
        rb_str = f" (rank-biserial r = {r_rb:.3f})" if r_rb is not None else ""
        interpretation = (
            f"Age distributions were {sig_word} different between "
            f"{group1_label} (median {g1_age.median():.1f} yrs) and "
            f"{group2_label} (median {g2_age.median():.1f} yrs){rb_str}."
        )
    else:
        interpretation = "Could not test age distribution."

    # Effect size string for the dedicated column
    effect_size_str = (
        f"rank-biserial r = {r_rb:.3f}" if r_rb is not None else None
    )

    # Small-sample warning for age test
    warning_parts = []
    if len(g1_age) < 20 or len(g2_age) < 20:
        warning_parts.append(f"Small n (n1={len(g1_age)}, n2={len(g2_age)})")
    warnings_str = "; ".join(warning_parts) if warning_parts else ""

    return {
        "Outcome": "Age distribution",
        f"{group1_label} n/N": f"median {g1_age.median():.1f}" if len(g1_age) > 0 else "N/A",
        f"{group1_label} %": None,
        f"{group2_label} n/N": f"median {g2_age.median():.1f}" if len(g2_age) > 0 else "N/A",
        f"{group2_label} %": None,
        "Test": "Mann-Whitney U",
        "p-value": p_value,
        "Sig": sig,
        "Odds ratio": None,
        "OR 95% CI": None,
        # Relative risk is not applicable for age distribution
        "Relative risk": None,
        "RR 95% CI": None,
        # Rank-biserial r lives here, not in Relative risk
        "Effect size": effect_size_str,
        "Warnings": warnings_str,
        "Interpretation": interpretation,
    }


# ---------------------------------------------------------------------
# MAIN: Run all statistical tests
# ---------------------------------------------------------------------
def run_statistical_tests(group1_df, group2_df, group1_label, group2_label):
    """
    Run the full suite of statistical tests for a two-group NEISS comparison.

    Outcomes tested:
    - Fracture (dx 57)
    - Concussion (dx 52)
    - Internal organ injury (dx 62)
    - Laceration (dx 59)
    - Sprain/strain (dx 64 or 74)
    - Hospital admission (disp 4)
    - Transfer (disp 2)
    - Fatality (disp 8)
    - Head/neck injury (body parts 75, 76, 89, 88, 94)
    - Upper extremity injury (body parts 30, 32, 33, 34, 80, 82, 92)
    - Lower extremity injury (body parts 35, 36, 37, 81, 83, 93)
    - Pediatric age <18
    - Male sex
    - Age distribution (Mann-Whitney U + rank-biserial r)
    """
    age_col = find_column(["age"])
    sex_col = find_column(["sex"])
    diagnosis_col = find_column(["diagnosis", "diag"])
    disposition_col = find_column(["disposition", "disp"])
    body_part_col = find_column(["body_part", "bodypart", "body_part_1", "bodypart_1"])

    tests = []

    # ------------------------------------------------------------------
    # DIAGNOSIS-BASED OUTCOMES
    # ------------------------------------------------------------------
    if diagnosis_col:

        tests.append(binary_outcome_test(
            group1_df, group2_df,
            "Fracture",
            group1_label, group2_label,
            lambda df: pd.to_numeric(df[diagnosis_col], errors="coerce") == 57
        ))

        tests.append(binary_outcome_test(
            group1_df, group2_df,
            "Concussion",
            group1_label, group2_label,
            lambda df: pd.to_numeric(df[diagnosis_col], errors="coerce") == 52
        ))

        tests.append(binary_outcome_test(
            group1_df, group2_df,
            "Internal organ injury",
            group1_label, group2_label,
            lambda df: pd.to_numeric(df[diagnosis_col], errors="coerce") == 62
        ))

        tests.append(binary_outcome_test(
            group1_df, group2_df,
            "Laceration",
            group1_label, group2_label,
            lambda df: pd.to_numeric(df[diagnosis_col], errors="coerce") == 59
        ))

        tests.append(binary_outcome_test(
            group1_df, group2_df,
            "Sprain/strain",
            group1_label, group2_label,
            # codes 64 and 74 both map to sprain/strain in NEISS
            lambda df: pd.to_numeric(df[diagnosis_col], errors="coerce").isin([64, 74])
        ))

    # ------------------------------------------------------------------
    # DISPOSITION-BASED OUTCOMES
    # ------------------------------------------------------------------
    if disposition_col:

        tests.append(binary_outcome_test(
            group1_df, group2_df,
            "Hospital admission",
            group1_label, group2_label,
            lambda df: pd.to_numeric(df[disposition_col], errors="coerce") == 4
        ))

        tests.append(binary_outcome_test(
            group1_df, group2_df,
            "Transfer",
            group1_label, group2_label,
            lambda df: pd.to_numeric(df[disposition_col], errors="coerce") == 2
        ))

        tests.append(binary_outcome_test(
            group1_df, group2_df,
            "Fatality",
            group1_label, group2_label,
            lambda df: pd.to_numeric(df[disposition_col], errors="coerce") == 8
        ))

    # ------------------------------------------------------------------
    # BODY PART-BASED OUTCOMES
    # ------------------------------------------------------------------
    if body_part_col:

        # Head or neck: head=75, face=76, neck=89, mouth=88, ear=94
        tests.append(binary_outcome_test(
            group1_df, group2_df,
            "Head/neck injury",
            group1_label, group2_label,
            lambda df: pd.to_numeric(df[body_part_col], errors="coerce").isin(
                [75, 76, 89, 88, 94]
            )
        ))

        # Upper extremity: shoulder=30, elbow=32, lower arm=33, wrist=34,
        #                  upper arm=80, hand=82, finger=92
        tests.append(binary_outcome_test(
            group1_df, group2_df,
            "Upper extremity injury",
            group1_label, group2_label,
            lambda df: pd.to_numeric(df[body_part_col], errors="coerce").isin(
                [30, 32, 33, 34, 80, 82, 92]
            )
        ))

        # Lower extremity: knee=35, lower leg=36, ankle=37, upper leg=81,
        #                  foot=83, toe=93
        tests.append(binary_outcome_test(
            group1_df, group2_df,
            "Lower extremity injury",
            group1_label, group2_label,
            lambda df: pd.to_numeric(df[body_part_col], errors="coerce").isin(
                [35, 36, 37, 81, 83, 93]
            )
        ))

    # ------------------------------------------------------------------
    # DEMOGRAPHIC OUTCOMES
    # ------------------------------------------------------------------
    if age_col:
        tests.append(binary_outcome_test(
            group1_df, group2_df,
            "Pediatric age <18",
            group1_label, group2_label,
            lambda df: pd.to_numeric(df[age_col], errors="coerce") < 18
        ))

    if sex_col:
        tests.append(binary_outcome_test(
            group1_df, group2_df,
            "Male sex",
            group1_label, group2_label,
            lambda df: pd.to_numeric(df[sex_col], errors="coerce") == 1
        ))

    # ------------------------------------------------------------------
    # AGE DISTRIBUTION (Mann-Whitney U + rank-biserial r)
    # ------------------------------------------------------------------
    tests.append(age_distribution_test(
        group1_df, group2_df,
        group1_label, group2_label
    ))

    # ------------------------------------------------------------------
    # BUILD DATAFRAME
    # ------------------------------------------------------------------
    stats_df = pd.DataFrame(tests)

    # Format p-value for display
    if "p-value" in stats_df.columns:
        stats_df["p-value"] = pd.to_numeric(stats_df["p-value"], errors="coerce")
        stats_df["p-value formatted"] = stats_df["p-value"].apply(format_p_value)

    # Round numeric columns
    for col in ["Odds ratio", "Relative risk"]:
        if col in stats_df.columns:
            stats_df[col] = pd.to_numeric(stats_df[col], errors="coerce")

    return stats_df


# ---------------------------------------------------------------------
# HELPER: Format p-value for display
# ---------------------------------------------------------------------
def format_p_value(p):
    if pd.isna(p):
        return "N/A"
    if p < 0.001:
        return "<0.001"
    return f"{p:.3f}"
