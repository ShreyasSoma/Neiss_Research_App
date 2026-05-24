from database import get_connection
from analysis import (
    build_where_clause,
    find_column,
    summarize_group,
    top_category_table,
)
from proportions import age_group_table, proportion_summary_table


def run_single_group_study(
    year_min,
    year_max,
    group_label,
    product_codes,
    age_min=None,
    age_max=None,
    sex=None,
    keyword=""
):
    """
    Run a full descriptive single-group study.

    Returns:
    - summary table
    - annual trend table
    - top diagnoses
    - top body parts
    - disposition breakdown
    - raw matching cases
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

    full_query = f"""
    SELECT *
    FROM neiss_cases
    WHERE {where_sql}
    """

    full_df = con.execute(full_query, params).df()

    summary = summarize_group(group_label, full_df)

    weight_col = find_column(["weight", "wt"])

    if weight_col:
        annual_query = f"""
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
        annual_query = f"""
        SELECT
            year,
            COUNT(*) AS sample_cases,
            NULL AS weighted_estimate
        FROM neiss_cases
        WHERE {where_sql}
        GROUP BY year
        ORDER BY year
        """

    annual_df = con.execute(annual_query, params).df()

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

    # Resolve weight column name once for proportion tables
    weight_col = find_column(["weight", "wt"])

    # Age group breakdown with Wilson CIs
    age_groups = age_group_table(
        full_df,
        label=group_label,
        weight_col=weight_col if weight_col else None,
    )

    # Key proportion summary with Wilson CIs (display-only; does not alter
    # the numeric summary dict used by charts)
    prop_summary = proportion_summary_table(full_df, label=group_label)

    return {
        "summary": summary,
        "annual_df": annual_df,
        "top_dx": top_dx,
        "top_body": top_body,
        "disposition": disposition,
        "full_df": full_df,
        "age_groups": age_groups,
        "prop_summary": prop_summary,
    }
