
from pathlib import Path
import re
import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data.csv"


def norm(text) -> str:
    text = str(text or "").lower().replace("?", "?")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


LAT_TO_CYR = str.maketrans({
    "a": "?", "b": "?", "c": "?", "e": "?", "h": "?", "k": "?",
    "m": "?", "o": "?", "p": "?", "t": "?", "x": "?", "y": "?",
})

CYR_TO_LAT = str.maketrans({
    "?": "a", "?": "b", "?": "c", "?": "e", "?": "h", "?": "k",
    "?": "m", "?": "o", "?": "p", "?": "t", "?": "x", "?": "y",
})


def generate_term_variants(term: str):
    base = norm(term)
    variants = {base, base.translate(LAT_TO_CYR), base.translate(CYR_TO_LAT)}
    return [v for v in variants if v]


def build_exact_patterns(term: str):
    patterns = []
    for variant in generate_term_variants(term):
        escaped = re.escape(variant)
        patterns.append(
            re.compile(
                rf'(?<![0-9A-Za-z?-??-???_]){escaped}(?![0-9A-Za-z?-??-???_])',
                re.IGNORECASE,
            )
        )
    return patterns


@st.cache_data
def load_data():
    if not DATA_PATH.exists():
        return pd.DataFrame()

    df = pd.read_csv(DATA_PATH)

    defaults = {
        "post_url": "",
        "published_at": "",
        "post_text": "",
        "raw_html": "",
        "processed_comments": "",
    }
    for col, val in defaults.items():
        if col not in df.columns:
            df[col] = val

    numeric_cols = ["views", "likes_visible", "comments_visible", "reposts_visible"]
    for col in numeric_cols:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    try:
        df["published_at_dt"] = pd.to_datetime(df["published_at"], errors="coerce")
    except Exception:
        df["published_at_dt"] = pd.NaT

    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].fillna("").astype(str)

    df["post_url"] = df["post_url"].astype(str).str.strip()

    search_text = df["post_text"].astype(str).copy()
    empty_mask = search_text.str.strip().eq("")
    raw_html_as_text = df["raw_html"].astype(str)
    search_text.loc[empty_mask] = raw_html_as_text.loc[empty_mask]
    df["search_text"] = search_text

    return df


def save_main_editor_changes(edited_df: pd.DataFrame):
    full_df = pd.read_csv(DATA_PATH)

    if "post_url" not in full_df.columns:
        raise ValueError("? data.csv ??? ??????? post_url")

    full_df["post_url"] = full_df["post_url"].astype(str).str.strip()
    edited_df = edited_df.copy()
    edited_df["post_url"] = edited_df["post_url"].astype(str).str.strip()

    for _, row in edited_df.iterrows():
        mask = full_df["post_url"] == row["post_url"]
        if not mask.any():
            continue
        for col in edited_df.columns:
            if col in full_df.columns:
                full_df.loc[mask, col] = row[col]

    full_df.to_csv(DATA_PATH, index=False, encoding="utf-8-sig")
    load_data.clear()


st.set_page_config(page_title="MUZTV Telegram Monitor", layout="wide")

st.title("MUZTV Telegram Monitor")
st.caption("???-?????? ?? ?????? Telegram MUZ-TV")

df = load_data()

if df.empty:
    st.warning("????? Telegram ???? ?? ?????? ??? ????.")
    st.stop()

min_date = None
max_date = None
if df["published_at_dt"].notna().any():
    min_date = df["published_at_dt"].min().date()
    max_date = df["published_at_dt"].max().date()

with st.sidebar:
    st.header("????????? ??????")
    artist = st.text_input("??????", "")
    aliases_raw = st.text_input("?????? ????? ???????", "")

    if min_date and max_date:
        date_from = st.date_input("???? ?", value=min_date)
        date_to = st.date_input("???? ??", value=max_date)
    else:
        date_from = None
        date_to = None

aliases = [x.strip() for x in aliases_raw.split(",") if x.strip()]
search_terms = []
if artist.strip():
    search_terms.append(artist.strip())
search_terms.extend(aliases)

patterns = []
for term in search_terms:
    patterns.extend(build_exact_patterns(term))

filtered_df = df.copy()

if date_from is not None and "published_at_dt" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["published_at_dt"].dt.date >= date_from]

if date_to is not None and "published_at_dt" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["published_at_dt"].dt.date <= date_to]

if patterns:
    combined_text = (
        filtered_df["search_text"].fillna("").astype(str)
        + " "
        + filtered_df["processed_comments"].fillna("").astype(str)
        + " "
        + filtered_df["post_url"].fillna("").astype(str)
    ).map(norm)

    mask = pd.Series(False, index=filtered_df.index)
    for pattern in patterns:
        mask = mask | combined_text.str.contains(pattern, na=False)

    filtered_df = filtered_df[mask]

posts_total = int(len(filtered_df))
likes_total = int(filtered_df["likes_visible"].sum()) if "likes_visible" in filtered_df.columns else 0
comments_total = int(filtered_df["comments_visible"].sum()) if "comments_visible" in filtered_df.columns else 0
reposts_total = int(filtered_df["reposts_visible"].sum()) if "reposts_visible" in filtered_df.columns else 0
views_total = int(filtered_df["views"].sum()) if "views" in filtered_df.columns else 0

erv_percent = 0.0
if views_total > 0:
    erv_percent = round((likes_total + comments_total + reposts_total) / views_total * 100, 2)

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("?????", posts_total)
m2.metric("?????", likes_total)
m3.metric("???????????", comments_total)
m4.metric("???????", reposts_total)
m5.metric("?????????", views_total)
m6.metric("ERV %", f"{erv_percent:.2f}")

st.caption(
    f"ERV = (????? {likes_total} + ??????????? {comments_total} + ??????? {reposts_total}) / ????????? {views_total}"
)

show_cols = [
    c for c in [
        "published_at",
        "post_url",
        "views",
        "likes_visible",
        "comments_visible",
        "reposts_visible",
        "search_text",
    ]
    if c in filtered_df.columns
]

show_df = filtered_df[show_cols].copy()

if "search_text" in show_df.columns:
    show_df["search_text"] = show_df["search_text"].astype(str).str.replace(r"<[^>]+>", " ", regex=True)
    show_df["search_text"] = show_df["search_text"].str.replace(r"\s+", " ", regex=True).str.slice(0, 300)

if "published_at" in show_df.columns:
    try:
        show_df = show_df.sort_values("published_at", ascending=False)
    except Exception:
        pass

st.subheader("????????? ?????")

limit = min(len(show_df), 200)
if len(show_df) > 200:
    st.info("??? ?????????????? ???????? ?????? 200 ????? ???????? ???????, ????? ?????????? ?? ?????? ?? ??????.")

editor_df = show_df.head(limit).copy()

edited_show_df = st.data_editor(
    editor_df,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    key="main_editor_table",
)

c1, c2 = st.columns([1, 5])

with c1:
    if st.button("????????? ?????????"):
        try:
            save_main_editor_changes(edited_show_df)
            st.success("????????? ????????? ? data.csv")
            st.rerun()
        except Exception as e:
            st.error(f"?????? ??????????: {e}")

csv_data = show_df.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    label="??????? CSV",
    data=csv_data,
    file_name="tg_filtered_posts.csv",
    mime="text/csv",
)
