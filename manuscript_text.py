"""
manuscript_text.py
------------------
Generates draft manuscript text and study quality checks for the NEISS
Research Studio.

All functions are pure Python/pandas — no database calls, no Streamlit.
They accept only data already computed by the existing pipeline.

Public API
----------
quality_checks(mode, ...)          -> list of check dicts
draft_methods(mode, ...)           -> str
draft_abstract_descriptive(...)    -> str
draft_abstract_comparative(...)    -> str
draft_abstract_trend(...)          -> str

Each returned string begins with a DRAFT DISCLAIMER and ends with a
LIMITATIONS note.  Users should verify all numbers before submission.
"""

import math
import pandas as pd

# ── constants ──────────────────────────────────────────────────────────────
DISCLAIMER = (
    "⚠️  DRAFT ONLY — verify all numbers against source data before submission.\n"
    "Statistics are based on unweighted NEISS sample counts unless otherwise noted.\n"
)

UNWEIGHTED_CAVEAT = (
    "All comparative statistics (chi-square, Fisher exact, odds ratios, relative risks) "
    "were performed on unweighted sample counts and have not been adjusted for the "
    "complex NEISS survey design (Weight, Stratum, PSU). "
    "Results should be interpreted as descriptive and exploratory. "
    "Survey-weighted inference is recommended prior to publication."
)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1  —  QUALITY CHECKS
# ══════════════════════════════════════════════════════════════════════════════

def quality_checks(
    mode,
    *,
    # Common
    year_range=None,
    keyword=None,
    has_weight=True,
    # Descriptive / Trend
    sample_n=None,
    # Comparative
    group1_label=None,
    group2_label=None,
    group1_n=None,
    group2_n=None,
    stats_df=None,         # the raw stats DataFrame from run_statistical_tests
    prop_summary_df=None,  # Wilson CI proportion table (either group)
):
    """
    Return a list of quality-check dicts, each with keys:
        level   : "error" | "warning" | "info"
        message : plain-English description
    Sorted: errors first, then warnings, then info.
    """
    checks = []

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _add(level, msg):
        checks.append({"level": level, "message": msg})

    # ── Universal checks ─────────────────────────────────────────────────────
    if not has_weight:
        _add("warning",
             "Weight variable not found. National estimates are unavailable. "
             "All analyses are based on raw sample counts only.")

    if keyword and keyword.strip():
        _add("warning",
             f"Narrative keyword filter active: '{keyword.strip()}'. "
             "Keyword filtering may misclassify cases (false positives and "
             "false negatives depending on narrative completeness).")

    _add("info", UNWEIGHTED_CAVEAT)

    # ── Single-group / trend checks ──────────────────────────────────────────
    if mode in ("descriptive", "trend") and sample_n is not None:
        if sample_n == 0:
            _add("error",
                 "No cases matched the selected filters. "
                 "Widen the year range, product codes, or other filters.")
        elif sample_n < 20:
            _add("error",
                 f"Very small sample size (n = {sample_n}). "
                 "Results are likely unstable. Widen filters before interpreting.")
        elif sample_n < 100:
            _add("warning",
                 f"Small sample size (n = {sample_n}). "
                 "Proportions and CIs may be wide. Interpret with caution.")

    # ── Comparative checks ───────────────────────────────────────────────────
    if mode == "comparative":
        for label, n in [(group1_label, group1_n), (group2_label, group2_n)]:
            if n is None:
                continue
            if n == 0:
                _add("error",
                     f"Group '{label}' has zero cases. "
                     "Check product codes and filters.")
            elif n < 20:
                _add("error",
                     f"Group '{label}' has very few cases (n = {n}). "
                     "Statistical tests are unreliable.")
            elif n < 100:
                _add("warning",
                     f"Group '{label}' has a small sample (n = {n}). "
                     "Interpret results with caution.")

        # Check stats_df for flagged rows
        if stats_df is not None and not stats_df.empty and "Warnings" in stats_df.columns:
            flagged = stats_df[
                stats_df["Warnings"].notna() & (stats_df["Warnings"] != "")
            ]
            if len(flagged) > 0:
                outcomes = flagged["Outcome"].tolist() if "Outcome" in flagged.columns else []
                _add("warning",
                     f"{len(flagged)} outcome row(s) have small-cell warnings: "
                     f"{', '.join(str(o) for o in outcomes)}. "
                     "OR and RR estimates for these rows may be unstable.")

            # Check for zero events
            zero_rows = stats_df[
                stats_df["Warnings"].str.contains("Zero events", na=False)
            ]
            if len(zero_rows) > 0:
                outcomes = zero_rows["Outcome"].tolist() if "Outcome" in zero_rows.columns else []
                _add("warning",
                     f"Zero events in one group for: "
                     f"{', '.join(str(o) for o in outcomes)}. "
                     "Estimates use a 0.5 continuity correction and are approximate.")

        # Check for wide CIs in proportion summary
        if prop_summary_df is not None and not prop_summary_df.empty:
            wide_ci_rows = _find_wide_ci_rows(prop_summary_df)
            if wide_ci_rows:
                _add("warning",
                     f"Wide 95% CIs (span >30 percentage points) for: "
                     f"{', '.join(wide_ci_rows)}. "
                     "These proportions are imprecise — consider these estimates preliminary.")

    # Sort: errors → warnings → info
    order = {"error": 0, "warning": 1, "info": 2}
    checks.sort(key=lambda c: order.get(c["level"], 3))
    return checks


