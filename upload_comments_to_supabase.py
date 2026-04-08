from pathlib import Path
import math
import tomllib
import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data.csv"
SECRETS_PATH = BASE_DIR / ".streamlit" / "secrets.toml"

if not DATA_PATH.exists():
    raise SystemExit("data.csv not found")

if not SECRETS_PATH.exists():
    raise SystemExit("secrets.toml not found")

with open(SECRETS_PATH, "rb") as f:
    secrets = tomllib.load(f)

SUPABASE_URL = str(secrets["SUPABASE_URL"]).rstrip("/")
SUPABASE_KEY = str(secrets["SUPABASE_SECRET_KEY"]).strip()

df = pd.read_csv(DATA_PATH)

if "post_url" not in df.columns or "comments_visible" not in df.columns:
    raise SystemExit("data.csv must contain post_url and comments_visible")

df["post_url"] = df["post_url"].fillna("").astype(str).str.strip()
df["comments_visible"] = pd.to_numeric(df["comments_visible"], errors="coerce").fillna(0).astype(int)

df = df[df["post_url"] != ""].copy()
df = df[["post_url", "comments_visible"]].drop_duplicates(subset=["post_url"], keep="last")

records = df.to_dict(orient="records")
if not records:
    raise SystemExit("No records to upload")

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=minimal",
}

url = f"{SUPABASE_URL}/rest/v1/comment_overrides?on_conflict=post_url"

chunk_size = 500
total = len(records)
sent = 0

for i in range(0, total, chunk_size):
    chunk = records[i:i + chunk_size]
    r = requests.post(url, headers=headers, json=chunk, timeout=60)
    if r.status_code >= 300:
        print(r.status_code, r.text[:1000])
        raise SystemExit("Upload failed")
    sent += len(chunk)
    print(f"uploaded {sent}/{total}")

print("SUPABASE_UPLOAD_OK")
