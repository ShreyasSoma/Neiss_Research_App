import streamlit as st
import pandas as pd

from database import build_database, get_connection, get_year_range, get_columns
from analysis import (
    run_basic_query,
    parse_product_codes,
    run_two_group_comparison,
)
from stats import run_statistical_tests
from reports import generate_word_report
from excel_export import generate_excel_workbook
from trend_analysis import run_trend_analysis
from single_group import run_single_group_study
from proportions import age_group_table, proportion_summary_table
from figures import (
    fig_trend_line,
    fig_horizontal_bar,
    fig_grouped_bar,
    fig_age_groups,
    fig_age_groups_comparison,
)
from manuscript_text import (
    quality_checks,
    draft_methods,
    draft_abstract_descriptive,
    draft_abstract_comparative,
    draft_abstract_trend,
    draft_case_search_summary,
)


st.set_page_config(
    page_title="NEISS Research Studio v2",
    page_icon="📊",
    layout="wide"
)

st.title("NEISS Research Studio v2")
st.caption("DuckDB + Streamlit prototype")


# ---------------------------------------------------------------------
# HELPER FUNCTIONS FOR CHARTS
# ---------------------------------------------------------------------
def make_group_metric_chart(summary_df, metric_column):
    if metric_column not in summary_df.columns:
        return None

    chart_df = summary_df[["Group", metric_column]].copy()
    chart_df[metric_column] = pd.to_numeric(chart_df[metric_column], errors="coerce")
    chart_df = chart_df.dropna()

    if chart_df.empty:
        return None

    return chart_df.set_index("Group")


def make_category_chart(category_df, category_column, value_column="Count"):
    if category_df.empty:
        return None

    if category_column not in category_df.columns or value_column not in category_df.columns:
        return None

    chart_df = category_df[[category_column, value_column]].copy()
    chart_df[category_column] = chart_df[category_column].astype(str)
    chart_df[value_column] = pd.to_numeric(chart_df[value_column], errors="coerce")
    chart_df = chart_df.dropna()

    if chart_df.empty:
        return None

    return chart_df.set_index(category_column)


def show_bar_chart(title, chart_df):
    st.markdown(f"#### {title}")

    if chart_df is None or chart_df.empty:
        st.info("No chart data available.")
    else:
        st.bar_chart(chart_df)


def clean_stats_for_display(stats_df, group1_label, group2_label):
    stats_display_df = stats_df.copy()

    # Drop the raw p-value float; keep the formatted string version
    if "p-value" in stats_display_df.columns:
        stats_display_df = stats_display_df.drop(columns=["p-value"])

    preferred_order = [
        "Outcome",
        f"{group1_label} n/N",
        f"{group1_label} %",
        f"{group2_label} n/N",
        f"{group2_label} %",
        "Test",
        "p-value formatted",
        "Sig",
        "Odds ratio",
        "OR 95% CI",
        "Relative risk",
        "RR 95% CI",
        "Effect size",
        "Warnings",
        "Interpretation",
    ]

    existing_order = [col for col in preferred_order if col in stats_display_df.columns]
    stats_display_df = stats_display_df[existing_order]

    return stats_display_df


def dict_to_display_df(summary_dict):
    """
    Converts a one-row summary dictionary into a cleaner vertical table.
    """
    return pd.DataFrame(
        [{"Metric": key, "Value": value} for key, value in summary_dict.items()]
    )


def safe_label(s):
    """
    Convert a label string to a safe filename component.
    Replaces spaces, slashes, and other risky characters with underscores.
    Example: "E-bike Injuries" -> "E-bike_Injuries"
    """
    import re
    s = s.strip()
    s = re.sub(r"[\s/\\]+", "_", s)   # spaces and slashes -> underscore
    s = re.sub(r"[^\w\-]", "", s)     # remove anything that isn't word, dash
    return s or "cohort"


# ---------------------------------------------------------------------
# MANUSCRIPT DRAFT HELPERS
# Render quality checks and manuscript text sections inside a tab/expander.
# Kept here so app.py modes stay clean.
# ---------------------------------------------------------------------

def render_quality_checks(checks):
    """
    Display quality check results using Streamlit callouts.
    checks is a list of {"level": ..., "message": ...} dicts from quality_checks().
    """
    if not checks:
        st.success("No quality issues detected.")
        return

    for check in checks:
        level = check.get("level", "info")
        msg   = check.get("message", "")
        if level == "error":
            st.error(f"🔴 {msg}")
        elif level == "warning":
            st.warning(f"🟡 {msg}")
        else:
            st.info(f"🔵 {msg}")


def render_manuscript_section(abstract_text, methods_text, checks,
                               abstract_filename, methods_filename,
                               checklist_filename):
    """
    Render the full Manuscript Draft section:
      - Study Quality Check
      - Draft Abstract
      - Draft Methods Paragraph
      - Download buttons for each
    """
    st.markdown("### Study Quality Check")
    render_quality_checks(checks)

    st.markdown("---")
    st.markdown("### Draft Abstract")
    st.caption(
        "Auto-generated from study results. "
        "Verify all numbers before use. "
        "Adjust language for your target journal."
    )
    st.text_area(
        "Abstract (editable)",
        value=abstract_text,
        height=400,
        key=f"abstract_{abstract_filename}",
    )
    st.download_button(
        "⬇️ Download abstract (.txt)",
        data=abstract_text.encode("utf-8"),
        file_name=abstract_filename,
        mime="text/plain",
    )

    st.markdown("---")
    st.markdown("### Draft Methods Paragraph")
    st.caption(
        "Copy into your manuscript Methods section. "
        "Adapt product code descriptions and statistical language for your journal."
    )
    st.text_area(
        "Methods (editable)",
        value=methods_text,
        height=300,
        key=f"methods_{methods_filename}",
    )
    st.download_button(
        "⬇️ Download methods (.txt)",
        data=methods_text.encode("utf-8"),
        file_name=methods_filename,
        mime="text/plain",
    )

    st.markdown("---")
    st.markdown("### Download Study Quality Checklist")
    # Build checklist as CSV text
    import io
    buf = io.StringIO()
    buf.write("Level,Message\n")
    for c in checks:
        lvl = c.get("level", "")
        msg = c.get("message", "").replace('"', "'")
        buf.write(f'"{lvl}","{msg}"\n')
    checklist_csv = buf.getvalue()
    st.download_button(
        "⬇️ Download quality checklist (.csv)",
        data=checklist_csv.encode("utf-8"),
        file_name=checklist_filename,
        mime="text/csv",
    )


# ---------------------------------------------------------------------
# DATABASE SETUP
# ---------------------------------------------------------------------
st.sidebar.header("Database")

if st.sidebar.button("Build / Refresh Database"):
    with st.spinner("Loading CSV files into DuckDB..."):
        build_database()
    st.sidebar.success("Database built successfully.")

try:
    con = get_connection()
    year_min_available, year_max_available = get_year_range()
    columns = get_columns()

    st.sidebar.success("Database connected")

