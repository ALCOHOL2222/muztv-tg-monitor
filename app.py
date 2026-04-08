
from pathlib import Path
import re
import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data.csv"


def strip_html(text: str) -> str:
    text = str(text or "")
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def cleanup_text(text: str) -> str:
    text = strip_html(text)
    for phrase in [
        "media is too big",
        "view in telegram",
        "open in web",
        "this media is not supported in your browser",
        "embed",
        "open in channel",
    ]:
        text = re.sub(re.escape(phrase), " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def norm(text: str) -> str:
    return cleanup_text(text).lower().replace("?", "?")


LAT_TO_CYR = str.maketrans({
    "a": "?", "b": "?", "c": "?", "e": "?", "h": "?", "k": "?",
    "m": "?", "o": "?", "p": "?", "t": "?", "x": "?", "y": "?",
})

CYR_TO_LAT = str.maketrans({
    "?": "a", "?": "b", "?": "c", "?": "e", "?": "h", "?": "k",
    "?": "m", "?": "o", "?": "p", "?": "t", "?": "x", "?": "y",
})


def generate_term_variants(term: str):
    base = norm(term).strip()
    variants = {base}
    variants.add(base.translate(LAT_TO_CYR))
    variants.add(base.translate(CYR_TO_LAT))
    return [v for v in variants if v]


def token_pattern(token: str) -> str:
    token = token.strip()
    if not token:
        return ""

    # short aliases like MOT / ??? -> exact word only
    if len(token) <= 3:
        return rf"\b{re.escape(token)}\b"

    # inflection-tolerant prefix for regular names
    stem_len = max(3, len(token) - 2)
    stem = token[:stem_len]
    return rf"\b{re.escape(stem)}[A-Za-z?-??-???0-9_-]*"


def build_term_regex(term: str):
    regexes = []

    for variant in generate_term_variants(term):
        tokens = re.findall(r"[0-9A-Za-z?-??-???]+", variant)
        if not tokens:
            continue

        parts = []
        for token in tokens:
            token = token.strip()
            if not token:
                continue

            # ???????? ?????: ?????? ?????? ?????
            if len(token) <= 3:
                parts.append(rf"{re.escape(token)}")
            else:
                # ??? ??????? ????/??????? ????? ??????????:
                # ????? -> ?????? / ???????
                # ???? -> ???? / ????
                stem_len = max(3, len(token) - 2)
                stem = token[:stem_len]
                parts.append(rf"{re.escape(stem)}[A-Za-z?-??-???-]*")

        if not parts:
            continue

        if len(parts) == 1:
            regexes.append(re.compile(parts[0], re.IGNORECASE))
        else:
            # ??? ???? ???? "???? ?????" ?????? ????? ?????? ???????????
            lookahead_pattern = "".join(f"(?=.*{part})" for part in parts) + ".*"
            regexes.append(re.compile(lookahead_pattern, re.IGNORECASE | re.DOTALL))

    return regexes


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

    visible_text = df["post_text"].copy()
    empty_mask = visible_text.str.strip().eq("")
    visible_text.loc[empty_mask] = df.loc[empty_mask, "raw_html"]
    visible_text = visible_text.map(cleanup_text)

    comments_text = df["processed_comments"].map(cleanup_text)

    df["visible_text"] = visible_text
    df["comments_text"] = comments_text
    df["text_preview"] = visible_text.str.slice(0, 300)

    return df


def save_main_editor_changes(edited_df: pd.DataFrame):
    full_df = pd.read_csv(DATA_PATH)

    if "post_url" not in full_df.columns:
        raise ValueError("No post_url column in data.csv")

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
st.caption("Web version based on Telegram MUZ-TV archive")

df = load_data()

if df.empty:
    st.warning("Archive file was not found or is empty.")
    st.stop()

min_date = None
max_date = None
if df["published_at_dt"].notna().any():
    min_date = df["published_at_dt"].min().date()
    max_date = df["published_at_dt"].max().date()

with st.sidebar:
    st.header("Search parameters")
    artist = st.text_input("Artist", "")
    aliases_raw = st.text_input("Aliases (comma separated)", "")

    if min_date and max_date:
        date_from = st.date_input("Date from", value=min_date)
        date_to = st.date_input("Date to", value=max_date)
    else:
        date_from = None
        date_to = None

aliases = [x.strip() for x in aliases_raw.split(",") if x.strip()]
search_terms = []
if artist.strip():
    search_terms.append(artist.strip())
search_terms.extend(aliases)

term_regexes = []
for term in search_terms:
    term_regexes.extend(build_term_regex(term))

filtered_df = df.copy()

if date_from is not None and "published_at_dt" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["published_at_dt"].dt.date >= date_from]

if date_to is not None and "published_at_dt" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["published_at_dt"].dt.date <= date_to]

if term_regexes:
    search_blob = (
        filtered_df["visible_text"].fillna("").astype(str)
        + " "
        + filtered_df["comments_text"].fillna("").astype(str)
    ).map(norm)

    mask = search_blob.apply(lambda x: any(r.search(x) for r in term_regexes))
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
m1.metric("Posts", posts_total)
m2.metric("Likes", likes_total)
m3.metric("Comments", comments_total)
m4.metric("Reposts", reposts_total)
m5.metric("Views", views_total)
m6.metric("ERV %", f"{erv_percent:.2f}")

st.caption(
    f"ERV = (likes {likes_total} + comments {comments_total} + reposts {reposts_total}) / views {views_total}"
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

if "published_at" in show_df.columns:
    try:
        show_df = show_df.sort_values("published_at", ascending=False)
    except Exception:
        pass

st.subheader("Found posts")

limit = min(len(show_df), 200)
if len(show_df) > 200:
    st.info("Only the first 200 rows of the current filter are shown in the editor to avoid memory issues.")

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
    if st.button("Save changes"):
        try:
            save_main_editor_changes(edited_show_df)
            st.success("Changes were saved to data.csv")
            st.rerun()
        except Exception as e:
            st.error("Save error: " + str(e))

csv_data = show_df.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    label="Download CSV",
    data=csv_data,
    file_name="tg_filtered_posts.csv",
    mime="text/csv",
)
