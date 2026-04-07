
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
    variants = {base}
    variants.add(base.translate(LAT_TO_CYR))
    variants.add(base.translate(CYR_TO_LAT))
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
        "source": "",
        "channel_name": "",
        "post_id": "",
        "post_url": "",
        "published_at": "",
        "post_text": "",
        "raw_html": "",
        "processed_comments": "",
        "views": 0,
        "likes_visible": 0,
        "comments_visible": 0,
        "reposts_visible": 0,
    }

    for col, val in defaults.items():
        if col not in df.columns:
            df[col] = val

    for col in ["views", "likes_visible", "comments_visible", "reposts_visible"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    for col in ["source", "channel_name", "post_id", "post_url", "published_at", "post_text", "raw_html", "processed_comments"]:
        df[col] = df[col].fillna("").astype(str)

    try:
        df["published_at_dt"] = pd.to_datetime(df["published_at"], errors="coerce")
    except Exception:
        df["published_at_dt"] = pd.NaT

    df["post_url"] = df["post_url"].str.strip()

    preview = df["post_text"].copy()
    empty_mask = preview.str.strip().eq("")
    preview.loc[empty_mask] = df.loc[empty_mask, "raw_html"]
    preview = preview.astype(str).str.replace(r"<[^>]+>", " ", regex=True)
    preview = preview.str.replace(r"\s+", " ", regex=True).str.strip()
    df["text_preview"] = preview

    return df


def save_main_editor_changes(edited_df: pd.DataFrame):
    full_df = pd.read_csv(DATA_PATH)

    if "post_url" not in full_df.columns:
        raise ValueError("? data.csv ??? ??????? post_url")

    full_df["post_url"] = full_df["post_url"].fillna("").astype(str).str.strip()
    edited_df = edited_df.copy()
    edited_df["post_url"] = edited_df["post_url"].fillna("").astype(str).str.strip()

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
st.caption("\u0412\u0435\u0431-\u0432\u0435\u0440\u0441\u0438\u044f \u043f\u043e \u0430\u0440\u0445\u0438\u0432\u0443 Telegram MUZ-TV")

df = load_data()

if df.empty:
    st.warning("\u0410\u0440\u0445\u0438\u0432 Telegram \u043f\u043e\u043a\u0430 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d \u0438\u043b\u0438 \u043f\u0443\u0441\u0442.")
    st.stop()

min_date = None
max_date = None
if df["published_at_dt"].notna().any():
    min_date = df["published_at_dt"].min().date()
    max_date = df["published_at_dt"].max().date()

with st.sidebar:
    st.header("\u041f\u0430\u0440\u0430\u043c\u0435\u0442\u0440\u044b \u043f\u043e\u0438\u0441\u043a\u0430")
    artist = st.text_input("\u0410\u0440\u0442\u0438\u0441\u0442", "")
    aliases_raw = st.text_input("\u0410\u043b\u0438\u0430\u0441\u044b \u0447\u0435\u0440\u0435\u0437 \u0437\u0430\u043f\u044f\u0442\u0443\u044e", "")

    if min_date and max_date:
        date_from = st.date_input("\u0414\u0430\u0442\u0430 \u0441", value=min_date)
        date_to = st.date_input("\u0414\u0430\u0442\u0430 \u043f\u043e", value=max_date)
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
        filtered_df["post_text"].fillna("").astype(str)
        + " "
        + filtered_df["raw_html"].fillna("").astype(str)
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
likes_total = int(filtered_df["likes_visible"].sum())
comments_total = int(filtered_df["comments_visible"].sum())
reposts_total = int(filtered_df["reposts_visible"].sum())
views_total = int(filtered_df["views"].sum())

erv_percent = 0.0
if views_total > 0:
    erv_percent = round((likes_total + comments_total + reposts_total) / views_total * 100, 2)

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("\u041f\u043e\u0441\u0442\u044b", posts_total)
m2.metric("\u041b\u0430\u0439\u043a\u0438", likes_total)
m3.metric("\u041a\u043e\u043c\u043c\u0435\u043d\u0442\u0430\u0440\u0438\u0438", comments_total)
m4.metric("\u0420\u0435\u043f\u043e\u0441\u0442\u044b", reposts_total)
m5.metric("\u041f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u044b", views_total)
m6.metric("ERV %", f"{erv_percent:.2f}")

st.caption(
    f"ERV = (\u043b\u0430\u0439\u043a\u0438 {likes_total} + \u043a\u043e\u043c\u043c\u0435\u043d\u0442\u0430\u0440\u0438\u0438 {comments_total} + \u0440\u0435\u043f\u043e\u0441\u0442\u044b {reposts_total}) / \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u044b {views_total}"
)

show_cols = [
    c for c in [
        "published_at",
        "post_url",
        "views",
        "likes_visible",
        "comments_visible",
        "reposts_visible",
        "text_preview",
    ]
    if c in filtered_df.columns
]

show_df = filtered_df[show_cols].copy()

if "text_preview" in show_df.columns:
    show_df["text_preview"] = show_df["text_preview"].astype(str).str.slice(0, 300)

if "published_at" in show_df.columns:
    try:
        show_df = show_df.sort_values("published_at", ascending=False)
    except Exception:
        pass

st.subheader("\u041d\u0430\u0439\u0434\u0435\u043d\u043d\u044b\u0435 \u043f\u043e\u0441\u0442\u044b")

limit = min(len(show_df), 200)
if len(show_df) > 200:
    st.info("\u0414\u043b\u044f \u0440\u0435\u0434\u0430\u043a\u0442\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u044f \u043f\u043e\u043a\u0430\u0437\u0430\u043d\u044b \u043f\u0435\u0440\u0432\u044b\u0435 200 \u0441\u0442\u0440\u043e\u043a \u0442\u0435\u043a\u0443\u0449\u0435\u0433\u043e \u0444\u0438\u043b\u044c\u0442\u0440\u0430, \u0447\u0442\u043e\u0431\u044b \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0435 \u043d\u0435 \u043f\u0430\u0434\u0430\u043b\u043e \u043f\u043e \u043f\u0430\u043c\u044f\u0442\u0438.")

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
    if st.button("\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c \u0438\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u044f"):
        try:
            save_main_editor_changes(edited_show_df)
            st.success("\u0418\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u044f \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u044b \u0432 data.csv")
            st.rerun()
        except Exception as e:
            st.error(f"\u041e\u0448\u0438\u0431\u043a\u0430 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0438\u044f: {e}")

csv_data = show_df.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    label="\u0421\u043a\u0430\u0447\u0430\u0442\u044c CSV",
    data=csv_data,
    file_name="tg_filtered_posts.csv",
    mime="text/csv",
)
