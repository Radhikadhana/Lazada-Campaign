import io
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Campaign Price Updater", layout="wide")
st.title("Campaign Price Updater")
st.caption(
    "Looks up each SKU's Article Number from the Content file, pulls RRP/SRP "
    "for that Article Number from the Zecom Tracker, and fills the campaign "
    "price column with SRP (falling back to RRP)."
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
            "SKU column (in Campaign file)", campaign_df.columns, key="campaign_sku_col"
        )
    with c2:
        campaign_price_col = st.selectbox(
            "Campaign Price column to update (in Campaign file)",
            campaign_df.columns, key="campaign_price_col",
        )

    c3, c4 = st.columns(2)
    with c3:
        content_sku_col = st.selectbox(
            "SKU column (in Content file)", content_df.columns, key="content_sku_col"
        )
    with c4:
        content_article_col = st.selectbox(
            "Article Number column (in Content file)", content_df.columns, key="content_article_col"
        )

    c5, c6, c7 = st.columns(3)
    with c5:
        tracker_article_col = st.selectbox(
            "Article Number column (in Zecom Tracker)", tracker_df.columns, key="tracker_article_col"
        )
    with c6:
        rrp_col = st.selectbox("RRP column (Zecom Tracker)", tracker_df.columns, key="rrp_col")
    with c7:
        srp_col = st.selectbox("SRP column (Zecom Tracker)", tracker_df.columns, key="srp_col")

    if st.button("Update Campaign Prices", type="primary"):
        campaign_work = campaign_df.copy()

        # --- Step 1: SKU -> Article Number, using the Content file ---
        content_work = content_df[[content_sku_col, content_article_col]].copy()
        content_work.columns = ["_sku", "_article"]
        content_work["_sku_key"] = content_work["_sku"].astype(str).str.strip()
        content_work["_article"] = content_work["_article"].astype(str).str.strip()
        content_work = content_work.drop_duplicates(subset="_sku_key", keep="first")

        campaign_work["_sku_key"] = campaign_work[campaign_sku_col].astype(str).str.strip()

        merged = campaign_work.merge(
            content_work[["_sku_key", "_article"]], on="_sku_key", how="left"
        )

        # --- Step 2: Article Number -> RRP / SRP, using the Zecom Tracker ---
        tracker_work = tracker_df[[tracker_article_col, rrp_col, srp_col]].copy()
        tracker_work.columns = ["_article_t", "_rrp", "_srp"]
        tracker_work["_article_t"] = tracker_work["_article_t"].astype(str).str.strip()
        tracker_work = tracker_work.drop_duplicates(subset="_article_t", keep="first")

        merged = merged.merge(
            tracker_work, left_on="_article", right_on="_article_t", how="left"
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

        no_article = merged["_article"].isna()
        no_price = merged["_rrp"].isna() & merged["_srp"].isna() & ~no_article
        unmatched = merged[no_article | no_price]

        matched_srp = merged["_srp"].notna().sum()
        matched_rrp_fallback = ((merged["_srp"].isna()) & (merged["_rrp"].notna())).sum()

        drop_cols = ["_sku_key", "_article", "_article_t", "_rrp", "_srp"]
        result_df = merged.drop(columns=drop_cols)

        st.success(
            f"Updated {len(result_df)} rows — {matched_srp} from SRP, "
            f"{matched_rrp_fallback} fell back to RRP, {len(unmatched)} had no match "
            f"({int(no_article.sum())} with no Article Number found, "
            f"{int(no_price.sum())} with an Article Number but no RRP/SRP)."
        )

        st.subheader("Preview")
        st.dataframe(result_df.head(50), use_container_width=True)

        if len(unmatched) > 0:
            st.subheader("Unmatched rows (no Article Number, or no RRP/SRP found)")
            st.dataframe(unmatched.drop(columns=drop_cols), use_container_width=True)

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