except Exception as e:
    st.error("Database could not be loaded.")
    st.info("Make sure your NEISS CSV files are inside the data/ folder.")
    st.exception(e)
    st.stop()


# ---------------------------------------------------------------------
# STUDY SETUP
# ---------------------------------------------------------------------
st.sidebar.header("Study Setup")

study_mode = st.sidebar.radio(
    "Study mode",
    [
        "Case Search",
        "Descriptive Cohort Study",
        "Comparative Cohort Study",
        "Annual Trend Study",
    ]
)

study_title = st.sidebar.text_input(
    "Study title",
    value="Skiing vs Snowboarding Injury Comparison"
)

research_question = st.sidebar.text_area(
    "Research question",
    value="How do injury patterns differ between skiing and snowboarding injuries?"
)

year_range = st.sidebar.slider(
    "Year range",
    min_value=int(year_min_available),
    max_value=int(year_max_available),
    value=(int(year_min_available), int(year_max_available)),
    step=1
)


# ---------------------------------------------------------------------
# OPTIONAL FILTERS
# ---------------------------------------------------------------------
st.sidebar.subheader("Optional Filters")

use_age_filter = st.sidebar.checkbox("Filter by age")

if use_age_filter:
    age_min_filter = st.sidebar.number_input(
        "Minimum age",
        min_value=0,
        max_value=120,
        value=0,
        step=1
    )

    age_max_filter = st.sidebar.number_input(
        "Maximum age",
        min_value=0,
        max_value=120,
        value=120,
        step=1
    )

    if age_min_filter > age_max_filter:
        st.sidebar.error("Minimum age cannot be greater than maximum age.")
        st.stop()
else:
    age_min_filter = None
    age_max_filter = None


sex_filter_label = st.sidebar.selectbox(
    "Sex filter",
    ["All", "Male", "Female"]
)

if sex_filter_label == "Male":
    sex_filter = 1
elif sex_filter_label == "Female":
    sex_filter = 2
else:
    sex_filter = None


keyword_filter = st.sidebar.text_input(
    "Narrative keyword filter",
    placeholder="Example: fall, collision, helmet"
)


# ---------------------------------------------------------------------
# PRODUCT CODE QUICK REFERENCE
# ---------------------------------------------------------------------
with st.sidebar.expander("📋 Common product codes"):
    st.markdown("""
| Code | Sport / Activity |
|------|-----------------|
| 3283 | Alpine skiing |
| 5031 | Snowboarding |
| 5040 | Bicycle |
| 5045 | E-bike |
| 1233 | Trampoline |
| 1243 | Playground equipment |
| 1211 | Basketball |
| 1205 | Football |
| 1274 | Soccer |
| 3286 | ATV |
| 5036 | Dirt bike |
| 1842 | Stairs / steps |
| 1843 | Ladders |
""")


with st.sidebar.expander("ℹ️ About / Limitations"):
    st.markdown("""
**NEISS Research Studio v2**

This tool is for research support only.
All outputs should be reviewed before submission.

**Key limitations:**
- Weighted national estimates use the NEISS weight
  variable when available. If the weight column is
  missing, only raw sample counts are shown.
- Comparative statistics (OR, RR, chi-square) are
  currently **unweighted**. Survey-weighted inference
  using Weight, Stratum, and PSU is recommended
  before publication.
- Narrative keyword filters should be manually
  validated — they may include false positives or
  miss relevant cases depending on narrative quality.
- NEISS captures only ED-treated injuries. Injuries
  seen in outpatient, urgent care, or primary care
  settings are not included.
""")


with st.expander("Available columns"):
    st.write(columns)


# ---------------------------------------------------------------------
# BASIC QUERY MODE
# ---------------------------------------------------------------------
if study_mode == "Case Search":
    st.markdown("## Case Search")

    product_code_text = st.sidebar.text_area(
        "Product codes",
        placeholder="Example: 3283, 5031",
        help="Enter one or more NEISS product codes separated by commas."
    )

    run_button = st.sidebar.button("Run Query", type="primary")

    if not run_button:
        st.info("Choose filters in the sidebar, then click **Run Query**.")
        st.stop()

    try:
        product_codes = parse_product_codes(product_code_text)

        with st.spinner("Running query..."):
            results = run_basic_query(
                year_min=year_range[0],
                year_max=year_range[1],
                product_codes=product_codes,
                age_min=age_min_filter,
                age_max=age_max_filter,
                sex=sex_filter,
                keyword=keyword_filter
            )

        col1, col2 = st.columns(2)

        with col1:
            st.metric("Sample cases", f"{results['case_count']:,}")

        with col2:
            if results["weighted_estimate"] is not None:
                st.metric(
                    "Weighted national estimate",
                    f"{round(results['weighted_estimate']):,}"
                )
            else:
                st.metric("Weighted national estimate", "Not found")

        st.markdown("### First 100 Matching Rows")
        st.dataframe(results["sample_df"], use_container_width=True)

        # ---- Cohort summary (not a full abstract) ----
        with st.expander("📝 Cohort Summary"):
            has_wt = results["weighted_estimate"] is not None
            cs_text = draft_case_search_summary(
                product_codes=product_codes,
                year_range=year_range,
                case_count=results["case_count"],
                weighted_estimate=results["weighted_estimate"],
                keyword=keyword_filter,
            )
            st.text(cs_text)
            st.download_button(
                "⬇️ Download cohort summary (.txt)",
                data=cs_text.encode("utf-8"),
                file_name="case_search_summary.txt",
                mime="text/plain",
            )

        csv_data = results["full_df"].to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Download matching cases as CSV",
            data=csv_data,
            file_name="neiss_matching_cases.csv",
            mime="text/csv"
        )

    except Exception as e:
        st.error("Something went wrong while running the query.")
        st.exception(e)