def _find_wide_ci_rows(prop_df, threshold_pp=30):
    """
    Return a list of Proportion names where the CI span exceeds threshold_pp
    percentage points.  Parses strings like '42.1% (95% CI 39.8–44.4)'.
    """
    wide = []
    if "% (95% CI)" not in prop_df.columns or "Proportion" not in prop_df.columns:
        return wide
    for _, row in prop_df.iterrows():
        val = str(row.get("% (95% CI)", ""))
        try:
            # Extract the two CI numbers from the en-dash range
            ci_part = val.split("95% CI")[-1].strip().rstrip(")")
            parts = ci_part.replace("–", "-").split("-")
            lo = float(parts[0].strip())
            hi = float(parts[1].strip())
            if (hi - lo) > threshold_pp:
                wide.append(str(row.get("Proportion", "?")))
        except Exception:
            pass
    return wide


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2  —  METHODS PARAGRAPHS
# ══════════════════════════════════════════════════════════════════════════════

def draft_methods(
    mode,
    *,
    year_range,
    product_codes,
    group_label=None,        # descriptive / trend
    group1_label=None,       # comparative
    group1_codes=None,
    group2_label=None,
    group2_codes=None,
    age_min=None,
    age_max=None,
    sex_filter_label="All",
    keyword=None,
    has_weight=True,
):
    """
    Return a draft Methods paragraph as a plain-text string.
    """
    lines = [DISCLAIMER, ""]

    # Data source
    lines.append(
        "Data source: This study used data from the National Electronic Injury "
        "Surveillance System (NEISS), operated by the U.S. Consumer Product Safety "
        "Commission (CPSC). NEISS provides nationally representative estimates of "
        "consumer product-related injuries treated in U.S. hospital emergency "
        "departments via a stratified probability sample of approximately 100 EDs."
    )
    lines.append("")

    # Years and cohort definition
    yr = f"{year_range[0]}–{year_range[1]}"
    if mode == "comparative":
        codes1_str = ", ".join(str(c) for c in (group1_codes or []))
        codes2_str = ", ".join(str(c) for c in (group2_codes or []))
        lines.append(
            f"Cases were identified from NEISS records for {yr}. "
            f"{group1_label} injuries were identified using NEISS product code(s) {codes1_str}. "
            f"{group2_label} injuries were identified using NEISS product code(s) {codes2_str}."
        )
    else:
        codes_str = ", ".join(str(c) for c in (product_codes or []))
        lbl = group_label or "the cohort"
        lines.append(
            f"Cases were identified from NEISS records for {yr} "
            f"using product code(s) {codes_str} to define {lbl}."
        )
    lines.append("")

    # Filters applied
    filter_parts = []
    if age_min is not None or age_max is not None:
        age_lo = age_min if age_min is not None else 0
        age_hi = age_max if age_max is not None else 120
        filter_parts.append(f"age {age_lo}–{age_hi} years")
    if sex_filter_label != "All":
        filter_parts.append(f"sex = {sex_filter_label}")
    if keyword and keyword.strip():
        filter_parts.append(
            f"narrative keyword containing '{keyword.strip()}' "
            "(case-insensitive; may introduce misclassification)"
        )
    if filter_parts:
        lines.append("Additional filters applied: " + "; ".join(filter_parts) + ".")
        lines.append("")

    # Weighting
    if has_weight:
        lines.append(
            "National estimates were calculated by summing individual NEISS case weights "
            "provided by CPSC. Sample case counts represent the number of NEISS records "
            "matching the selected filters."
        )
    else:
        lines.append(
            "The NEISS weight variable was not available in the loaded data. "
            "National estimates could not be computed; all reported counts are unweighted sample values."
        )
    lines.append("")

    # Statistics
    if mode == "comparative":
        lines.append(
            "Binary outcomes were compared between groups using chi-square testing, "
            "or Fisher exact testing when any expected cell count was less than 5. "
            "Odds ratios (OR) and relative risks (RR) with 95% confidence intervals "
            "were calculated using the log method. "
            "A Haldane-Anscombe continuity correction of 0.5 was applied when any "
            "cell count was zero. "
            "Age distributions were compared using the Mann-Whitney U test (two-sided); "
            "effect size was quantified using rank-biserial correlation. "
            "All comparative tests were performed on unweighted sample counts and have "
            "not been adjusted for the NEISS complex survey design. "
            "Survey-weighted inference is recommended before publication."
        )
    else:
        lines.append(
            "Descriptive statistics include counts, proportions, mean and median age, "
            "and sex distribution."
        )
    lines.append("")

    # Wilson CIs
    lines.append(
        "Wilson score 95% confidence intervals were computed for all reported proportions "
        "(% Male, % Female, % Pediatric, % Adult, hospital admission rate, fracture rate, "
        "concussion rate, anatomic region rates, and age group percentages). "
        "The Wilson interval was chosen for its performance near proportions of 0 and 1 "
        "and with moderate sample sizes."
    )

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3  —  ABSTRACT: DESCRIPTIVE COHORT
# ══════════════════════════════════════════════════════════════════════════════

