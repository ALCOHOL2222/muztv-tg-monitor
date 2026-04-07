import re
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower().replace("ё", "е")).strip()


def find_archive_file() -> Path:
    candidates = [
        OUTPUT_DIR / "tg_muztv_archive_period_v2.xlsx",
        OUTPUT_DIR / "tg_muztv_archive_period_v2.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("Не найден v2-архив. Сначала запусти collect_archive_v2.py.")


def load_archive(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".xlsx":
        return pd.read_excel(path)
    return pd.read_csv(path)
def main():
    archive_path = find_archive_file()
    print(f"Архив: {archive_path}")

    artist_name = input("Имя артиста: ").strip()
    aliases_raw = input("Алиасы через запятую: ").strip()

    aliases = [artist_name] + [x.strip() for x in aliases_raw.split(",") if x.strip()]
    aliases_norm = [norm(x) for x in aliases if x.strip()]

    df = load_archive(archive_path)

    required_columns = ["post_url", "published_at", "post_text", "views"]
    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        raise ValueError(f"В архиве не хватает колонок: {missing}")

    matches = []

    for _, row in df.iterrows():
        post_text = str(row.get("post_text", "") or "")
        haystack = norm(post_text)

        matched_alias = None
        for alias in aliases_norm:
            if alias and alias in haystack:
                matched_alias = alias
                break

        if not matched_alias:
            continue

        matches.append({
            "source": row.get("source", "telegram"),
            "channel_name": row.get("channel_name", "muztv"),
            "artist_name": artist_name,
            "matched_alias": matched_alias,
            "post_id": row.get("post_id", ""),
            "post_url": row.get("post_url", ""),
            "published_at": row.get("published_at", ""),
            "post_text": row.get("post_text", ""),
            "views": int(row.get("views", 0) or 0),
            "likes_visible": int(row.get("likes_visible", 0) or 0),
            "comments_visible": int(row.get("comments_visible", 0) or 0),
            "reposts_visible": int(row.get("reposts_visible", 0) or 0),
            "page_number": row.get("page_number", ""),
        })

    result_df = pd.DataFrame(matches)
    if result_df.empty:
        print("\nСовпадений не найдено.")
        result_df = pd.DataFrame(columns=[
            "source",
            "channel_name",
            "artist_name",
            "matched_alias",
            "post_id",
            "post_url",
            "published_at",
            "post_text",
            "views",
            "likes_visible",
            "comments_visible",
            "reposts_visible",
            "page_number",
        ])
    else:
        result_df = result_df.sort_values(by="published_at", ascending=False).reset_index(drop=True)
        print(f"\nНайдено совпадений: {len(result_df)}")

    out_csv = OUTPUT_DIR / "tg_artist_matches_v2.csv"
    out_xlsx = OUTPUT_DIR / "tg_artist_matches_v2.xlsx"

    result_df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    result_df.to_excel(out_xlsx, index=False)

    print("Файлы:")
    print(f" - {out_csv}")
    print(f" - {out_xlsx}")


if __name__ == "__main__":
    main()
