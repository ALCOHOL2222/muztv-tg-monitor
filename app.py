from pathlib import Path
import re
import pandas as pd
import requests
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
    return cleanup_text(text).lower().replace("ё", "е")


def generate_term_variants(term: str):
    base = norm(term).strip()
    if not base:
        return []
    return [base]


def token_pattern(token: str) -> str:
    token = token.strip().lower().replace("ё", "е")
    if not token:
        return ""

    if len(token) <= 3:
        return rf"(?<![\u0400-\u04FFA-Za-z0-9_]){re.escape(token)}(?![\u0400-\u04FFA-Za-z0-9_])"

    stem_len = max(3, len(token) - 2)
    stem = token[:stem_len]
    return rf"(?<![\u0400-\u04FFA-Za-z0-9_]){re.escape(stem)}[\u0400-\u04FFA-Za-z-]*(?![\u0400-\u04FFA-Za-z0-9_])"


def build_term_regex(term: str):
    regexes = []
    for variant in generate_term_variants(term):
        tokens = re.findall(r"[\u0400-\u04FFA-Za-z0-9-]+", variant)
        if not tokens:
            continue

        parts = []
        for token in tokens:
            part = token_pattern(token)
            if part:
                parts.append(part)

        if not parts:
            continue

        if len(parts) == 1:
            regexes.append(re.compile(parts[0], re.IGNORECASE))
        else:
            pattern = "".join(f"(?=.*{part})" for part in parts) + ".*"
            regexes.append(re.compile(pattern, re.IGNORECASE | re.DOTALL))

    return regexes


def calc_row_erv(df: pd.DataFrame) -> pd.Series:
    views = pd.to_numeric(df["views"], errors="coerce").fillna(0)
    likes = pd.to_numeric(df["likes_visible"], errors="coerce").fillna(0)
    comments = pd.to_numeric(df["comments_visible"], errors="coerce").fillna(0)
    reposts = pd.to_numeric(df["reposts_visible"], errors="coerce").fillna(0)

    result = pd.Series(0.0, index=df.index)
    nonzero = views > 0
    result.loc[nonzero] = ((likes.loc[nonzero] + comments.loc[nonzero] + reposts.loc[nonzero]) / views.loc[nonzero] * 100).round(4)
    return result


def get_supabase_config():
    try:
        url = str(st.secrets["SUPABASE_URL"]).rstrip("/")
        key = str(st.secrets["SUPABASE_SECRET_KEY"]).strip()
        if url and key:
            return url, key
    except Exception:
        return None, None
    return None, None


@st.cache_data(ttl=60)
def fetch_comment_overrides():
    supabase_url, supabase_key = get_supabase_config()
    if not supabase_url or not supabase_key:
        return pd.DataFrame(columns=["post_url", "comments_visible"])

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }

    all_rows = []
    offset = 0
    limit = 1000

    while True:
        url = f"{supabase_url}/rest/v1/comment_overrides?select=post_url,comments_visible&limit={limit}&offset={offset}"
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code >= 300:
            raise RuntimeError(f"Supabase read error: {r.status_code} {r.text[:300]}")
        rows = r.json()
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < limit:
            break
        offset += limit

    if not all_rows:
        return pd.DataFrame(columns=["post_url", "comments_visible"])

    df = pd.DataFrame(all_rows)
    df["post_url"] = df["post_url"].fillna("").astype(str).str.strip()
    df["comments_visible"] = pd.to_numeric(df["comments_visible"], errors="coerce").fillna(0).astype(int)
    return df[["post_url", "comments_visible"]].drop_duplicates(subset=["post_url"], keep="last")


def upsert_comment_overrides(edited_df: pd.DataFrame):
    supabase_url, supabase_key = get_supabase_config()
    if not supabase_url or not supabase_key:
        raise RuntimeError("Supabase secrets are missing")

    payload = edited_df[["post_url", "comments_visible"]].copy()
    payload["post_url"] = payload["post_url"].fillna("").astype(str).str.strip()
    payload["comments_visible"] = pd.to_numeric(payload["comments_visible"], errors="coerce").fillna(0).astype(int)
    payload = payload[payload["post_url"] != ""]
    payload = payload.drop_duplicates(subset=["post_url"], keep="last")

    records = payload.to_dict(orient="records")
    if not records:
        return

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }

    url = f"{supabase_url}/rest/v1/comment_overrides?on_conflict=post_url"
    chunk_size = 500

    for i in range(0, len(records), chunk_size):
        chunk = records[i:i + chunk_size]
        r = requests.post(url, headers=headers, json=chunk, timeout=60)
        if r.status_code >= 300:
            raise RuntimeError(f"Supabase save error: {r.status_code} {r.text[:300]}")

    fetch_comment_overrides.clear()
    load_data.clear()


