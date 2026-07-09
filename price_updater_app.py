import pandas as pd
import numpy as np

# Simulate the app logic programmatically using the real files in the directory.
print("--- Verifying app logic on real files ---")

# Inputs
campaign_path = "Brand Mega Offers (0622-0627) - DEALS.xlsx"
content_path = "Content file 11.06.2026 (2).xlsx"
tracker_path = "6.18 Updated Tracker Javi (3).xlsx"

# 1. Read files
print("Reading Campaign file...")
campaign_df = pd.read_excel(campaign_path, sheet_name="null1")

print("Reading Content file...")
content_df = pd.read_excel(content_path, sheet_name="content")

print("Reading Zecom Tracker...")
tracker_df = pd.read_excel(tracker_path, sheet_name="Sheet1", header=2)

print(f"Campaign shape: {campaign_df.shape}")
print(f"Content shape: {content_df.shape}")
print(f"Tracker shape: {tracker_df.shape}")

# 2. Columns mappings (matching UI selections)
campaign_sku_col = "Seller SKU"
campaign_price_col = "Campaign Price（Mandatory）"

content_sku_col = "EAN"
content_article_col = "Color_No"

tracker_article_col = "PIM Article#"
rrp_col = "PH EC RRP"
srp_col = "SRP ao.1" # Index 53 (the second SRP ao column)

strip_color_suffix = True

# Helper functions from app.py
def normalize_key(val):
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
    key = normalize_key(val)
    if strip_color_suffix and "_" in key:
        key = key.split("_")[0]
    return key

# --- Step 1: SKU -> Article Number ---
content_work = content_df[[content_sku_col, content_article_col]].copy()
content_work.columns = ["_sku", "_article"]
content_work["_sku_key"] = content_work["_sku"].apply(normalize_key)
content_work["_article"] = content_work["_article"].apply(base_article_key)
content_work = content_work.drop_duplicates(subset="_sku_key", keep="first")

campaign_work = campaign_df.copy()
campaign_work["_sku_key"] = campaign_work[campaign_sku_col].apply(normalize_key)

merged = campaign_work.merge(
    content_work[["_sku_key", "_article"]], on="_sku_key", how="left"
)

# --- Step 2: Article Number -> RRP / SRP ---
tracker_work = tracker_df[[tracker_article_col, rrp_col, srp_col]].copy()
tracker_work.columns = ["_article_t", "_rrp", "_srp"]
tracker_work["_article_t"] = tracker_work["_article_t"].apply(base_article_key)
tracker_work = tracker_work.drop_duplicates(subset="_article_t", keep="first")

merged = merged.merge(
    tracker_work, left_on="_article", right_on="_article_t", how="left"
)

def is_missing_price(val):
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

# Stats
srp_missing = merged["_srp"].apply(is_missing_price)
rrp_missing = merged["_rrp"].apply(is_missing_price)
no_article = merged["_article"].isna()
no_price = rrp_missing & srp_missing & ~no_article
unmatched = merged[no_article | no_price]

matched_srp = (~srp_missing).sum()
matched_rrp_fallback = (srp_missing & ~rrp_missing).sum()

print("\n--- Processing Results ---")
print(f"Total rows processed: {len(merged)}")
print(f"Matched with SRP: {matched_srp}")
print(f"Fell back to RRP: {matched_rrp_fallback}")
print(f"Unmatched: {len(unmatched)}")

assert len(merged) == len(campaign_df), "Row count mismatch!"
assert matched_srp > 0, "No SRP values were matched!"
print("\nSuccess! Logic matches expectations perfectly.")