# ---------------------------------------------------------------------
# SINGLE GROUP STUDY MODE
# ---------------------------------------------------------------------
elif study_mode == "Descriptive Cohort Study":
    st.markdown("## Descriptive Cohort Study")

    st.sidebar.subheader("Single Group Cohort")

    single_label = st.sidebar.text_input(
        "Cohort name",
        value="E-bike Injuries"
    )

    single_codes_text = st.sidebar.text_area(
        "Product codes",
        value="5045",
        help="Example: 5045 for e-bikes, 3283 for skiing, 5031 for snowboarding"
    )

    run_single = st.sidebar.button("Run Single Group Study", type="primary")

    if not run_single:
        st.info("Enter a cohort in the sidebar, then click **Run Single Group Study**.")
        st.stop()

    try:
        single_codes = parse_product_codes(single_codes_text)

        if not single_codes:
            st.error("Single group study needs at least one product code.")
            st.stop()

        with st.spinner("Running single group study..."):
            single_results = run_single_group_study(
                year_min=year_range[0],
                year_max=year_range[1],
                group_label=single_label,
                product_codes=single_codes,
                age_min=age_min_filter,
                age_max=age_max_filter,
                sex=sex_filter,
                keyword=keyword_filter
            )

        summary_dict = single_results["summary"]
        summary_df = dict_to_display_df(summary_dict)
        annual_df = single_results["annual_df"]
        full_df = single_results["full_df"]

        # Build filename components once — used for all downloads and figures
        _s  = safe_label(single_label)
        _yr = f"{year_range[0]}_{year_range[1]}"

        st.markdown(f"### {single_label}")

        c1, c2, c3 = st.columns(3)

        with c1:
            st.metric("Sample cases", f"{summary_dict.get('Sample cases', 0):,}")

        with c2:
            weighted_estimate = summary_dict.get("Weighted estimate")
            if weighted_estimate is not None:
                st.metric("Weighted national estimate", f"{round(weighted_estimate):,}")
            else:
                st.metric("Weighted national estimate", "Not found")

        with c3:
            mean_age = summary_dict.get("Mean age")
            if mean_age is not None:
                st.metric("Mean age", f"{mean_age:.1f}")
            else:
                st.metric("Mean age", "Not found")

        st.markdown("### Summary Table")
        st.dataframe(summary_df, use_container_width=True)

        st.markdown("---")

        st.markdown("## Annual Trends")

        st.markdown("### Annual Trend Table")
        st.dataframe(annual_df, use_container_width=True)

        chart1, chart2 = st.columns(2)

        with chart1:
            st.markdown("### Annual Sample Cases")
            if not annual_df.empty:
                sample_chart = annual_df[["year", "sample_cases"]].copy()
                sample_chart = sample_chart.set_index("year")
                st.line_chart(sample_chart)
            else:
                st.info("No annual sample case data available.")

        with chart2:
            st.markdown("### Annual Weighted Estimates")
            if (
                not annual_df.empty
                and "weighted_estimate" in annual_df.columns
                and annual_df["weighted_estimate"].notna().any()
            ):
                weighted_chart = annual_df[["year", "weighted_estimate"]].copy()
                weighted_chart = weighted_chart.set_index("year")
                st.line_chart(weighted_chart)
            else:
                st.info("Weighted estimate column not available.")

        st.markdown("---")

        st.markdown("## Cohort Tables")

        t1, t2, t3 = st.columns(3)

        with t1:
            st.markdown("### Top Diagnoses")
            st.dataframe(single_results["top_dx"], use_container_width=True)

        with t2:
            st.markdown("### Top Body Parts")
            st.dataframe(single_results["top_body"], use_container_width=True)

        with t3:
            st.markdown("### Disposition")
            st.dataframe(single_results["disposition"], use_container_width=True)

        st.markdown("---")

        # ---- NEW: Proportion CI table ----
        st.markdown("## Key Proportions with 95% Wilson CIs")
        prop_df = single_results.get("prop_summary")
        if prop_df is not None and not prop_df.empty:
            st.dataframe(prop_df, use_container_width=True)
            st.caption(
                "Proportions are of the filtered sample. "
                "95% confidence intervals use the Wilson score method."
            )
        else:
            st.info("Proportion table not available (required columns may be missing).")

        st.markdown("---")

        # ---- NEW: Age group breakdown ----
        st.markdown("## Age Group Breakdown")
        age_df = single_results.get("age_groups")
        if age_df is not None and not age_df.empty:
            st.dataframe(age_df, use_container_width=True)
            st.caption(
                "Age groups: Pediatric <18, Young adult 18–34, "
                "Middle adult 35–64, Older adult 65+. "
                "95% CIs use the Wilson score method."
            )
        else:
            st.info("Age group table not available (age column may be missing).")

        st.markdown("---")

        st.markdown("## Charts")

        chart_tabs = st.tabs([
            "Diagnoses",
            "Body Parts",
            "Disposition"
        ])

        with chart_tabs[0]:
            show_bar_chart(
                "Top Diagnoses",
                make_category_chart(single_results["top_dx"], "Diagnosis")
            )

        with chart_tabs[1]:
            show_bar_chart(
                "Top Body Parts",
                make_category_chart(single_results["top_body"], "Body Part")
            )

        with chart_tabs[2]:
            show_bar_chart(
                "Disposition",
                make_category_chart(single_results["disposition"], "Disposition")
            )

        # ---- PNG Figure Downloads ----
        st.markdown("---")
        st.markdown("## 📥 Download Figures (PNG)")
        st.caption("Publication-ready PNG files at 150 dpi.")

        fig_cols = st.columns(3)

        with fig_cols[0]:
            _buf = fig_trend_line(
                annual_df, "sample_cases",
                f"{single_label}: Annual Sample Cases", "Sample Cases (n)"
            )
            if _buf:
                st.download_button(
                    "⬇️ Annual sample cases",
                    data=_buf,
                    file_name=f"{_s}_{_yr}_Annual_Sample_Cases.png",
                    mime="image/png",
                )

        with fig_cols[1]:
            _buf2 = fig_trend_line(
                annual_df, "weighted_estimate",
                f"{single_label}: Annual Weighted Estimates",
                "National Estimate",
                color="#5B8DB8",
            ) if (
                not annual_df.empty
                and "weighted_estimate" in annual_df.columns
                and annual_df["weighted_estimate"].notna().any()
            ) else None
            if _buf2:
                st.download_button(
                    "⬇️ Annual weighted estimates",
                    data=_buf2,
                    file_name=f"{_s}_{_yr}_Annual_Weighted_Estimates.png",
                    mime="image/png",
                )
            else:
                st.caption("Weighted estimate trend: not available.")

        with fig_cols[2]:
            _buf3 = fig_horizontal_bar(
                single_results["top_dx"], "Diagnosis", "Count",
                f"{single_label}: Top Diagnoses"
            )
            if _buf3:
                st.download_button(
                    "⬇️ Top diagnoses",
                    data=_buf3,
                    file_name=f"{_s}_{_yr}_Top_Diagnoses.png",
                    mime="image/png",
                )

        fig_cols2 = st.columns(3)

        with fig_cols2[0]:
            _buf4 = fig_horizontal_bar(
                single_results["top_body"], "Body Part", "Count",
                f"{single_label}: Top Body Parts"
            )
            if _buf4:
                st.download_button(
                    "⬇️ Top body parts",
                    data=_buf4,
                    file_name=f"{_s}_{_yr}_Top_Body_Parts.png",
                    mime="image/png",
                )

        with fig_cols2[1]:
            _buf5 = fig_horizontal_bar(
                single_results["disposition"], "Disposition", "Count",
                f"{single_label}: Disposition"
            )
            if _buf5:
                st.download_button(
                    "⬇️ Disposition",
                    data=_buf5,
                    file_name=f"{_s}_{_yr}_Disposition.png",
                    mime="image/png",
                )

        with fig_cols2[2]:
            _age_fig_df = single_results.get("age_groups")
            _buf6 = fig_age_groups(
                _age_fig_df,
                f"{single_label}: Age Group Breakdown"
            ) if _age_fig_df is not None else None
            if _buf6:
                st.download_button(
                    "⬇️ Age group breakdown",
                    data=_buf6,
                    file_name=f"{_s}_{_yr}_Age_Groups.png",
                    mime="image/png",
                )
            else:
                st.caption("Age group figure: not available.")

        st.markdown("---")

        st.markdown("## Downloads")

        summary_csv = summary_df.to_csv(index=False).encode("utf-8")
        annual_csv  = annual_df.to_csv(index=False).encode("utf-8")
        full_csv    = full_df.to_csv(index=False).encode("utf-8")

        d1, d2, d3 = st.columns(3)

        with d1:
            st.download_button(
                "Download summary table",
                data=summary_csv,
                file_name=f"{_s}_{_yr}_Summary.csv",
                mime="text/csv"
            )

        with d2:
            st.download_button(
                "Download annual trend table",
                data=annual_csv,
                file_name=f"{_s}_{_yr}_Annual_Trend.csv",
                mime="text/csv"
            )

        with d3:
            st.download_button(
                "Download matching cases",
                data=full_csv,
                file_name=f"{_s}_{_yr}_Cases.csv",
                mime="text/csv"
            )

        # New downloads for proportion CI and age group tables
        d4, d5 = st.columns(2)

        prop_df_dl = single_results.get("prop_summary")
        age_df_dl  = single_results.get("age_groups")

        with d4:
            if prop_df_dl is not None and not prop_df_dl.empty:
                st.download_button(
                    "Download proportions table",
                    data=prop_df_dl.to_csv(index=False).encode("utf-8"),
                    file_name=f"{_s}_{_yr}_Proportions.csv",
                    mime="text/csv"
                )

        with d5:
            if age_df_dl is not None and not age_df_dl.empty:
                st.download_button(
                    "Download age group table",
                    data=age_df_dl.to_csv(index=False).encode("utf-8"),
                    file_name=f"{_s}_{_yr}_Age_Groups.csv",
                    mime="text/csv"
                )

        # ---- MANUSCRIPT DRAFT ----
        st.markdown("---")
        with st.expander("📝 Manuscript Draft", expanded=False):
            has_wt_single = summary_dict.get("Weighted estimate") is not None

            _qc = quality_checks(
                "descriptive",
                year_range=year_range,
                keyword=keyword_filter,
                has_weight=has_wt_single,
                sample_n=summary_dict.get("Sample cases", 0),
            )
            _abstract = draft_abstract_descriptive(
                group_label=single_label,
                product_codes=single_codes,
                year_range=year_range,
                summary_dict=summary_dict,
                annual_df=annual_df,
                top_dx_df=single_results["top_dx"],
                top_body_df=single_results["top_body"],
                disposition_df=single_results["disposition"],
                age_groups_df=single_results.get("age_groups"),
                prop_summary_df=single_results.get("prop_summary"),
                keyword=keyword_filter,
            )
            _methods = draft_methods(
                "descriptive",
                year_range=year_range,
                product_codes=single_codes,
                group_label=single_label,
                age_min=age_min_filter,
                age_max=age_max_filter,
                sex_filter_label=sex_filter_label,
                keyword=keyword_filter,
                has_weight=has_wt_single,
            )
            _safe = single_label.replace(" ", "_")
            render_manuscript_section(
                abstract_text=_abstract,
                methods_text=_methods,
                checks=_qc,
                abstract_filename=f"{_safe}_Abstract.txt",
                methods_filename=f"{_safe}_Methods.txt",
                checklist_filename=f"{_safe}_QualityChecklist.csv",
            )

    except Exception as e:
        st.error("Something went wrong while running the single group study.")
        st.exception(e)