def draft_abstract_descriptive(
    *,
    group_label,
    product_codes,
    year_range,
    summary_dict,       # from analysis.summarize_group
    annual_df,          # year | sample_cases | weighted_estimate
    top_dx_df,          # Diagnosis | Count | Percent
    top_body_df,        # Body Part | Count | Percent
    disposition_df,     # Disposition | Count | Percent
    age_groups_df=None, # from proportions.age_group_table
    prop_summary_df=None,
    keyword=None,
):
    """
    Return a draft structured abstract for a Descriptive Cohort Study.
    """
    parts = [DISCLAIMER, ""]

    # ── Background ──────────────────────────────────────────────────────────
    codes_str = ", ".join(str(c) for c in product_codes)
    yr = f"{year_range[0]}–{year_range[1]}"
    parts.append("BACKGROUND")
    parts.append(
        f"Injuries associated with {group_label} represent an important source of "
        f"emergency department (ED) presentations in the United States. "
        f"This study describes the epidemiology of {group_label}-related ED visits "
        f"using nationally representative surveillance data."
    )
    parts.append("")

    # ── Methods ─────────────────────────────────────────────────────────────
    parts.append("METHODS")
    kw_note = (
        f" Cases were further filtered using the narrative keyword '{keyword.strip()}'."
        if keyword and keyword.strip() else ""
    )
    parts.append(
        f"We analyzed NEISS data from {yr} for injuries associated with "
        f"product code(s) {codes_str} ({group_label}).{kw_note} "
        f"Descriptive statistics were computed. "
        f"National estimates were calculated using NEISS case weights when available. "
        f"Wilson score 95% confidence intervals (CIs) were computed for proportions."
    )
    parts.append("")

    # ── Results ─────────────────────────────────────────────────────────────
    parts.append("RESULTS")
    result_sentences = []

    n = summary_dict.get("Sample cases", 0)
    weighted = summary_dict.get("Weighted estimate")
    mean_age = summary_dict.get("Mean age")
    median_age = summary_dict.get("Median age")
    pct_male = summary_dict.get("% Male")
    pct_ped = summary_dict.get("% Pediatric")

    # Sample size
    if weighted and weighted > 0:
        result_sentences.append(
            f"A total of {n:,} NEISS sample cases were identified, representing an "
            f"estimated {_fmt_n(weighted)} ED visits nationally over {yr}."
        )
    else:
        result_sentences.append(
            f"A total of {n:,} NEISS sample cases were identified from {yr}."
        )

    # Demographics
    if mean_age is not None and median_age is not None:
        result_sentences.append(
            f"The mean age was {mean_age:.1f} years (median {median_age:.1f} years)."
        )
    if pct_male is not None:
        result_sentences.append(
            f"Males accounted for {pct_male:.1f}% of cases."
        )
    if pct_ped is not None:
        result_sentences.append(
            f"Pediatric patients (age <18 years) represented {pct_ped:.1f}% of the cohort."
        )

    # Age group breakdown
    if age_groups_df is not None and not age_groups_df.empty:
        ped_row = age_groups_df[age_groups_df["Age Group"].str.startswith("Pediatric")]
        ya_row  = age_groups_df[age_groups_df["Age Group"].str.startswith("Young adult")]
        if not ped_row.empty and not ya_row.empty:
            result_sentences.append(
                f"By age group, pediatric patients (<18 years) represented "
                f"{ped_row.iloc[0]['% (95% CI)']} and young adults (18–34 years) "
                f"represented {ya_row.iloc[0]['% (95% CI)']} of cases."
            )

    # Top diagnosis
    if top_dx_df is not None and not top_dx_df.empty:
        top_dx = top_dx_df.iloc[0]
        dx_name = str(top_dx.get("Diagnosis", ""))
        dx_pct  = top_dx.get("Percent", None)
        if dx_pct is not None:
            result_sentences.append(
                f"The most common diagnosis was {dx_name} ({dx_pct:.1f}% of cases)."
            )

    # Top body part
    if top_body_df is not None and not top_body_df.empty:
        top_bp = top_body_df.iloc[0]
        bp_name = str(top_bp.get("Body Part", ""))
        bp_pct  = top_bp.get("Percent", None)
        if bp_pct is not None:
            result_sentences.append(
                f"The most frequently injured body region was {bp_name} ({bp_pct:.1f}% of cases)."
            )

    # Hospital admission from prop_summary or disposition
    hosp_pct = _get_prop_row(prop_summary_df, "Hospital admission")
    if hosp_pct:
        result_sentences.append(
            f"Hospital admission occurred in {hosp_pct} of cases."
        )
    elif disposition_df is not None and not disposition_df.empty:
        admitted = disposition_df[
            disposition_df["Disposition"].str.contains("admitted|4 -", case=False, na=False)
        ]
        if not admitted.empty:
            pct = admitted.iloc[0].get("Percent", None)
            if pct is not None:
                result_sentences.append(
                    f"Approximately {pct:.1f}% of patients were admitted."
                )

    # Annual trend
    trend_sent = _trend_sentence(annual_df, group_label)
    if trend_sent:
        result_sentences.append(trend_sent)

    parts.append(" ".join(result_sentences) if result_sentences else "See tables for results.")
    parts.append("")

    # ── Conclusion ──────────────────────────────────────────────────────────
    parts.append("CONCLUSION")
    parts.append(
        f"{group_label}-related ED visits represent a substantial injury burden. "
        f"These findings characterize the epidemiology of {group_label.lower()} injuries "
        f"and may inform injury prevention and clinical resource planning. "
        f"Further analysis using survey-weighted methods is recommended to obtain "
        f"design-adjusted national estimates."
    )
    parts.append("")
    parts.append("LIMITATIONS")
    parts.append(_standard_limitations(keyword))

    return "\n".join(parts)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4  —  ABSTRACT: COMPARATIVE COHORT
