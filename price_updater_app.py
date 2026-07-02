import io
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Campaign Price Updater", layout="wide")
st.title("Campaign Price Updater")
st.caption(
    "Looks up each SKU's Article Number from the Content file, pulls RRP/SRP "
    "for that Article Number from the Zecom Tracker, adds Article Number, RRP, "
    "and SRP as new columns in the Campaign sheet, and fills the campaign price "
    "column with SRP (falling back to RRP whenever SRP is blank or 0)."
)

col1, col2, col3 = st.columns(3)
with col1:
    campaign_file = st.file_uploader(
        "Campaign file (has SKU, Campaign Price)",
        type=["xlsx", "csv"], key="campaign_file",
    )
with col2:
    content_file = st.file_uploader(
        "Content file (has SKU, Article Number)",
        type=["xlsx", "csv"], key="content_file",
    )
with col3:
    tracker_file = st.file_uploader(
        "Zecom Tracker (has Article Number, RRP, SRP)",
        type=["xlsx", "csv"], key="tracker_file",
    )


def excel_col_letter(idx):
    """Convert a 0-based column index to Excel-style letters (0->A, 25->Z, 26->AA...)."""
    letters = ""
    idx += 1
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def make_col_formatter(columns):
    """Return a format_func that prefixes each column name with its Excel letter."""
    cols = list(columns)

    def fmt(col):
        letter = excel_col_letter(cols.index(col))
        return f"{letter}: {col}"

    return fmt


def read_any(uploaded_file, sheet_picker_key):
    """Read an uploaded csv/xlsx, letting the user pick a sheet for xlsx."""
    if uploaded_file.name.lower().endswith(".csv"):
        return pd.read_csv(uploaded_file)
    xls = pd.ExcelFile(uploaded_file)
    sheet = st.selectbox(
        f"Sheet for {uploaded_file.name}", xls.sheet_names, key=sheet_picker_key
    )
    return xls.parse(sheet)


campaign_df = None
content_df = None
tracker_df = None

if campaign_file is not None:
    st.subheader("Campaign file")
    campaign_df = read_any(campaign_file, "campaign_sheet")
    st.dataframe(campaign_df.head(5), use_container_width=True)

if content_file is not None:
    st.subheader("Content file")
    content_df = read_any(content_file, "content_sheet")
    st.dataframe(content_df.head(5), use_container_width=True)

if tracker_file is not None:
    st.subheader("Zecom Tracker")
    tracker_df = read_any(tracker_file, "tracker_sheet")
    st.dataframe(tracker_df.head(5), use_container_width=True)

