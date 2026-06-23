# Campaign Price Updater

Streamlit app that:
1. Takes a **SKU/campaign file** (has SKU, Article Number, and a Campaign
   Price column you want filled in) and a **Zecom Tracker** (has Article
   Number, RRP, and SRP).
2. Matches each SKU's Article Number against the Zecom Tracker.
3. Sets Campaign Price = SRP; if SRP is blank/missing, falls back to RRP.
4. Flags any rows where neither RRP nor SRP was found.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy
1. Push this folder to a GitHub repo.
2. On [share.streamlit.io](https://share.streamlit.io), create a new app
   pointing at the repo and `app.py`.

## How it works
- Both files can be `.xlsx` (any sheet, you pick which one) or `.csv`.
- After upload, you map which column is which (SKU, Article Number,
  Campaign Price in the SKU file; Article Number, RRP, SRP in the
  Zecom Tracker) — no hardcoded column names, so it works with whatever
  headers your real files use.
- Article numbers are compared as trimmed strings so type mismatches
  (e.g. `"1234"` vs `1234.0`) still match correctly.
- If the Zecom Tracker has duplicate Article Numbers, the first one is
  used.
- Output is an Excel file with an "Updated" sheet (your data with
  Campaign Price filled in) and, if any rows didn't match, an
  "Unmatched" sheet listing them for manual review.