# ══════════════════════════════════════════════════════════════════════════════

def draft_abstract_comparative(
    *,
    group1_label,
    group1_codes,
    group2_label,
    group2_codes,
    year_range,
    summary_df,          # two-row DataFrame from run_two_group_comparison
    stats_df,            # raw stats DataFrame (with p-value column)
    group1_top_dx,
    group2_top_dx,
    group1_top_body=None,
    group2_top_body=None,
    comparative_age_groups=None,
    group1_prop_summary=None,
    group2_prop_summary=None,
    keyword=None,
):
    """
    Return a draft structured abstract for a Comparative Cohort Study.
    """
    parts = [DISCLAIMER, ""]
    yr = f"{year_range[0]}–{year_range[1]}"

    # ── Background ──────────────────────────────────────────────────────────
    parts.append("BACKGROUND")
    parts.append(
        f"Both {group1_label} and {group2_label} injuries are common causes of "
        f"emergency department (ED) presentations in the United States. "
        f"Whether injury patterns, severity, and demographic characteristics differ "
        f"between these activities has important implications for injury prevention "
        f"and clinical management."
    )
    parts.append("")

    # ── Methods ─────────────────────────────────────────────────────────────
    parts.append("METHODS")
    c1 = ", ".join(str(c) for c in group1_codes)
    c2 = ", ".join(str(c) for c in group2_codes)
    kw_note = (
        f" Cases were further filtered using the narrative keyword '{keyword.strip()}'."
        if keyword and keyword.strip() else ""
    )
    parts.append(
        f"We analyzed NEISS data from {yr}. "
        f"{group1_label} injuries were identified using product code(s) {c1}; "
        f"{group2_label} injuries using product code(s) {c2}.{kw_note} "
        f"Binary outcomes were compared using chi-square or Fisher exact testing. "
        f"Odds ratios (OR) and relative risks (RR) with 95% CIs were calculated. "
        f"All tests were performed on unweighted sample counts. "
        f"Wilson score 95% CIs were computed for proportions."
    )
    parts.append("")

    # ── Results ─────────────────────────────────────────────────────────────
    parts.append("RESULTS")
    result_sentences = []

    # Sample sizes
    n1, n2, w1, w2 = _extract_summary_ns(summary_df, group1_label, group2_label)
    if n1 is not None and n2 is not None:
        size_sent = f"We identified {n1:,} {group1_label} and {n2:,} {group2_label} cases"
        if w1 and w2:
            size_sent += (
                f", representing an estimated {_fmt_n(w1)} and {_fmt_n(w2)} "
                f"national ED visits respectively"
            )
        result_sentences.append(size_sent + ".")

    # Age comparison from stats_df
    age_row = _get_stats_row(stats_df, "Age distribution")
    if age_row is not None:
        g1_median = _extract_median_from_nn(age_row.get(f"{group1_label} n/N", ""))
        g2_median = _extract_median_from_nn(age_row.get(f"{group2_label} n/N", ""))
        p_age = age_row.get("p-value", None)
        if g1_median and g2_median:
            sig_word = "significantly" if (p_age is not None and _is_sig(p_age)) else "not significantly"
            result_sentences.append(
                f"{group1_label} patients had a median age of {g1_median} years compared with "
                f"{g2_median} years for {group2_label} (Mann-Whitney U, {sig_word} different)."
            )

    # Sex comparison
    sex_row = _get_stats_row(stats_df, "Male sex")
    if sex_row is not None:
        g1_pct = sex_row.get(f"{group1_label} %")
        g2_pct = sex_row.get(f"{group2_label} %")
        p_sex  = sex_row.get("p-value")
        if g1_pct is not None and g2_pct is not None:
            sig_note = _sig_note(p_sex)
            result_sentences.append(
                f"Males represented {_fmt_pct(g1_pct)} of {group1_label} and "
                f"{_fmt_pct(g2_pct)} of {group2_label} cases{sig_note}."
            )

    # Top diagnoses
    if group1_top_dx is not None and not group1_top_dx.empty:
        dx1 = group1_top_dx.iloc[0]
        result_sentences.append(
            f"The most common diagnosis in {group1_label} was "
            f"{dx1.get('Diagnosis', '')} ({dx1.get('Percent', 0):.1f}%)."
        )
    if group2_top_dx is not None and not group2_top_dx.empty:
        dx2 = group2_top_dx.iloc[0]
        result_sentences.append(
            f"In {group2_label}, {dx2.get('Diagnosis', '')} was most common "
            f"({dx2.get('Percent', 0):.1f}%)."
        )

    # Significant outcomes from stats_df
    sig_sentences = _significant_outcome_sentences(
        stats_df, group1_label, group2_label, max_outcomes=4
    )
    result_sentences.extend(sig_sentences)

    parts.append(" ".join(result_sentences) if result_sentences else "See tables for results.")
    parts.append("")

    # ── Conclusion ──────────────────────────────────────────────────────────
    parts.append("CONCLUSION")
    parts.append(
        f"This study identified differences in injury patterns between "
        f"{group1_label} and {group2_label}-related ED visits. "
        f"These findings were based on unweighted NEISS sample counts and "
        f"should be confirmed using survey-weighted methods prior to publication. "
        f"Results may inform targeted injury prevention strategies for each activity."
    )
    parts.append("")
    parts.append("LIMITATIONS")
    parts.append(_standard_limitations(keyword))

    return "\n".join(parts)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5  —  ABSTRACT: ANNUAL TREND
