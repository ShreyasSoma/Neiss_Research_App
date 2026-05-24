import pandas as pd
from database import get_connection, get_columns
from code_mappings import DIAGNOSIS_MAP, BODY_PART_MAP, DISPOSITION_MAP, label_code
from proportions import age_group_table, proportion_summary_table, comparative_age_group_table


def normalize_column_lookup():
    columns = get_columns()
    return {col.lower(): col for col in columns}


def find_column(possible_names):
    lookup = normalize_column_lookup()

    for name in possible_names:
        if name.lower() in lookup:
            return lookup[name.lower()]

    return None


def parse_product_codes(text):
    if not text.strip():
        return []

    codes = []

    for part in text.replace("\n", ",").split(","):
        part = part.strip()
        if not part:
            continue

        try:
            codes.append(int(part))
        except ValueError:
            raise ValueError(f"Invalid product code: {part}")

    return codes


def build_where_clause(
    year_min,
    year_max,
    product_codes,
    age_min=None,
    age_max=None,
    sex=None,
    keyword=""
):
    where_parts = ["year BETWEEN ? AND ?"]
    params = [year_min, year_max]

    product_col = find_column(["prod1", "product_1", "product1", "product"])

    if product_codes:
        if product_col is None:
            raise ValueError("Could not find a product code column.")

        placeholders = ",".join(["?"] * len(product_codes))
        where_parts.append(f"{product_col} IN ({placeholders})")
        params.extend(product_codes)

    age_col = find_column(["age"])

    if age_min is not None and age_col:
        where_parts.append(f"{age_col} >= ?")
        params.append(age_min)

    if age_max is not None and age_col:
        where_parts.append(f"{age_col} <= ?")
        params.append(age_max)

    sex_col = find_column(["sex"])

    if sex is not None and sex_col:
        where_parts.append(f"{sex_col} = ?")
        params.append(sex)

    narrative_col = find_column([
        "narrative",
        "narr1",
        "narrative_1",
        "narrative1",
        "case_narrative"
    ])

    if keyword and keyword.strip() and narrative_col:
        where_parts.append(f"LOWER(CAST({narrative_col} AS VARCHAR)) LIKE ?")
        params.append(f"%{keyword.lower().strip()}%")

    where_sql = " AND ".join(where_parts)
    return where_sql, params


def run_basic_query(
    year_min,
    year_max,
    product_codes,
    age_min=None,
    age_max=None,
    sex=None,
    keyword=""
):
    con = get_connection()

    where_sql, params = build_where_clause(
        year_min,
        year_max,
        product_codes,
        age_min=age_min,
        age_max=age_max,
        sex=sex,
        keyword=keyword
    )

    count_query = f"""
    SELECT COUNT(*)
    FROM neiss_cases
    WHERE {where_sql}
    """

    case_count = con.execute(count_query, params).fetchone()[0]

    weight_col = find_column(["weight", "wt"])

    if weight_col:
        estimate_query = f"""
        SELECT SUM({weight_col})
        FROM neiss_cases
        WHERE {where_sql}
        """
        weighted_estimate = con.execute(estimate_query, params).fetchone()[0]
    else:
        weighted_estimate = None

    sample_query = f"""
    SELECT *
    FROM neiss_cases
    WHERE {where_sql}
    LIMIT 100
    """

    sample_df = con.execute(sample_query, params).df()

    full_query = f"""
    SELECT *
    FROM neiss_cases
    WHERE {where_sql}
    """

    full_df = con.execute(full_query, params).df()

    return {
        "case_count": case_count,
        "weighted_estimate": weighted_estimate,
        "sample_df": sample_df,
        "full_df": full_df,
    }


def get_group_dataframe(
    year_min,
    year_max,
    product_codes,
    age_min=None,
    age_max=None,
    sex=None,
    keyword=""
):
    con = get_connection()

    where_sql, params = build_where_clause(
        year_min,
        year_max,
        product_codes,
        age_min=age_min,
        age_max=age_max,
        sex=sex,
        keyword=keyword
    )

    query = f"""
    SELECT *
    FROM neiss_cases
    WHERE {where_sql}
    """

    return con.execute(query, params).df()


def summarize_group(label, df):
    age_col = find_column(["age"])
    sex_col = find_column(["sex"])
    weight_col = find_column(["weight", "wt"])

    sample_cases = len(df)

    if sample_cases == 0:
        return {
            "Group": label,
            "Sample cases": 0,
            "Weighted estimate": None,
            "Mean age": None,
            "Median age": None,
            "% Male": None,
            "% Female": None,
            "% Pediatric": None,
            "% Adult": None,
        }

    if weight_col and weight_col in df.columns:
        weighted_estimate = df[weight_col].sum()
    else:
        weighted_estimate = None

    if age_col and age_col in df.columns:
        age_series = pd.to_numeric(df[age_col], errors="coerce")
        mean_age = age_series.mean()
        median_age = age_series.median()
        pediatric_pct = (age_series < 18).mean() * 100
        adult_pct = (age_series >= 18).mean() * 100
    else:
        mean_age = None
        median_age = None
        pediatric_pct = None
        adult_pct = None

    if sex_col and sex_col in df.columns:
        sex_series = pd.to_numeric(df[sex_col], errors="coerce")
        male_pct = (sex_series == 1).mean() * 100
        female_pct = (sex_series == 2).mean() * 100
    else:
        male_pct = None
        female_pct = None

    return {
        "Group": label,
        "Sample cases": sample_cases,
        "Weighted estimate": weighted_estimate,
        "Mean age": mean_age,
        "Median age": median_age,
        "% Male": male_pct,
        "% Female": female_pct,
        "% Pediatric": pediatric_pct,
        "% Adult": adult_pct,
    }


