from pathlib import Path
import pandas as pd

COMMENTS_OVERRIDE_PATH = Path("output") / "comments_manual_overrides.csv"


def _safe_int_series(series):
    return pd.to_numeric(series, errors="coerce").fillna(0).astype(int)


def load_comment_overrides() -> pd.DataFrame:
    if COMMENTS_OVERRIDE_PATH.exists():
        try:
            df = pd.read_csv(COMMENTS_OVERRIDE_PATH)
            if "post_url" in df.columns and "comments_visible" in df.columns:
                df["post_url"] = df["post_url"].astype(str).str.strip()
                df["comments_visible"] = _safe_int_series(df["comments_visible"])
                df = df[["post_url", "comments_visible"]].drop_duplicates(subset=["post_url"], keep="last")
                return df
        except Exception:
            pass
    return pd.DataFrame(columns=["post_url", "comments_visible"])


def apply_comment_overrides(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    if "comments_visible" not in result.columns:
        result["comments_visible"] = 0

    if "post_url" not in result.columns:
        return result

    result["post_url"] = result["post_url"].astype(str).str.strip()
    result["comments_visible"] = _safe_int_series(result["comments_visible"])

    overrides = load_comment_overrides()
    if overrides.empty:
        return result

    merged = result.merge(
        overrides.rename(columns={"comments_visible": "comments_visible_override"}),
        on="post_url",
        how="left",
    )

    merged["comments_visible"] = merged["comments_visible_override"].fillna(merged["comments_visible"])
    merged["comments_visible"] = _safe_int_series(merged["comments_visible"])
    merged = merged.drop(columns=["comments_visible_override"])

    return merged


def save_comment_overrides_from_editor(edited_df: pd.DataFrame):
    if edited_df is None or edited_df.empty:
        return 0

    if "post_url" not in edited_df.columns or "comments_visible" not in edited_df.columns:
        return 0

    edited = edited_df.copy()
    edited["post_url"] = edited["post_url"].astype(str).str.strip()
    edited["comments_visible"] = _safe_int_series(edited["comments_visible"])
    edited = edited[["post_url", "comments_visible"]].drop_duplicates(subset=["post_url"], keep="last")

    existing = load_comment_overrides()

    if existing.empty:
        final_df = edited
    else:
        existing = existing[["post_url", "comments_visible"]].drop_duplicates(subset=["post_url"], keep="last")
        existing = existing.set_index("post_url")
        edited = edited.set_index("post_url")

        existing.update(edited)
        missing = edited.loc[~edited.index.isin(existing.index)]

        final_df = pd.concat([existing, missing]).reset_index()

    COMMENTS_OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(COMMENTS_OVERRIDE_PATH, index=False, encoding="utf-8-sig")

    return len(edited_df)