# ---------------------------------------------------------------------
# TREND ANALYSIS MODE
# ---------------------------------------------------------------------
elif study_mode == "Annual Trend Study":
    st.markdown("## Annual Trend Study")

    st.sidebar.subheader("Trend Cohort")

    trend_label = st.sidebar.text_input(
        "Cohort name",
        value="E-bike Injuries"
    )

    trend_codes_text = st.sidebar.text_area(
        "Product codes",
        value="5045",
        help="Example: 5045 for e-bikes, 3283 for skiing, 5031 for snowboarding"
    )

    run_trend = st.sidebar.button("Run Trend Analysis", type="primary")

    if not run_trend:
        st.info("Enter a cohort in the sidebar, then click **Run Trend Analysis**.")
        st.stop()

    try:
        trend_codes = parse_product_codes(trend_codes_text)

        if not trend_codes:
            st.error("Trend analysis needs at least one product code.")
            st.stop()

        with st.spinner("Running trend analysis..."):
            trend_results = run_trend_analysis(
                year_min=year_range[0],
                year_max=year_range[1],
                product_codes=trend_codes,
                age_min=age_min_filter,
                age_max=age_max_filter,
                sex=sex_filter,
                keyword=keyword_filter
            )

        trend_df = trend_results["trend_df"]
        full_df = trend_results["full_df"]

        # Filename components for all downloads and figures
        _st  = safe_label(trend_label)
        _yr_t = f"{year_range[0]}_{year_range[1]}"

        st.markdown(f"### {trend_label}")

        total_cases = len(full_df)

        if "weighted_estimate" in trend_df.columns:
            total_weighted = pd.to_numeric(
                trend_df["weighted_estimate"],
                errors="coerce"
            ).sum()
        else:
            total_weighted = None

        c1, c2 = st.columns(2)

        with c1:
            st.metric("Total sample cases", f"{total_cases:,}")

        with c2:
            if total_weighted is not None and total_weighted > 0:
                st.metric("Total weighted estimate", f"{round(total_weighted):,}")
            else:
                st.metric("Total weighted estimate", "Not found")

        st.markdown("### Annual Trend Table")
        st.dataframe(trend_df, use_container_width=True)

        st.markdown("### Annual Sample Cases")
        if not trend_df.empty:
            sample_chart = trend_df[["year", "sample_cases"]].copy()
            sample_chart = sample_chart.set_index("year")
            st.line_chart(sample_chart)
        else:
            st.info("No annual sample case data available.")

        st.markdown("### Annual Weighted National Estimates")
        if (
            not trend_df.empty
            and "weighted_estimate" in trend_df.columns
            and trend_df["weighted_estimate"].notna().any()
        ):
            weighted_chart = trend_df[["year", "weighted_estimate"]].copy()
            weighted_chart = weighted_chart.set_index("year")
            st.line_chart(weighted_chart)
        else:
            st.info("Weighted estimate column not available.")

        st.markdown("---")

        st.markdown("## Cohort Tables")

        t1, t2, t3 = st.columns(3)

        with t1:
            st.markdown("### Top Diagnoses")
            st.dataframe(trend_results["top_dx"], use_container_width=True)

        with t2:
            st.markdown("### Top Body Parts")
            st.dataframe(trend_results["top_body"], use_container_width=True)

        with t3:
            st.markdown("### Disposition")
            st.dataframe(trend_results["disposition"], use_container_width=True)

        st.markdown("---")

        # ---- NEW: Proportion CI table ----
        st.markdown("## Key Proportions with 95% Wilson CIs")
        trend_prop_df = trend_results.get("prop_summary")
        if trend_prop_df is not None and not trend_prop_df.empty:
            st.dataframe(trend_prop_df, use_container_width=True)
            st.caption(
                "Proportions are of the full filtered cohort across all selected years. "
                "95% CIs use the Wilson score method."
            )
        else:
            st.info("Proportion table not available.")

        st.markdown("---")

        # ---- NEW: Age group breakdown ----
        st.markdown("## Age Group Breakdown (Overall Cohort)")
        trend_age_df = trend_results.get("age_groups")
        if trend_age_df is not None and not trend_age_df.empty:
            st.dataframe(trend_age_df, use_container_width=True)
            st.caption(
                "Age groups across all selected years combined. "
                "95% CIs use the Wilson score method."
            )
        else:
            st.info("Age group table not available.")

        st.markdown("---")

        st.markdown("## Downloads")

        trend_csv = trend_df.to_csv(index=False).encode("utf-8")
        full_csv = full_df.to_csv(index=False).encode("utf-8")

        d1, d2 = st.columns(2)

        with d1:
            st.download_button(
                "Download annual trend table",
                data=trend_csv,
                file_name=f"{_st}_{_yr_t}_Annual_Trend.csv",
                mime="text/csv"
            )

        with d2:
            st.download_button(
                "Download matching cases",
                data=full_csv,
                file_name=f"{_st}_{_yr_t}_Cases.csv",
                mime="text/csv"
            )

        # New downloads for proportion CI and age group tables
        d3, d4 = st.columns(2)

        with d3:
            if trend_prop_df is not None and not trend_prop_df.empty:
                st.download_button(
                    "Download proportions table",
                    data=trend_prop_df.to_csv(index=False).encode("utf-8"),
                    file_name=f"{_st}_{_yr_t}_Proportions.csv",
                    mime="text/csv"
                )

        with d4:
            if trend_age_df is not None and not trend_age_df.empty:
                st.download_button(
                    "Download age group table",
                    data=trend_age_df.to_csv(index=False).encode("utf-8"),
                    file_name=f"{_st}_{_yr_t}_Age_Groups.csv",
                    mime="text/csv"
                )

        # ---- PNG Figure Downloads ----
        st.markdown("---")
        st.markdown("## 📥 Download Figures (PNG)")
        st.caption("Publication-ready PNG files at 150 dpi.")

        t_fig_cols = st.columns(3)

        with t_fig_cols[0]:
            _tbuf1 = fig_trend_line(
                trend_df, "sample_cases",
                f"{trend_label}: Annual Sample Cases", "Sample Cases (n)"
            )
            if _tbuf1:
                st.download_button(
                    "⬇️ Annual sample cases",
                    data=_tbuf1,
                    file_name=f"{_st}_{_yr_t}_Annual_Sample_Cases.png",
                    mime="image/png",
                )

        with t_fig_cols[1]:
            _has_wt_trend_fig = (
                not trend_df.empty
                and "weighted_estimate" in trend_df.columns
                and trend_df["weighted_estimate"].notna().any()
            )
            if _has_wt_trend_fig:
                _tbuf2 = fig_trend_line(
                    trend_df, "weighted_estimate",
                    f"{trend_label}: Annual Weighted Estimates",
                    "National Estimate", color="#5B8DB8",
                )
                if _tbuf2:
                    st.download_button(
                        "⬇️ Annual weighted estimates",
                        data=_tbuf2,
                        file_name=f"{_st}_{_yr_t}_Annual_Weighted_Estimates.png",
                        mime="image/png",
                    )
            else:
                st.caption("Weighted estimate trend: not available.")

        with t_fig_cols[2]:
            _tbuf3 = fig_horizontal_bar(
                trend_results["top_dx"], "Diagnosis", "Count",
                f"{trend_label}: Top Diagnoses"
            )
            if _tbuf3:
                st.download_button(
                    "⬇️ Top diagnoses",
                    data=_tbuf3,
                    file_name=f"{_st}_{_yr_t}_Top_Diagnoses.png",
                    mime="image/png",
                )

        t_fig_cols2 = st.columns(3)

        with t_fig_cols2[0]:
            _tbuf4 = fig_horizontal_bar(
                trend_results["top_body"], "Body Part", "Count",
                f"{trend_label}: Top Body Parts"
            )
            if _tbuf4:
                st.download_button(
                    "⬇️ Top body parts",
                    data=_tbuf4,
                    file_name=f"{_st}_{_yr_t}_Top_Body_Parts.png",
                    mime="image/png",
                )

        with t_fig_cols2[1]:
            _tbuf5 = fig_horizontal_bar(
                trend_results["disposition"], "Disposition", "Count",
                f"{trend_label}: Disposition"
            )
            if _tbuf5:
                st.download_button(
                    "⬇️ Disposition",
                    data=_tbuf5,
                    file_name=f"{_st}_{_yr_t}_Disposition.png",
                    mime="image/png",
                )

        with t_fig_cols2[2]:
            _t_age_df = trend_results.get("age_groups")
            if _t_age_df is not None:
                _tbuf6 = fig_age_groups(
                    _t_age_df, f"{trend_label}: Age Group Breakdown"
                )
                if _tbuf6:
                    st.download_button(
                        "⬇️ Age group breakdown",
                        data=_tbuf6,
                        file_name=f"{_st}_{_yr_t}_Age_Groups.png",
                        mime="image/png",
                    )
            else:
                st.caption("Age group figure: not available.")

        # ---- MANUSCRIPT DRAFT ----
        st.markdown("---")
        with st.expander("📝 Manuscript Draft", expanded=False):
            has_wt_trend = (
                total_weighted is not None and total_weighted > 0
            )
            _qc_t = quality_checks(
                "trend",
                year_range=year_range,
                keyword=keyword_filter,
                has_weight=has_wt_trend,
                sample_n=total_cases,
            )
            _abstract_t = draft_abstract_trend(
                group_label=trend_label,
                product_codes=trend_codes,
                year_range=year_range,
                trend_df=trend_df,
                top_dx_df=trend_results["top_dx"],
                top_body_df=trend_results["top_body"],
                disposition_df=trend_results["disposition"],
                prop_summary_df=trend_results.get("prop_summary"),
                keyword=keyword_filter,
            )
            _methods_t = draft_methods(
                "trend",
                year_range=year_range,
                product_codes=trend_codes,
                group_label=trend_label,
                age_min=age_min_filter,
                age_max=age_max_filter,
                sex_filter_label=sex_filter_label,
                keyword=keyword_filter,
                has_weight=has_wt_trend,
            )
            _safe_t = trend_label.replace(" ", "_")
            render_manuscript_section(
                abstract_text=_abstract_t,
                methods_text=_methods_t,
                checks=_qc_t,
                abstract_filename=f"{_safe_t}_Trend_Abstract.txt",
                methods_filename=f"{_safe_t}_Trend_Methods.txt",
                checklist_filename=f"{_safe_t}_Trend_QualityChecklist.csv",
            )

    except Exception as e:
        st.error("Something went wrong while running trend analysis.")
        st.exception(e)