# ══════════════════════════════════════════════════════════════════════════════

def draft_abstract_trend(
    *,
    group_label,
    product_codes,
    year_range,
    trend_df,          # year | sample_cases | weighted_estimate
    top_dx_df,
    top_body_df=None,
    disposition_df=None,
    prop_summary_df=None,
    keyword=None,
):
    """
    Return a draft structured abstract for an Annual Trend Study.
    """
    parts = [DISCLAIMER, ""]
    yr = f"{year_range[0]}–{year_range[1]}"
    codes_str = ", ".join(str(c) for c in product_codes)

    # ── Background ──────────────────────────────────────────────────────────
    parts.append("BACKGROUND")
    parts.append(
        f"Surveillance of temporal trends in {group_label}-related emergency department "
        f"(ED) visits is important for understanding the evolving injury burden and "
        f"evaluating the impact of policy or design changes over time."
    )
    parts.append("")

    # ── Methods ─────────────────────────────────────────────────────────────
    parts.append("METHODS")
    kw_note = (
        f" Cases were further filtered using the narrative keyword '{keyword.strip()}'."
        if keyword and keyword.strip() else ""
    )
    parts.append(
        f"We analyzed NEISS data from {yr} for injuries associated with "
        f"product code(s) {codes_str} ({group_label}).{kw_note} "
        f"Annual sample case counts and national estimates (when the weight variable "
        f"was available) were tabulated by year."
    )
    parts.append("")

    # ── Results ─────────────────────────────────────────────────────────────
    parts.append("RESULTS")
    result_sentences = []

    total_n = int(trend_df["sample_cases"].sum()) if not trend_df.empty else 0
    has_wt = (
        "weighted_estimate" in trend_df.columns
        and trend_df["weighted_estimate"].notna().any()
    )

    if has_wt:
        total_wt = pd.to_numeric(trend_df["weighted_estimate"], errors="coerce").sum()
        result_sentences.append(
            f"A total of {total_n:,} NEISS sample cases were identified from {yr}, "
            f"representing an estimated {_fmt_n(total_wt)} ED visits nationally."
        )
    else:
        result_sentences.append(
            f"A total of {total_n:,} NEISS sample cases were identified from {yr}."
        )

    # First-year vs last-year trend
    trend_sent = _trend_sentence(trend_df, group_label)
    if trend_sent:
        result_sentences.append(trend_sent)

    # Percent change
    pct_change = _compute_pct_change(trend_df)
    if pct_change is not None:
        direction = "increased" if pct_change > 0 else "decreased"
        result_sentences.append(
            f"Over the study period, annual sample case volume {direction} "
            f"by {abs(pct_change):.1f}% from the first to the last year."
        )

    # Top diagnosis
    if top_dx_df is not None and not top_dx_df.empty:
        top_dx = top_dx_df.iloc[0]
        dx_pct = top_dx.get("Percent")
        if dx_pct is not None:
            result_sentences.append(
                f"Across the study period, the most common diagnosis was "
                f"{top_dx.get('Diagnosis', '')} ({dx_pct:.1f}% of cases)."
            )

    # Top body part
    if top_body_df is not None and not top_body_df.empty:
        top_bp = top_body_df.iloc[0]
        bp_pct = top_bp.get("Percent")
        if bp_pct is not None:
            result_sentences.append(
                f"The most frequently injured body region was "
                f"{top_bp.get('Body Part', '')} ({bp_pct:.1f}% of cases)."
            )

    parts.append(" ".join(result_sentences) if result_sentences else "See tables for results.")
    parts.append("")

    # ── Conclusion ──────────────────────────────────────────────────────────
    parts.append("CONCLUSION")
    parts.append(
        f"This analysis documents temporal trends in {group_label}-related ED visits "
        f"using NEISS surveillance data. "
        f"Findings may reflect changes in participation rates, product adoption, "
        f"or clinical practice patterns. "
        f"Survey-weighted trend analyses are recommended for publication-ready estimates."
    )
    parts.append("")
    parts.append("LIMITATIONS")
    parts.append(_standard_limitations(keyword))

    return "\n".join(parts)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6  —  CASE SEARCH COHORT SUMMARY (short, not a full abstract)