def top_category_table(df, possible_columns, label, top_n=10):
    col = find_column(possible_columns)

    if col is None or col not in df.columns or len(df) == 0:
        return pd.DataFrame(columns=[label, "Count", "Percent"])

    counts = df[col].value_counts(dropna=False).head(top_n).reset_index()
    counts.columns = [label, "Count"]
    counts["Percent"] = counts["Count"] / len(df) * 100
    counts["Percent"] = counts["Percent"].round(2)

    if label == "Diagnosis":
        counts[label] = counts[label].apply(lambda x: label_code(x, DIAGNOSIS_MAP))

    elif label == "Body Part":
        counts[label] = counts[label].apply(lambda x: label_code(x, BODY_PART_MAP))

    elif label == "Disposition":
        counts[label] = counts[label].apply(lambda x: label_code(x, DISPOSITION_MAP))

    return counts


def disposition_table(df):
    return top_category_table(
        df,
        ["disposition", "disp"],
        "Disposition",
        top_n=10
    )


def run_two_group_comparison(
    year_min,
    year_max,
    group1_label,
    group1_codes,
    group2_label,
    group2_codes,
    age_min=None,
    age_max=None,
    sex=None,
    keyword=""
):
    group1_df = get_group_dataframe(
        year_min,
        year_max,
        group1_codes,
        age_min=age_min,
        age_max=age_max,
        sex=sex,
        keyword=keyword
    )

    group2_df = get_group_dataframe(
        year_min,
        year_max,
        group2_codes,
        age_min=age_min,
        age_max=age_max,
        sex=sex,
        keyword=keyword
    )

    summary = pd.DataFrame([
        summarize_group(group1_label, group1_df),
        summarize_group(group2_label, group2_df),
    ])

    numeric_cols = [
        "Weighted estimate",
        "Mean age",
        "Median age",
        "% Male",
        "% Female",
        "% Pediatric",
        "% Adult",
    ]

    for col in numeric_cols:
        if col in summary.columns:
            summary[col] = summary[col].round(2)

    group1_top_dx = top_category_table(
        group1_df,
        ["diagnosis", "diag"],
        "Diagnosis",
        top_n=10
    )

    group2_top_dx = top_category_table(
        group2_df,
        ["diagnosis", "diag"],
        "Diagnosis",
        top_n=10
    )

    group1_top_body = top_category_table(
        group1_df,
        ["body_part", "bodypart", "body_part_1", "bodypart_1"],
        "Body Part",
        top_n=10
    )

    group2_top_body = top_category_table(
        group2_df,
        ["body_part", "bodypart", "body_part_1", "bodypart_1"],
        "Body Part",
        top_n=10
    )

    group1_disposition = disposition_table(group1_df)
    group2_disposition = disposition_table(group2_df)

    # Resolve weight column for age group weighted estimates
    weight_col = find_column(["weight", "wt"])

    # Age group breakdown for each group
    group1_age_groups = age_group_table(
        group1_df,
        label=group1_label,
        weight_col=weight_col if weight_col else None,
    )
    group2_age_groups = age_group_table(
        group2_df,
        label=group2_label,
        weight_col=weight_col if weight_col else None,
    )

    # Side-by-side comparative age group table with chi-square
    comparative_age_groups = comparative_age_group_table(
        group1_df, group1_label,
        group2_df, group2_label,
    )

    # Key proportion summaries with Wilson CIs
    group1_prop_summary = proportion_summary_table(group1_df, label=group1_label)
    group2_prop_summary = proportion_summary_table(group2_df, label=group2_label)

    return {
        "summary": summary,
        "group1_df": group1_df,
        "group2_df": group2_df,
        "group1_top_dx": group1_top_dx,
        "group2_top_dx": group2_top_dx,
        "group1_top_body": group1_top_body,
        "group2_top_body": group2_top_body,
        "group1_disposition": group1_disposition,
        "group2_disposition": group2_disposition,
        "group1_age_groups": group1_age_groups,
        "group2_age_groups": group2_age_groups,
        "comparative_age_groups": comparative_age_groups,
        "group1_prop_summary": group1_prop_summary,
        "group2_prop_summary": group2_prop_summary,
    }
