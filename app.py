from comments_manual import apply_comment_overrides, save_comment_overrides_from_editor
from pathlib import Path
import re

import pandas as pd
# COMMENTS_OVERRIDE_MONKEYPATCH
_original_read_excel = pd.read_excel
_original_read_csv = pd.read_csv

def _needs_comment_override(path_like):
    try:
        s = str(path_like).lower()
    except Exception:
        return False
    return "tg_muztv_archive_period" in s and ("xlsx" in s or "csv" in s)

def _read_excel_with_comment_overrides(*args, **kwargs):
    df = _original_read_excel(*args, **kwargs)
    src = args[0] if args else kwargs.get("io")
    if _needs_comment_override(src) and isinstance(df, pd.DataFrame) and "post_url" in df.columns:
        df = apply_comment_overrides(df)
    return df

def _read_csv_with_comment_overrides(*args, **kwargs):
    df = _original_read_csv(*args, **kwargs)
    src = args[0] if args else kwargs.get("filepath_or_buffer")
    if _needs_comment_override(src) and isinstance(df, pd.DataFrame) and "post_url" in df.columns:
        df = apply_comment_overrides(df)
    return df

pd.read_excel = _read_excel_with_comment_overrides
pd.read_csv = _read_csv_with_comment_overrides

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower().replace("ё", "е")).strip()


def split_tokens(text: str):
    raw = norm(text)
    parts = re.split(r"[^a-zа-я0-9]+", raw)
    return [p for p in parts if len(p) >= 4]


@st.cache_data
def load_archive():
    xlsx_path = OUTPUT_DIR / "tg_muztv_archive_period_enriched_exact_comments_loggedin_v2.xlsx"
    csv_path = OUTPUT_DIR / "tg_muztv_archive_period_enriched_exact_comments_loggedin_v2.csv"

    if xlsx_path.exists():
        return pd.read_excel(xlsx_path)
    if csv_path.exists():
        return pd.read_csv(csv_path)

    return pd.DataFrame(columns=[
        "source",
        "channel_name",
        "post_id",
        "post_url",
        "published_at",
        "post_text",
        "views",
        "likes_visible",
        "comments_visible",
        "reposts_visible",
        "page_number",
        "raw_html",
    ])


def calc_erv(likes, comments, reposts, views):
    if not views:
        return 0.0
    return round(((likes + comments + reposts) / views) * 100, 2)


st.set_page_config(
    page_title="MUZTV Telegram Monitor",
    page_icon="📊",
    layout="wide",
)

st.title("MUZTV Telegram Monitor")
st.caption("Локальная веб-версия по архиву Telegram MUZ-TV")
df = load_archive()

if df.empty:
    st.warning("Архив Telegram пока не найден или пуст.")
    st.stop()

for col in ["views", "likes_visible", "comments_visible", "reposts_visible"]:
    if col not in df.columns:
        df[col] = 0
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

if "published_at" in df.columns:
    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")

min_date = df["published_at"].dropna().min()
max_date = df["published_at"].dropna().max()

with st.sidebar:
    st.header("Параметры поиска")
    artist_name = st.text_input("Артист", "")
    aliases_raw = st.text_input("Алиасы через запятую", "")
    date_from = st.date_input("Дата с", value=min_date.date() if pd.notna(min_date) else None)
    date_to = st.date_input("Дата по", value=max_date.date() if pd.notna(max_date) else None)

filtered = df.copy()

if artist_name.strip():
    aliases = [artist_name] + [x.strip() for x in aliases_raw.split(",") if x.strip()]
    aliases_norm = [norm(x) for x in aliases if x.strip()]

    token_set = set()
    for alias in aliases:
        for token in split_tokens(alias):
            token_set.add(token)

    keep_mask = []

    for _, row in filtered.iterrows():
        post_text = str(row.get("post_text", "") or "")
        raw_html = str(row.get("raw_html", "") or "")
        haystack = norm(post_text + " " + raw_html)

        matched = False

        for alias in aliases_norm:
            if alias and alias in haystack:
                matched = True
                break

        if not matched:
            for token in token_set:
                if token and token in haystack:
                    matched = True
                    break

        keep_mask.append(matched)

    filtered = filtered[keep_mask].copy()

if "published_at" in filtered.columns:
    filtered = filtered[
        (filtered["published_at"].dt.date >= date_from) &
        (filtered["published_at"].dt.date <= date_to)
    ].copy()

filtered = filtered.sort_values(by="published_at", ascending=False).reset_index(drop=True)

posts_count = len(filtered)
likes_total = int(filtered["likes_visible"].sum())
comments_total = int(filtered["comments_visible"].sum())
reposts_total = int(filtered["reposts_visible"].sum())
views_total = int(filtered["views"].sum())
erv_total = calc_erv(likes_total, comments_total, reposts_total, views_total)
c1, c2, c3, c4, c5, c6 = st.columns(6)

c1.metric("Посты", len(filtered))
c2.metric("Лайки", int(filtered["likes_visible"].sum()))
c3.metric("Комментарии", int(filtered["comments_visible"].sum()))
c4.metric("Репосты", int(filtered["reposts_visible"].sum()))
c5.metric("Просмотры", int(filtered["views"].sum()))
c6.metric(
    "ERV %",
    f'{calc_erv(int(filtered["likes_visible"].sum()), int(filtered["comments_visible"].sum()), int(filtered["reposts_visible"].sum()), int(filtered["views"].sum())):.2f}'
)

st.caption(f'ERV = (лайки {int(filtered["likes_visible"].sum())} + комментарии {int(filtered["comments_visible"].sum())} + репосты {int(filtered["reposts_visible"].sum())}) / просмотры {int(filtered["views"].sum())}')
st.divider()

show_df = filtered.copy()

if "published_at" in show_df.columns:
    show_df["published_at"] = show_df["published_at"].dt.strftime("%Y-%m-%d %H:%M:%S")

desired_columns = [
    "published_at",
    "post_url",
    "views",
    "likes_visible",
    "comments_visible",
    "reposts_visible",
    "post_text",
]

existing_columns = [c for c in desired_columns if c in show_df.columns]
show_df = show_df[existing_columns]

st.subheader("Найденные посты")
st.dataframe(show_df, use_container_width=True)

csv_data = show_df.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    label="Скачать CSV",
    data=csv_data,
    file_name="tg_filtered_posts.csv",
    mime="text/csv",
)




