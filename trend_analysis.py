import pandas as pd
from database import get_connection
from analysis import build_where_clause, find_column, top_category_table
from proportions import age_group_table, proportion_summary_table


def run_trend_analysis(
    year_min,
    year_max,
    product_codes,
    age_min=None,
    age_max=None,
    sex=None,
    keyword=""
):
    """
    Run a year-by-year trend analysis for one cohort.
    Returns:
    - annual sample cases
    - annual weighted national estimates, if weight exists
    - full cohort dataframe
    - top diagnoses
    - top body parts
    - disposition breakdown
    """

    con = get_connection()

    where_sql, params = build_where_clause(
        year_min=year_min,
        year_max=year_max,
        product_codes=product_codes,
        age_min=age_min,
        age_max=age_max,
        sex=sex,
        keyword=keyword
    )

    weight_col = find_column(["weight", "wt"])

    if weight_col:
        trend_query = f"""
        SELECT
            year,
            COUNT(*) AS sample_cases,
            SUM({weight_col}) AS weighted_estimate
        FROM neiss_cases
        WHERE {where_sql}
        GROUP BY year
        ORDER BY year
        """
    else:
        trend_query = f"""
        SELECT
            year,
            COUNT(*) AS sample_cases,
            NULL AS weighted_estimate
        FROM neiss_cases
        WHERE {where_sql}
        GROUP BY year
        ORDER BY year
        """

    trend_df = con.execute(trend_query, params).df()

    full_query = f"""
    SELECT *
    FROM neiss_cases
    WHERE {where_sql}
    """

    full_df = con.execute(full_query, params).df()

    top_dx = top_category_table(
        full_df,
        ["diagnosis", "diag"],
        "Diagnosis",
        top_n=10
    )

    top_body = top_category_table(
        full_df,
        ["body_part", "bodypart", "body_part_1", "bodypart_1"],
        "Body Part",
        top_n=10
    )

    disposition = top_category_table(
        full_df,
        ["disposition", "disp"],
        "Disposition",
        top_n=10
    )

    # Overall cohort age group breakdown (not per-year)
    weight_col_name = find_column(["weight", "wt"])
    age_groups = age_group_table(
        full_df,
        label="Cohort",
        weight_col=weight_col_name if weight_col_name else None,
    )

    # Key proportion summary with Wilson CIs
    prop_summary = proportion_summary_table(full_df, label="Cohort")

    return {
        "trend_df": trend_df,
        "full_df": full_df,
        "top_dx": top_dx,
        "top_body": top_body,
        "disposition": disposition,
        "age_groups": age_groups,
        "prop_summary": prop_summary,
    }