@st.cache_data(ttl=60)
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
        "views": 0,
        "likes_visible": 0,
        "comments_visible": 0,
        "reposts_visible": 0,
    }

    for col, val in defaults.items():
        if col not in df.columns:
            df[col] = val

    for col in ["views", "likes_visible", "comments_visible", "reposts_visible"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    for col in ["source", "channel_name", "post_id", "post_url", "published_at", "post_text", "raw_html"]:
        df[col] = df[col].fillna("").astype(str)

    df["post_url"] = df["post_url"].str.strip()

    try:
        df["published_at_dt"] = pd.to_datetime(df["published_at"], errors="coerce")
    except Exception:
        df["published_at_dt"] = pd.NaT

    visible_text = df["post_text"].copy()
    empty_mask = visible_text.str.strip().eq("")
    visible_text.loc[empty_mask] = df.loc[empty_mask, "raw_html"]
    visible_text = visible_text.map(cleanup_text)

    df["visible_text"] = visible_text
    df["text_preview"] = visible_text.str.slice(0, 300)

    overrides = fetch_comment_overrides()
    if not overrides.empty:
        df = df.merge(overrides, on="post_url", how="left", suffixes=("", "_override"))
        df["comments_visible"] = df["comments_visible_override"].fillna(df["comments_visible"]).astype(int)
        df = df.drop(columns=["comments_visible_override"], errors="ignore")

    df["erv_percent"] = calc_row_erv(df)
    return df


st.set_page_config(page_title="MUZTV Telegram Monitor", layout="wide")

st.title("MUZTV Telegram Monitor")
st.caption("Cloud comments source: Supabase")

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

    sort_by = st.selectbox(
        "Sort by",
        ["Date desc", "Comments desc", "ERV desc", "Views desc", "Likes desc", "Reposts desc"],
        index=0,
    )

    row_limit = st.selectbox("Rows in editor", ["200", "500", "1000", "All"], index=0)

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
        filtered_df[["visible_text", "post_url"]]
        .fillna("")
        .astype(str)
        .agg(" ".join, axis=1)
        .map(norm)
    )
    mask = search_blob.apply(lambda x: any(r.search(x) for r in term_regexes))
    filtered_df = filtered_df[mask]

filtered_df = filtered_df.copy()
filtered_df["erv_percent"] = calc_row_erv(filtered_df)

posts_total = int(len(filtered_df))
likes_total = int(filtered_df["likes_visible"].sum())
comments_total = int(filtered_df["comments_visible"].sum())
reposts_total = int(filtered_df["reposts_visible"].sum())
views_total = int(filtered_df["views"].sum())

erv_percent = 0.0
if views_total > 0:
    erv_percent = round((likes_total + comments_total + reposts_total) / views_total * 100, 4)

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Posts", posts_total)
m2.metric("Likes", likes_total)
m3.metric("Comments", comments_total)
m4.metric("Reposts", reposts_total)
m5.metric("Views", views_total)
m6.metric("ERV %", f"{erv_percent:.4f}")

st.caption(f"ERV = (likes {likes_total} + comments {comments_total} + reposts {reposts_total}) / views {views_total}")

show_cols = [
    c for c in [
        "published_at",
        "post_url",
        "views",
        "likes_visible",
        "comments_visible",
        "reposts_visible",
        "erv_percent",
        "text_preview",
    ]
    if c in filtered_df.columns
]

show_df = filtered_df[show_cols].copy()

if sort_by == "Date desc" and "published_at" in show_df.columns:
    show_df = show_df.sort_values("published_at", ascending=False)
elif sort_by == "Comments desc":
    show_df = show_df.sort_values(["comments_visible", "published_at"], ascending=[False, False])
elif sort_by == "ERV desc":
    show_df = show_df.sort_values(["erv_percent", "published_at"], ascending=[False, False])
elif sort_by == "Views desc":
    show_df = show_df.sort_values(["views", "published_at"], ascending=[False, False])
elif sort_by == "Likes desc":
    show_df = show_df.sort_values(["likes_visible", "published_at"], ascending=[False, False])
elif sort_by == "Reposts desc":
    show_df = show_df.sort_values(["reposts_visible", "published_at"], ascending=[False, False])

st.subheader("Found posts")

if row_limit == "All":
    limit = len(show_df)
else:
    limit = min(len(show_df), int(row_limit))

editor_df = show_df.head(limit).copy()
disabled_cols = [c for c in editor_df.columns if c != "comments_visible"]

edited_show_df = st.data_editor(
    editor_df,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    disabled=disabled_cols,
    column_config={
        "post_url": st.column_config.LinkColumn("post_url"),
        "comments_visible": st.column_config.NumberColumn("comments_visible", min_value=0, step=1),
        "erv_percent": st.column_config.NumberColumn("erv_percent", format="%.4f"),
    },
    key="main_editor_table",
)

if st.button("Save comments to cloud"):
    try:
        upsert_comment_overrides(edited_show_df)
        st.success("Comments saved to Supabase")
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