if campaign_df is not None and content_df is not None and tracker_df is not None:
    st.subheader("Map columns")

    c1, c2 = st.columns(2)
    with c1:
        campaign_sku_col = st.selectbox(
            "SKU column (in Campaign file)", campaign_df.columns, key="campaign_sku_col",
            format_func=make_col_formatter(campaign_df.columns),
        )
    with c2:
        campaign_price_col = st.selectbox(
            "Campaign Price column to update (in Campaign file)",
            campaign_df.columns, key="campaign_price_col",
            format_func=make_col_formatter(campaign_df.columns),
        )

    c3, c4 = st.columns(2)
    with c3:
        content_sku_col = st.selectbox(
            "SKU column (in Content file)", content_df.columns, key="content_sku_col",
            format_func=make_col_formatter(content_df.columns),
        )
    with c4:
        content_article_col = st.selectbox(
            "Article Number column (in Content file)", content_df.columns, key="content_article_col",
            format_func=make_col_formatter(content_df.columns),
        )

    strip_color_suffix = st.checkbox(
        "Content file's Article Number is a color number like 783237_01 — "
        "match using only the part before the underscore",
        value=True,
        key="strip_color_suffix",
    )

    c5, c6, c7 = st.columns(3)
    with c5:
        tracker_article_col = st.selectbox(
            "Article Number column (in Zecom Tracker)", tracker_df.columns, key="tracker_article_col",
            format_func=make_col_formatter(tracker_df.columns),
        )
    with c6:
        rrp_col = st.selectbox(
            "RRP column (Zecom Tracker)", tracker_df.columns, key="rrp_col",
            format_func=make_col_formatter(tracker_df.columns),
        )
    with c7:
        srp_col = st.selectbox(
            "SRP column (Zecom Tracker)", tracker_df.columns, key="srp_col",
            format_func=make_col_formatter(tracker_df.columns),
        )

    if st.button("Update Campaign Prices", type="primary"):
        campaign_work = campaign_df.copy()

        def normalize_key(val):
            """Turn SKU/Article values into a comparable string.

            Handles the common Excel gotchas that break lookups:
            - numeric IDs read in as floats (1234 -> "1234.0")
            - long IDs read in as scientific notation (4.07E+12)
            - stray whitespace / non-breaking spaces
            """
            if pd.isna(val):
                return ""
            if isinstance(val, float):
                if val.is_integer():
                    return str(int(val))
                return repr(val)
            s = str(val).strip().replace("\xa0", "")
            if s == "":
                return ""
            try:
                f = float(s)
                if f.is_integer():
                    return str(int(f))
                return repr(f)
            except (ValueError, TypeError):
                return s

        def base_article_key(val):
            """Normalize an Article/color number, optionally dropping a _XX color suffix."""
            key = normalize_key(val)
            if strip_color_suffix and "_" in key:
                key = key.split("_")[0]
            return key

        # --- Step 1: SKU -> Article Number, using the Content file ---
        content_work = content_df[[content_sku_col, content_article_col]].copy()
        content_work.columns = ["_sku", "_article"]
        content_work["_sku_key"] = content_work["_sku"].apply(normalize_key)
        content_work["_article"] = content_work["_article"].apply(base_article_key)
        content_work = content_work.drop_duplicates(subset="_sku_key", keep="first")

        campaign_work["_sku_key"] = campaign_work[campaign_sku_col].apply(normalize_key)

        merged = campaign_work.merge(
            content_work[["_sku_key", "_article"]], on="_sku_key", how="left"
        )

        # --- Step 2: Article Number -> RRP / SRP, using the Zecom Tracker ---
        tracker_work = tracker_df[[tracker_article_col, rrp_col, srp_col]].copy()
        tracker_work.columns = ["_article_t", "_rrp", "_srp"]
        tracker_work["_article_t"] = tracker_work["_article_t"].apply(base_article_key)
        tracker_work = tracker_work.drop_duplicates(subset="_article_t", keep="first")

        merged = merged.merge(
            tracker_work, left_on="_article", right_on="_article_t", how="left"
        )

        # --- Diagnostics: help pinpoint why a lookup step isn't matching ---
        step1_unmatched = merged["_article"].isna().sum()
        step2_unmatched = (merged["_article"].notna() & merged["_article_t"].isna()).sum()
        with st.expander("Matching diagnostics (open if RRP/SRP still come back blank)"):
            st.write(
                f"SKU → Article Number: {len(merged) - step1_unmatched} matched, "
                f"{step1_unmatched} unmatched."
            )
            st.write(
                f"Article Number → RRP/SRP: {len(merged) - step1_unmatched - step2_unmatched} matched, "
                f"{step2_unmatched} unmatched (of rows that had an Article Number)."
            )
            if step2_unmatched > 0:
                sample_missing = (
                    merged.loc[merged["_article"].notna() & merged["_article_t"].isna(), "_article"]
                    .drop_duplicates()
                    .head(10)
                )
                st.write("Sample Article Numbers (from Content file) not found in Zecom Tracker:")
                st.write(list(sample_missing))
                st.write("Sample Article Numbers as they appear in Zecom Tracker:")
                st.write(list(tracker_work["_article_t"].drop_duplicates().head(10)))

        def is_missing_price(val):
            """A price counts as missing if it's blank/NaN OR equal to 0."""
            if pd.isna(val):
                return True
            s = str(val).strip()
            if s == "":
                return True
            try:
                return float(s) == 0
            except ValueError:
                return False

        def pick_price(row):
            srp = row["_srp"]
            rrp = row["_rrp"]
            if not is_missing_price(srp):
                return srp
            if not is_missing_price(rrp):
                return rrp
            return pd.NA

        merged[campaign_price_col] = merged.apply(pick_price, axis=1)

        srp_missing = merged["_srp"].apply(is_missing_price)
        rrp_missing = merged["_rrp"].apply(is_missing_price)

        no_article = merged["_article"].isna()
        no_price = rrp_missing & srp_missing & ~no_article
        unmatched = merged[no_article | no_price]

        matched_srp = (~srp_missing).sum()
        matched_rrp_fallback = (srp_missing & ~rrp_missing).sum()

        # --- Add Article Number / RRP / SRP as their own columns in the output ---
        # Pick names that won't collide with any column already in the Campaign file.
        existing_cols = set(campaign_df.columns)

        def unique_name(base):
            name = base
            i = 2
            while name in existing_cols:
                name = f"{base} ({i})"
                i += 1
            existing_cols.add(name)
            return name

        article_out_col = unique_name("Article Number")
        rrp_out_col = unique_name("RRP")
        srp_out_col = unique_name("SRP")

        rename_map = {"_article": article_out_col, "_rrp": rrp_out_col, "_srp": srp_out_col}
        merged = merged.rename(columns=rename_map)

        drop_cols = ["_sku_key", "_article_t"]
        result_df = merged.drop(columns=drop_cols)

        st.success(
            f"Updated {len(result_df)} rows — {matched_srp} from SRP, "
            f"{matched_rrp_fallback} fell back to RRP, {len(unmatched)} had no match "
            f"({int(no_article.sum())} with no Article Number found, "
            f"{int(no_price.sum())} with an Article Number but no RRP/SRP). "
            f"Added columns: '{article_out_col}', '{rrp_out_col}', '{srp_out_col}'."
        )

        st.subheader("Preview")
        st.dataframe(result_df.head(50), use_container_width=True)

        if len(unmatched) > 0:
            unmatched_display = unmatched.rename(columns=rename_map).drop(columns=drop_cols)
            st.subheader("Unmatched rows (no Article Number, or no RRP/SRP found)")
            st.dataframe(unmatched_display, use_container_width=True)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            result_df.to_excel(writer, sheet_name="Updated", index=False)
            if len(unmatched) > 0:
                unmatched.drop(columns=drop_cols).to_excel(
                    writer, sheet_name="Unmatched", index=False
                )
        buffer.seek(0)

        st.download_button(
            "Download updated file",
            data=buffer,
            file_name="Updated_Campaign_Prices.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
else:
    st.info("Upload the Campaign file, the Content file, and the Zecom Tracker to continue.")