# ══════════════════════════════════════════════════════════════════════════════

def draft_case_search_summary(
    *,
    product_codes,
    year_range,
    case_count,
    weighted_estimate,
    keyword=None,
):
    """
    Return a short cohort summary string for Case Search mode.
    Not a full abstract.
    """
    yr = f"{year_range[0]}–{year_range[1]}"
    codes_str = ", ".join(str(c) for c in product_codes) if product_codes else "all"
    lines = [
        f"Query: NEISS product code(s) {codes_str}, years {yr}.",
    ]
    if keyword and keyword.strip():
        lines.append(f"Narrative keyword filter: '{keyword.strip()}'.")
    lines.append(f"Matching NEISS sample cases: {case_count:,}.")
    if weighted_estimate and weighted_estimate > 0:
        lines.append(
            f"Estimated national ED visits: {_fmt_n(weighted_estimate)} "
            f"(based on NEISS case weights)."
        )
    else:
        lines.append("National estimate: not available (weight variable not found).")
    lines.append("")
    lines.append(
        "Note: These counts are raw query results. For a full descriptive or "
        "comparative analysis, use Descriptive Cohort Study or "
        "Comparative Cohort Study mode."
    )
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _fmt_n(n):
    """Format a large number: e.g. 1234567 → '~1.2 million'."""
    if n is None:
        return "N/A"
    n = float(n)
    if n >= 1_000_000:
        return f"~{n/1_000_000:.1f} million"
    if n >= 1_000:
        return f"~{round(n/1000)*1000:,}"
    return f"~{int(round(n)):,}"