# ---------------------------------------------------------------------
# TWO-GROUP COMPARISON MODE
# ---------------------------------------------------------------------
elif study_mode == "Comparative Cohort Study":
    st.markdown("## Comparative Cohort Study")

    st.sidebar.subheader("Group 1")
    group1_label = st.sidebar.text_input(
        "Group 1 name",
        value="Skiing"
    )
    group1_codes_text = st.sidebar.text_area(
        "Group 1 product codes",
        value="3283",
        help="Example: 3283"
    )

    st.sidebar.subheader("Group 2")
    group2_label = st.sidebar.text_input(
        "Group 2 name",
        value="Snowboarding"
    )
    group2_codes_text = st.sidebar.text_area(
        "Group 2 product codes",
        value="5031",
        help="Example: 5031"
    )

    run_comparison = st.sidebar.button("Run Comparison", type="primary")

    if not run_comparison:
        st.info("Enter two groups in the sidebar, then click **Run Comparison**.")
        st.stop()

    try:
        group1_codes = parse_product_codes(group1_codes_text)
        group2_codes = parse_product_codes(group2_codes_text)

        if not group1_codes:
            st.error("Group 1 needs at least one product code.")
            st.stop()

        if not group2_codes:
            st.error("Group 2 needs at least one product code.")
            st.stop()

        with st.spinner("Running two-group comparison..."):
            results = run_two_group_comparison(
                year_min=year_range[0],
                year_max=year_range[1],
                group1_label=group1_label,
                group1_codes=group1_codes,
                group2_label=group2_label,
                group2_codes=group2_codes,
                age_min=age_min_filter,
                age_max=age_max_filter,
                sex=sex_filter,
                keyword=keyword_filter
            )

        summary_df = results["summary"]

        # -----------------------------------------------------------------
        # Build dynamic filename base: "Skiing_vs_Snowboarding_2014_2024"
        # Replaces spaces/slashes with underscores; safe for all OS
        # -----------------------------------------------------------------
        def safe_name(s):
            return s.strip().replace(" ", "_").replace("/", "_")

        filename_base = (
            f"{safe_name(group1_label)}_vs_{safe_name(group2_label)}"
            f"_{year_range[0]}_{year_range[1]}"
        )

        # -----------------------------------------------------------------
        # Run statistics (done once, used across multiple tabs)
        # -----------------------------------------------------------------
        with st.spinner("Running statistical tests..."):
            stats_df = run_statistical_tests(
                results["group1_df"],
                results["group2_df"],
                group1_label,
                group2_label
            )

        stats_display_df = clean_stats_for_display(
            stats_df,
            group1_label,
            group2_label
        )

        # -----------------------------------------------------------------
        # Pre-compute manuscript text once — used in both Exports tab
        # (Word report) and Manuscript tab (on-screen display).
        # Done here so variables are in scope before either tab executes.
        # -----------------------------------------------------------------
        has_wt_comp = (
            results["summary"]["Weighted estimate"].notna().any()
            if "Weighted estimate" in results["summary"].columns else False
        )
        _qc_c = quality_checks(
            "comparative",
            year_range=year_range,
            keyword=keyword_filter,
            has_weight=has_wt_comp,
            group1_label=group1_label,
            group2_label=group2_label,
            group1_n=len(results["group1_df"]),
            group2_n=len(results["group2_df"]),
            stats_df=stats_df,
            prop_summary_df=results.get("group1_prop_summary"),
        )
        _abstract_c = draft_abstract_comparative(
            group1_label=group1_label,
            group1_codes=group1_codes,
            group2_label=group2_label,
            group2_codes=group2_codes,
            year_range=year_range,
            summary_df=results["summary"],
            stats_df=stats_df,
            group1_top_dx=results["group1_top_dx"],
            group2_top_dx=results["group2_top_dx"],
            group1_top_body=results.get("group1_top_body"),
            group2_top_body=results.get("group2_top_body"),
            comparative_age_groups=results.get("comparative_age_groups"),
            group1_prop_summary=results.get("group1_prop_summary"),
            group2_prop_summary=results.get("group2_prop_summary"),
            keyword=keyword_filter,
        )
        _methods_c = draft_methods(
            "comparative",
            year_range=year_range,
            product_codes=group1_codes + group2_codes,
            group1_label=group1_label,
            group1_codes=group1_codes,
            group2_label=group2_label,
            group2_codes=group2_codes,
            age_min=age_min_filter,
            age_max=age_max_filter,
            sex_filter_label=sex_filter_label,
            keyword=keyword_filter,
            has_weight=has_wt_comp,
        )

        # -----------------------------------------------------------------
        # SEVEN OUTPUT TABS
        # -----------------------------------------------------------------
        tab_overview, tab_stats, tab_charts, tab_tables, tab_exports, tab_raw, tab_manuscript = st.tabs([
            "📋 Overview",
            "📊 Statistics",
            "📈 Charts",
            "🗂 Tables",
            "💾 Exports",
            "🔍 Raw Data",
            "📝 Manuscript",
        ])

        # =================================================================
        # TAB 1: OVERVIEW
        # =================================================================
        with tab_overview:
            st.markdown("### Summary Comparison")
            st.dataframe(summary_df, use_container_width=True)

            st.markdown("### Sample Size")
            c1, c2 = st.columns(2)

            with c1:
                st.metric(
                    group1_label,
                    f"{len(results['group1_df']):,} cases"
                )

            with c2:
                st.metric(
                    group2_label,
                    f"{len(results['group2_df']):,} cases"
                )

            # ---- NEW: Proportion CI tables side-by-side ----
            st.markdown("### Key Proportions with 95% Wilson CIs")
            ov1, ov2 = st.columns(2)

            with ov1:
                st.markdown(f"#### {group1_label}")
                g1_prop = results.get("group1_prop_summary")
                if g1_prop is not None and not g1_prop.empty:
                    st.dataframe(g1_prop, use_container_width=True)
                else:
                    st.info("Proportion table not available.")

            with ov2:
                st.markdown(f"#### {group2_label}")
                g2_prop = results.get("group2_prop_summary")
                if g2_prop is not None and not g2_prop.empty:
                    st.dataframe(g2_prop, use_container_width=True)
                else:
                    st.info("Proportion table not available.")

            st.caption("95% CIs use the Wilson score method on unweighted sample counts.")

        # =================================================================
        # TAB 2: STATISTICS
        # =================================================================
        with tab_stats:
            st.markdown("### Statistical Testing")

            st.dataframe(stats_display_df, use_container_width=True)

            st.caption(
                "**Sig:** *** p<0.001  ** p<0.01  * p<0.05  ns p≥0.05  |  "
                "**OR:** Odds ratio (Group 1 vs Group 2).  "
                "**RR:** Relative risk (Group 1 vs Group 2).  "
                "**Effect size:** Rank-biserial r for Age distribution row; blank for binary outcomes.  "
                "**Warnings:** Flags small n (<20), cell counts <5, or zero events — interpret those rows with caution.  "
                "Chi-square used unless expected cell counts are small, then Fisher exact.  "
                "All statistics are unweighted sample counts."
            )

            stats_csv = stats_df.to_csv(index=False).encode("utf-8")

            st.download_button(
                "Download statistics as CSV",
                data=stats_csv,
                file_name=f"{filename_base}_Statistics.csv",
                mime="text/csv"
            )

        # =================================================================
        # TAB 3: CHARTS
        # =================================================================
        with tab_charts:
            chart_tabs = st.tabs([
                "Group Overview",
                "Diagnoses",
                "Body Parts",
                "Disposition"
            ])

            with chart_tabs[0]:
                st.markdown("### Group-Level Comparisons")

                c1, c2 = st.columns(2)

                with c1:
                    show_bar_chart(
                        "Sample Cases",
                        make_group_metric_chart(summary_df, "Sample cases")
                    )

                with c2:
                    show_bar_chart(
                        "Weighted National Estimate",
                        make_group_metric_chart(summary_df, "Weighted estimate")
                    )

                c3, c4 = st.columns(2)

                with c3:
                    show_bar_chart(
                        "Mean Age",
                        make_group_metric_chart(summary_df, "Mean age")
                    )

                with c4:
                    show_bar_chart(
                        "Pediatric Percent",
                        make_group_metric_chart(summary_df, "% Pediatric")
                    )

                c5, c6 = st.columns(2)

                with c5:
                    show_bar_chart(
                        "Percent Male",
                        make_group_metric_chart(summary_df, "% Male")
                    )

                with c6:
                    show_bar_chart(
                        "Percent Female",
                        make_group_metric_chart(summary_df, "% Female")
                    )

                # PNG downloads for group overview
                st.markdown("**📥 Download figures:**")
                ov_dl_cols = st.columns(3)
                for _metric, _fname_part, _col in [
                    ("Sample cases",     "Sample_Cases",   ov_dl_cols[0]),
                    ("Mean age",         "Mean_Age",       ov_dl_cols[1]),
                    ("% Pediatric",      "Pct_Pediatric",  ov_dl_cols[2]),
                ]:
                    _buf_ov = fig_grouped_bar(
                        summary_df, _metric,
                        f"{group1_label} vs {group2_label}: {_metric}"
                    )
                    if _buf_ov:
                        with _col:
                            st.download_button(
                                f"⬇️ {_metric}",
                                data=_buf_ov,
                                file_name=f"{filename_base}_{_fname_part}.png",
                                mime="image/png",
                            )

            with chart_tabs[1]:
                st.markdown("### Top Diagnoses")

                dx1, dx2 = st.columns(2)

                with dx1:
                    show_bar_chart(
                        f"{group1_label}: Top Diagnoses",
                        make_category_chart(results["group1_top_dx"], "Diagnosis")
                    )

                with dx2:
                    show_bar_chart(
                        f"{group2_label}: Top Diagnoses",
                        make_category_chart(results["group2_top_dx"], "Diagnosis")
                    )

                # PNG downloads for diagnoses
                st.markdown("**📥 Download figures:**")
                dx_dl1, dx_dl2 = st.columns(2)
                _bdx1 = fig_horizontal_bar(
                    results["group1_top_dx"], "Diagnosis", "Count",
                    f"{group1_label}: Top Diagnoses"
                )
                _bdx2 = fig_horizontal_bar(
                    results["group2_top_dx"], "Diagnosis", "Count",
                    f"{group2_label}: Top Diagnoses"
                )
                if _bdx1:
                    with dx_dl1:
                        st.download_button(
                            f"⬇️ {group1_label} diagnoses",
                            data=_bdx1,
                            file_name=f"{filename_base}_{safe_name(group1_label)}_Top_Diagnoses.png",
                            mime="image/png",
                        )
                if _bdx2:
                    with dx_dl2:
                        st.download_button(
                            f"⬇️ {group2_label} diagnoses",
                            data=_bdx2,
                            file_name=f"{filename_base}_{safe_name(group2_label)}_Top_Diagnoses.png",
                            mime="image/png",
                        )

            with chart_tabs[2]:
                st.markdown("### Top Body Parts")

                bp1, bp2 = st.columns(2)

                with bp1:
                    show_bar_chart(
                        f"{group1_label}: Top Body Parts",
                        make_category_chart(results["group1_top_body"], "Body Part")
                    )

                with bp2:
                    show_bar_chart(
                        f"{group2_label}: Top Body Parts",
                        make_category_chart(results["group2_top_body"], "Body Part")
                    )

                # PNG downloads for body parts
                st.markdown("**📥 Download figures:**")
                bp_dl1, bp_dl2 = st.columns(2)
                _bbp1 = fig_horizontal_bar(
                    results["group1_top_body"], "Body Part", "Count",
                    f"{group1_label}: Top Body Parts"
                )
                _bbp2 = fig_horizontal_bar(
                    results["group2_top_body"], "Body Part", "Count",
                    f"{group2_label}: Top Body Parts"
                )
                if _bbp1:
                    with bp_dl1:
                        st.download_button(
                            f"⬇️ {group1_label} body parts",
                            data=_bbp1,
                            file_name=f"{filename_base}_{safe_name(group1_label)}_Top_Body_Parts.png",
                            mime="image/png",
                        )
                if _bbp2:
                    with bp_dl2:
                        st.download_button(
                            f"⬇️ {group2_label} body parts",
                            data=_bbp2,
                            file_name=f"{filename_base}_{safe_name(group2_label)}_Top_Body_Parts.png",
                            mime="image/png",
                        )

            with chart_tabs[3]:
                st.markdown("### Disposition Breakdown")

                disp1, disp2 = st.columns(2)

                with disp1:
                    show_bar_chart(
                        f"{group1_label}: Disposition",
                        make_category_chart(results["group1_disposition"], "Disposition")
                    )

                with disp2:
                    show_bar_chart(
                        f"{group2_label}: Disposition",
                        make_category_chart(results["group2_disposition"], "Disposition")
                    )

                # PNG downloads for disposition
                st.markdown("**📥 Download figures:**")
                d_dl1, d_dl2 = st.columns(2)
                _bd1 = fig_horizontal_bar(
                    results["group1_disposition"], "Disposition", "Count",
                    f"{group1_label}: Disposition"
                )
                _bd2 = fig_horizontal_bar(
                    results["group2_disposition"], "Disposition", "Count",
                    f"{group2_label}: Disposition"
                )
                if _bd1:
                    with d_dl1:
                        st.download_button(
                            f"⬇️ {group1_label} disposition",
                            data=_bd1,
                            file_name=f"{filename_base}_{safe_name(group1_label)}_Disposition.png",
                            mime="image/png",
                        )
                if _bd2:
                    with d_dl2:
                        st.download_button(
                            f"⬇️ {group2_label} disposition",
                            data=_bd2,
                            file_name=f"{filename_base}_{safe_name(group2_label)}_Disposition.png",
                            mime="image/png",
                        )

            # Age group comparison PNG — shown outside the sub-tabs
            _g1_age = results.get("group1_age_groups")
            _g2_age = results.get("group2_age_groups")
            if _g1_age is not None or _g2_age is not None:
                st.markdown("**📥 Age group comparison figure:**")
                _bage = fig_age_groups_comparison(
                    _g1_age, group1_label,
                    _g2_age, group2_label,
                    f"{group1_label} vs {group2_label}: Age Groups"
                )
                if _bage:
                    st.download_button(
                        "⬇️ Age group comparison",
                        data=_bage,
                        file_name=f"{filename_base}_Age_Groups_Comparison.png",
                        mime="image/png",
                    )

        # =================================================================
        # TAB 4: TABLES
        # =================================================================
        with tab_tables:
            st.markdown("### Top Diagnoses")
            dx1, dx2 = st.columns(2)

            with dx1:
                st.markdown(f"#### {group1_label}")
                st.dataframe(results["group1_top_dx"], use_container_width=True)

            with dx2:
                st.markdown(f"#### {group2_label}")
                st.dataframe(results["group2_top_dx"], use_container_width=True)

            st.markdown("### Top Body Parts")
            bp1, bp2 = st.columns(2)

            with bp1:
                st.markdown(f"#### {group1_label}")
                st.dataframe(results["group1_top_body"], use_container_width=True)

            with bp2:
                st.markdown(f"#### {group2_label}")
                st.dataframe(results["group2_top_body"], use_container_width=True)

            st.markdown("### Disposition Breakdown")
            disp1, disp2 = st.columns(2)

            with disp1:
                st.markdown(f"#### {group1_label}")
                st.dataframe(results["group1_disposition"], use_container_width=True)

            with disp2:
                st.markdown(f"#### {group2_label}")
                st.dataframe(results["group2_disposition"], use_container_width=True)

            # ---- NEW: Age group comparison table ----
            st.markdown("### Age Group Comparison")
            comp_age = results.get("comparative_age_groups")
            if comp_age is not None and not comp_age.empty:
                st.dataframe(comp_age, use_container_width=True)
                st.caption(
                    "Chi-square p-value tests the overall 2×4 age group distribution. "
                    "95% CIs use the Wilson score method on unweighted counts."
                )
            else:
                st.info("Age group comparison not available.")

            # ---- NEW: Individual age group breakdowns ----
            st.markdown("### Age Group Breakdowns")
            ag1, ag2 = st.columns(2)

            with ag1:
                st.markdown(f"#### {group1_label}")
                g1_age = results.get("group1_age_groups")
                if g1_age is not None and not g1_age.empty:
                    st.dataframe(g1_age, use_container_width=True)
                else:
                    st.info("Not available.")

            with ag2:
                st.markdown(f"#### {group2_label}")
                g2_age = results.get("group2_age_groups")
                if g2_age is not None and not g2_age.empty:
                    st.dataframe(g2_age, use_container_width=True)
                else:
                    st.info("Not available.")

        # =================================================================
        # TAB 5: EXPORTS  (Word + Excel + CSV downloads)
        # =================================================================
        with tab_exports:
            st.markdown("### Word Report")

            report_stream = generate_word_report(
                study_title=study_title,
                research_question=research_question,
                year_range=year_range,
                group1_label=group1_label,
                group1_codes=group1_codes,
                group2_label=group2_label,
                group2_codes=group2_codes,
                summary_df=summary_df,
                stats_display_df=stats_display_df,
                group1_top_dx=results["group1_top_dx"],
                group2_top_dx=results["group2_top_dx"],
                group1_top_body=results["group1_top_body"],
                group2_top_body=results["group2_top_body"],
                group1_disposition=results["group1_disposition"],
                group2_disposition=results["group2_disposition"],
                comparative_age_groups=results.get("comparative_age_groups"),
                group1_age_groups=results.get("group1_age_groups"),
                group2_age_groups=results.get("group2_age_groups"),
                group1_prop_summary=results.get("group1_prop_summary"),
                group2_prop_summary=results.get("group2_prop_summary"),
                abstract_text=_abstract_c,
                methods_text=_methods_c,
            )

            st.download_button(
                label="⬇️ Download Word report",
                data=report_stream,
                file_name=f"{filename_base}_Report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

            st.markdown("### Excel Workbook")

            excel_stream = generate_excel_workbook(
                summary_df=summary_df,
                stats_display_df=stats_display_df,
                group1_label=group1_label,
                group2_label=group2_label,
                group1_top_dx=results["group1_top_dx"],
                group2_top_dx=results["group2_top_dx"],
                group1_top_body=results["group1_top_body"],
                group2_top_body=results["group2_top_body"],
                group1_disposition=results["group1_disposition"],
                group2_disposition=results["group2_disposition"],
                group1_df=results["group1_df"],
                group2_df=results["group2_df"],
                group1_age_groups=results.get("group1_age_groups"),
                group2_age_groups=results.get("group2_age_groups"),
                comparative_age_groups=results.get("comparative_age_groups"),
                group1_prop_summary=results.get("group1_prop_summary"),
                group2_prop_summary=results.get("group2_prop_summary"),
            )

            st.download_button(
                label="⬇️ Download Excel workbook",
                data=excel_stream,
                file_name=f"{filename_base}_Workbook.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            st.markdown("### CSV Downloads")

            group1_csv = results["group1_df"].to_csv(index=False).encode("utf-8")
            group2_csv = results["group2_df"].to_csv(index=False).encode("utf-8")
            summary_csv = summary_df.to_csv(index=False).encode("utf-8")

            d1, d2, d3 = st.columns(3)

            with d1:
                st.download_button(
                    f"⬇️ {group1_label} cases (CSV)",
                    data=group1_csv,
                    file_name=f"{safe_name(group1_label)}_{year_range[0]}_{year_range[1]}_cases.csv",
                    mime="text/csv"
                )

            with d2:
                st.download_button(
                    f"⬇️ {group2_label} cases (CSV)",
                    data=group2_csv,
                    file_name=f"{safe_name(group2_label)}_{year_range[0]}_{year_range[1]}_cases.csv",
                    mime="text/csv"
                )

            with d3:
                st.download_button(
                    "⬇️ Summary table (CSV)",
                    data=summary_csv,
                    file_name=f"{filename_base}_Summary.csv",
                    mime="text/csv"
                )

        # =================================================================
        # TAB 6: RAW DATA
        # =================================================================
        with tab_raw:
            st.markdown(f"### {group1_label} — Raw Cases ({len(results['group1_df']):,} rows)")
            st.dataframe(results["group1_df"], use_container_width=True)

            st.markdown(f"### {group2_label} — Raw Cases ({len(results['group2_df']):,} rows)")
            st.dataframe(results["group2_df"], use_container_width=True)

        # =================================================================
        # TAB 7: MANUSCRIPT DRAFT
        # =================================================================
        with tab_manuscript:
            render_manuscript_section(
                abstract_text=_abstract_c,
                methods_text=_methods_c,
                checks=_qc_c,
                abstract_filename=f"{filename_base}_Abstract.txt",
                methods_filename=f"{filename_base}_Methods.txt",
                checklist_filename=f"{filename_base}_QualityChecklist.csv",
            )

    except Exception as e:
        st.error("Something went wrong while running the comparison.")
        st.exception(e)
