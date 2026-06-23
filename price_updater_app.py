import io
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Campaign Price Updater", layout="wide")
st.title("Campaign Price Updater")
st.caption(
    "Looks up each SKU's Article Number, pulls RRP/SRP from the Zecom Tracker, "
    "and fills the campaign price column with SRP (falling back to RRP)."
)

col1, col2 = st.columns(2)
with col1:
    sku_file = st.file_uploader(
        "SKU / Campaign file (has SKU, Article Number, Campaign Price)",
        type=["xlsx", "csv"], key="sku_file",
    )
with col2:
    content_file = st.file_uploader(
        "Zecom Tracker (has Article Number, RRP, SRP)",
        type=["xlsx", "csv"], key="content_file",
    )


def read_any(uploaded_file, sheet_picker_key):
    """Read an uploaded csv/xlsx, letting the user pick a sheet for xlsx."""
    if uploaded_file.name.lower().endswith(".csv"):
        return pd.read_csv(uploaded_file)
    xls = pd.ExcelFile(uploaded_file)
    sheet = st.selectbox(
        f"Sheet for {uploaded_file.name}", xls.sheet_names, key=sheet_picker_key
    )
    return xls.parse(sheet)


sku_df = None
content_df = None

if sku_file is not None:
    st.subheader("SKU / Campaign file")
    sku_df = read_any(sku_file, "sku_sheet")
    st.dataframe(sku_df.head(5), use_container_width=True)

if content_file is not None:
    st.subheader("Zecom Tracker")
    content_df = read_any(content_file, "content_sheet")
    st.dataframe(content_df.head(5), use_container_width=True)

if sku_df is not None and content_df is not None:
    st.subheader("Map columns")

    c1, c2, c3 = st.columns(3)
    with c1:
        sku_col = st.selectbox("SKU column", sku_df.columns, key="sku_col")
    with c2:
        sku_article_col = st.selectbox(
            "Article Number column (in SKU file)", sku_df.columns, key="sku_article_col"
        )
    with c3:
        campaign_price_col = st.selectbox(
            "Campaign Price column to update (in SKU file)",
            sku_df.columns, key="campaign_price_col",
        )

    c4, c5, c6 = st.columns(3)
    with c4:
        content_article_col = st.selectbox(
            "Article Number column (in Zecom Tracker)", content_df.columns, key="content_article_col"
        )
    with c5:
        rrp_col = st.selectbox("RRP column (Zecom Tracker)", content_df.columns, key="rrp_col")
    with c6:
        srp_col = st.selectbox("SRP column (Zecom Tracker)", content_df.columns, key="srp_col")

    if st.button("Update Campaign Prices", type="primary"):
        sku_work = sku_df.copy()
        content_work = content_df[[content_article_col, rrp_col, srp_col]].copy()
        content_work.columns = ["_article", "_rrp", "_srp"]

        # Normalize article numbers as strings so int/float/text mismatches
        # between the two files (e.g. "1234" vs 1234.0) still match.
        sku_work["_article_key"] = sku_work[sku_article_col].astype(str).str.strip()
        content_work["_article_key"] = content_work["_article"].astype(str).str.strip()
        content_work = content_work.drop_duplicates(subset="_article_key", keep="first")

        merged = sku_work.merge(
            content_work[["_article_key", "_rrp", "_srp"]], on="_article_key", how="left"
        )

        def pick_price(row):
            srp = row["_srp"]
            rrp = row["_rrp"]
            if pd.notna(srp) and str(srp).strip() != "":
                return srp
            if pd.notna(rrp) and str(rrp).strip() != "":
                return rrp
            return pd.NA

        merged[campaign_price_col] = merged.apply(pick_price, axis=1)

        unmatched = merged[merged["_rrp"].isna() & merged["_srp"].isna()]
        matched_srp = merged["_srp"].notna().sum()
        matched_rrp_fallback = ((merged["_srp"].isna()) & (merged["_rrp"].notna())).sum()

        result_df = merged.drop(columns=["_article_key", "_rrp", "_srp"])

        st.success(
            f"Updated {len(result_df)} rows — {matched_srp} from SRP, "
            f"{matched_rrp_fallback} fell back to RRP, {len(unmatched)} had no match."
        )

        st.subheader("Preview")
        st.dataframe(result_df.head(50), use_container_width=True)

        if len(unmatched) > 0:
            st.subheader("Unmatched rows (no RRP or SRP found)")
            st.dataframe(unmatched.drop(columns=["_article_key", "_rrp", "_srp"]), use_container_width=True)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            result_df.to_excel(writer, sheet_name="Updated", index=False)
            if len(unmatched) > 0:
                unmatched.drop(columns=["_article_key", "_rrp", "_srp"]).to_excel(
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
    st.info("Upload both files to continue.")
