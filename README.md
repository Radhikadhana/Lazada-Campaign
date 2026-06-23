# Campaign Price Updater

Streamlit app that:
1. Takes three files:
   - **Campaign file** — has SKU and a Campaign Price column you want filled in.
   - **Content file** — has SKU and Article Number (maps each SKU to its Article Number).
   - **Zecom Tracker** — has Article Number, RRP, and SRP.
2. Looks up each SKU's Article Number using the Content file.
3. Uses that Article Number to look up RRP and SRP from the Zecom Tracker.
4. Sets Campaign Price = SRP; if SRP is blank/missing, falls back to RRP.
5. Flags any rows where the SKU had no Article Number in the Content file, or
   the Article Number had neither RRP nor SRP in the Tracker.

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
- All three files can be `.xlsx` (any sheet, you pick which one) or `.csv`.
- After upload, you map which column is which:
  - Campaign file: SKU column, Campaign Price column.
  - Content file: SKU column, Article Number column.
  - Zecom Tracker: Article Number column, RRP column, SRP column.
  - No hardcoded column names, so it works with whatever headers your real
    files use.
- SKUs and Article Numbers are compared as trimmed strings so type mismatches
  (e.g. `"1234"` vs `1234.0`) still match correctly.
- If the Content file has duplicate SKUs, or the Zecom Tracker has duplicate
  Article Numbers, the first occurrence is used.
- Output is an Excel file with an "Updated" sheet (your Campaign data with
  Campaign Price filled in) and, if any rows didn't match, an "Unmatched"
  sheet listing them for manual review — split into "no Article Number
  found" and "Article Number found but no RRP/SRP" so you know which file to
  go fix.
