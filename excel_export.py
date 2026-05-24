from io import BytesIO
import pandas as pd


def safe_sheet_name(name):
    """
    Excel sheet names must be <=31 characters and cannot contain certain symbols.
    """
    invalid_chars = ["\\", "/", "*", "?", ":", "[", "]"]

    for char in invalid_chars:
        name = name.replace(char, "")

    return name[:31]


def generate_excel_workbook(
    summary_df,
    stats_display_df,
    group1_label,
    group2_label,
    group1_top_dx,
    group2_top_dx,
    group1_top_body,
    group2_top_body,
    group1_disposition,
    group2_disposition,
    group1_df,
    group2_df,
    # New parameters for age group and proportion CI tables.
    # Default to None so existing call sites without these args still work.
    group1_age_groups=None,
    group2_age_groups=None,
    comparative_age_groups=None,
    group1_prop_summary=None,
    group2_prop_summary=None,
):
    """
    Generate an Excel workbook with separate sheets for each table.
    Returns an in-memory BytesIO object for Streamlit download.
    """

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

        stats_display_df.to_excel(writer, sheet_name="Statistics", index=False)

        group1_top_dx.to_excel(
            writer,
            sheet_name=safe_sheet_name(f"{group1_label} Diagnoses"),
            index=False
        )

        group2_top_dx.to_excel(
            writer,
            sheet_name=safe_sheet_name(f"{group2_label} Diagnoses"),
            index=False
        )

        group1_top_body.to_excel(
            writer,
            sheet_name=safe_sheet_name(f"{group1_label} Body Parts"),
            index=False
        )

        group2_top_body.to_excel(
            writer,
            sheet_name=safe_sheet_name(f"{group2_label} Body Parts"),
            index=False
        )

        group1_disposition.to_excel(
            writer,
            sheet_name=safe_sheet_name(f"{group1_label} Disposition"),
            index=False
        )

        group2_disposition.to_excel(
            writer,
            sheet_name=safe_sheet_name(f"{group2_label} Disposition"),
            index=False
        )

        # Limit raw sheets to avoid giant Excel files crashing
        group1_df.head(50000).to_excel(
            writer,
            sheet_name=safe_sheet_name(f"{group1_label} Raw Cases"),
            index=False
        )

        group2_df.head(50000).to_excel(
            writer,
            sheet_name=safe_sheet_name(f"{group2_label} Raw Cases"),
            index=False
        )

        # ---- New sheets: age group breakdowns ----
        if comparative_age_groups is not None and not comparative_age_groups.empty:
            comparative_age_groups.to_excel(
                writer,
                sheet_name="Age Groups Comparison",
                index=False,
            )

        if group1_age_groups is not None and not group1_age_groups.empty:
            group1_age_groups.to_excel(
                writer,
                sheet_name=safe_sheet_name(f"{group1_label} Age Groups"),
                index=False,
            )

        if group2_age_groups is not None and not group2_age_groups.empty:
            group2_age_groups.to_excel(
                writer,
                sheet_name=safe_sheet_name(f"{group2_label} Age Groups"),
                index=False,
            )

        # ---- New sheets: proportion summaries with Wilson CIs ----
        if group1_prop_summary is not None and not group1_prop_summary.empty:
            group1_prop_summary.to_excel(
                writer,
                sheet_name=safe_sheet_name(f"{group1_label} Proportions"),
                index=False,
            )

        if group2_prop_summary is not None and not group2_prop_summary.empty:
            group2_prop_summary.to_excel(
                writer,
                sheet_name=safe_sheet_name(f"{group2_label} Proportions"),
                index=False,
            )

    output.seek(0)
    return output
