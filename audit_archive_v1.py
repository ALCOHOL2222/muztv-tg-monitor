from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

candidates = [
    OUTPUT_DIR / "tg_muztv_archive_period_enriched_exact.xlsx",
    OUTPUT_DIR / "tg_muztv_archive_period_enriched_exact.csv",
    OUTPUT_DIR / "tg_muztv_archive_period_v2.xlsx",
    OUTPUT_DIR / "tg_muztv_archive_period_v2.csv",
]

archive_path = None
for p in candidates:
    if p.exists():
        archive_path = p
        break

if archive_path is None:
    raise FileNotFoundError("Не найден архив для аудита.")

if archive_path.suffix.lower() == ".xlsx":
    df = pd.read_excel(archive_path)
else:
    df = pd.read_csv(archive_path)

print(f"ARCHIVE_FILE: {archive_path}")
print(f"TOTAL_ROWS: {len(df)}")

if "post_url" in df.columns:
    print(f"UNIQUE_POST_URL: {df['post_url'].astype(str).nunique()}")
else:
    print("UNIQUE_POST_URL: NO_COLUMN")

if "post_id" in df.columns:
    print(f"UNIQUE_POST_ID: {df['post_id'].astype(str).nunique()}")
else:
    print("UNIQUE_POST_ID: NO_COLUMN")

if "published_at" in df.columns:
    dt = pd.to_datetime(df["published_at"], errors="coerce", utc=True)
    print(f"MIN_DATE: {dt.min()}")
    print(f"MAX_DATE: {dt.max()}")

    month_counts = (
        dt.dropna()
        .dt.to_period("M")
        .astype(str)
        .value_counts()
        .sort_index()
    )

    print("MONTH_COUNTS_START")
    for month, count in month_counts.items():
        print(f"{month}: {count}")
    print("MONTH_COUNTS_END")
else:
    print("MIN_DATE: NO_COLUMN")
    print("MAX_DATE: NO_COLUMN")