def _fmt_pct(val):
    """Format a proportion value as percent string."""
    try:
        return f"{float(val):.1f}%"
    except Exception:
        return str(val)


def _is_sig(p_val):
    """Return True if p_val < 0.05 (numeric or string '<0.001')."""
    try:
        if isinstance(p_val, str):
            if p_val.startswith("<"):
                return True
            return float(p_val) < 0.05
        return float(p_val) < 0.05
    except Exception:
        return False


def _sig_note(p_val):
    """Return a short parenthetical significance note."""
    if p_val is None:
        return ""
    try:
        sig = _is_sig(p_val)
        return " (p<0.05)" if sig else " (p≥0.05, not significant)"
    except Exception:
        return ""


def _get_stats_row(stats_df, outcome_name):
    """Return the first row matching outcome_name as a dict, or None."""
    if stats_df is None or stats_df.empty or "Outcome" not in stats_df.columns:
        return None
    rows = stats_df[stats_df["Outcome"] == outcome_name]
    if rows.empty:
        return None
    return rows.iloc[0].to_dict()


def _extract_median_from_nn(nn_str):
    """Parse 'median 32.5' from the n/N column of the Age distribution row."""
    try:
        if "median" in str(nn_str).lower():
            return str(nn_str).lower().replace("median", "").strip()
    except Exception:
        pass
    return None


def _extract_summary_ns(summary_df, label1, label2):
    """
    Extract (n1, n2, weighted1, weighted2) from a two-row summary DataFrame.
    Returns (None, None, None, None) on failure.
    """
    try:
        row1 = summary_df[summary_df["Group"] == label1].iloc[0]
        row2 = summary_df[summary_df["Group"] == label2].iloc[0]
        n1 = int(row1.get("Sample cases", 0))
        n2 = int(row2.get("Sample cases", 0))
        w1 = row1.get("Weighted estimate")
        w2 = row2.get("Weighted estimate")
        # coerce to float or None
        w1 = float(w1) if w1 is not None and not (isinstance(w1, float) and math.isnan(w1)) else None
        w2 = float(w2) if w2 is not None and not (isinstance(w2, float) and math.isnan(w2)) else None
        return n1, n2, w1, w2
    except Exception:
        return None, None, None, None


def _get_prop_row(prop_df, prop_name):
    """Return the '% (95% CI)' string for a named proportion, or None."""
    if prop_df is None or prop_df.empty:
        return None
    if "Proportion" not in prop_df.columns or "% (95% CI)" not in prop_df.columns:
        return None
    rows = prop_df[prop_df["Proportion"] == prop_name]
    if rows.empty:
        return None
    return str(rows.iloc[0]["% (95% CI)"])


def _trend_sentence(trend_df, label):
    """
    Build a one-sentence description of the first vs last year.
    Returns empty string if trend_df is empty or has <2 years.
    """
    if trend_df is None or trend_df.empty:
        return ""
    df = trend_df.copy()
    df = df.sort_values("year") if "year" in df.columns else df
    if len(df) < 2:
        return ""
    first = df.iloc[0]
    last  = df.iloc[-1]
    fy = int(first.get("year", "?"))
    ly = int(last.get("year", "?"))

    # Prefer weighted if available
    use_wt = (
        "weighted_estimate" in df.columns
        and pd.to_numeric(df["weighted_estimate"], errors="coerce").notna().any()
    )
    if use_wt:
        v_first = pd.to_numeric(first.get("weighted_estimate"), errors="coerce")
        v_last  = pd.to_numeric(last.get("weighted_estimate"),  errors="coerce")
        metric  = "estimated national visits"
    else:
        v_first = pd.to_numeric(first.get("sample_cases"), errors="coerce")
        v_last  = pd.to_numeric(last.get("sample_cases"),  errors="coerce")
        metric  = "sample cases"

    if pd.isna(v_first) or pd.isna(v_last):
        return ""

    direction = "from" if v_last >= v_first else "falling from"
    change    = "increased" if v_last > v_first else ("decreased" if v_last < v_first else "remained stable")
    return (
        f"Annual {label} {metric} {change}, "
        f"{direction} {_fmt_n(v_first)} in {fy} to {_fmt_n(v_last)} in {ly}."
    )


def _compute_pct_change(trend_df):
    """
    Return percent change from first to last year in sample_cases.
    Returns None if not calculable.
    """
    if trend_df is None or trend_df.empty or "sample_cases" not in trend_df.columns:
        return None
    df = trend_df.sort_values("year") if "year" in trend_df.columns else trend_df
    if len(df) < 2:
        return None
    v_first = pd.to_numeric(df.iloc[0]["sample_cases"], errors="coerce")
    v_last  = pd.to_numeric(df.iloc[-1]["sample_cases"], errors="coerce")
    if pd.isna(v_first) or pd.isna(v_last) or v_first == 0:
        return None
    return (v_last - v_first) / v_first * 100


def _significant_outcome_sentences(stats_df, g1_label, g2_label, max_outcomes=4):
    """
    Return a list of sentences describing the most significant binary outcomes.
    Skips the Age distribution row.
    Limited to max_outcomes to keep abstracts concise.
    """
    if stats_df is None or stats_df.empty:
        return []
    if "Outcome" not in stats_df.columns or "p-value" not in stats_df.columns:
        return []

    df = stats_df.copy()
    df = df[df["Outcome"] != "Age distribution"]
    df["_p_num"] = pd.to_numeric(df["p-value"], errors="coerce")
    sig = df[df["_p_num"] < 0.05].sort_values("_p_num")

    sentences = []
    for _, row in sig.head(max_outcomes).iterrows():
        outcome = row.get("Outcome", "")
        g1_pct  = row.get(f"{g1_label} %")
        g2_pct  = row.get(f"{g2_label} %")
        rr      = row.get("Relative risk")
        rr_ci   = row.get("RR 95% CI")
        p_str   = row.get("p-value formatted", "")
        warn    = str(row.get("Warnings", ""))

        # Skip rows with instability warnings in the abstract
        if "Zero events" in warn or "Cell count <5" in warn:
            sentences.append(
                f"{outcome} was rarely observed in one group; "
                f"estimates are unreliable and are excluded from the abstract summary."
            )
            continue

        pct_part = ""
        if g1_pct is not None and g2_pct is not None:
            pct_part = (
                f"{_fmt_pct(g1_pct)} in {g1_label} vs "
                f"{_fmt_pct(g2_pct)} in {g2_label}"
            )

        rr_part = ""
        if rr is not None and not (isinstance(rr, float) and math.isnan(rr)):
            rr_ci_str = f" (95% CI {rr_ci})" if rr_ci else ""
            rr_part = f" (RR {rr:.2f}{rr_ci_str})"

        p_part = f" (p = {p_str})" if p_str and p_str != "N/A" else ""

        if pct_part:
            sentences.append(
                f"{outcome} was significantly more common in "
                f"{g1_label if float(g1_pct or 0) > float(g2_pct or 0) else g2_label} "
                f"({pct_part}{rr_part}{p_part})."
            )
        else:
            sentences.append(
                f"A significant difference was found for {outcome}{p_part}."
            )

    return sentences


def _standard_limitations(keyword=None):
    """Return a standard NEISS limitations paragraph."""
    lines = [
        "NEISS captures only injuries presenting to participating emergency departments "
        "and does not include injuries treated in outpatient, urgent care, or primary "
        "care settings, or injuries not seeking medical care.",

        "Product codes identify associated consumer products but do not establish "
        "causation or confirm mechanism of injury.",

        "All comparative statistics were performed on unweighted sample counts. "
        "Survey-weighted inferential statistics incorporating the NEISS Weight, "
        "Stratum, and PSU variables were not applied. "
        "Survey-weighted methods are recommended prior to publication.",
    ]
    if keyword and keyword.strip():
        lines.append(
            f"Narrative keyword filtering ('{keyword.strip()}') may introduce "
            "case misclassification due to variation in narrative completeness."
        )
    lines.append(
        "National estimates carry confidence intervals that were not reported here. "
        "Estimates should be interpreted as approximate."
    )
    return " ".join(lines)
