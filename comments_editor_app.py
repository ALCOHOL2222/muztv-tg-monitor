from pathlib import Path
import pandas as pd
import streamlit as st

from comments_manual import apply_comment_overrides, save_comment_overrides_from_editor


st.set_page_config(page_title="MUZTV Comments Editor", layout="wide")


def find_archive_file() -> Path:
    candidates = [
        Path("output") / "tg_muztv_archive_period_enriched_exact_comments_loggedin_v2.xlsx",
        Path("output") / "tg_muztv_archive_period_enriched_exact_comments_loggedin_v2.csv",
        Path("output") / "tg_muztv_archive_period_enriched_exact.xlsx",
        Path("output") / "tg_muztv_archive_period_enriched_exact.csv",
        Path("output") / "tg_muztv_archive_period_enriched.xlsx",
        Path("output") / "tg_muztv_archive_period_enriched.csv",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError("Не найден архив с Telegram-постами в папке output")


@st.cache_data
def load_base_archive(path_str: str) -> pd.DataFrame:
    path = Path(path_str)
    if path.suffix.lower() == ".xlsx":
        return pd.read_excel(path)
    return pd.read_csv(path)


st.title("Ручная правка комментариев")

archive_path = find_archive_file()
st.caption(f"Архив: {archive_path}")

base_df = load_base_archive(str(archive_path)).copy()
base_df = apply_comment_overrides(base_df)

if "comments_visible" not in base_df.columns:
    base_df["comments_visible"] = 0

if "published_at" in base_df.columns:
    try:
        base_df["published_at"] = pd.to_datetime(base_df["published_at"], errors="coerce")
        base_df = base_df.sort_values("published_at", ascending=False)
    except Exception:
        pass

search_text = st.text_input("Фильтр по ссылке или тексту поста", "")

work_df = base_df.copy()

if search_text.strip():
    q = search_text.strip().lower()

    def row_match(row):
        post_url = str(row.get("post_url", "")).lower()
        post_text = str(row.get("post_text", "")).lower()
        return q in post_url or q in post_text

    work_df = work_df[work_df.apply(row_match, axis=1)]

show_cols = [
    c for c in [
        "published_at",
        "post_url",
        "comments_visible",
        "views",
        "likes_visible",
        "reposts_visible",
        "post_text",
    ]
    if c in work_df.columns
]

editor_df = work_df[show_cols].copy()

disabled_cols = [c for c in editor_df.columns if c != "comments_visible"]

edited_df = st.data_editor(
    editor_df,
    use_container_width=True,
    disabled=disabled_cols,
    hide_index=False,
    column_config={
        "post_url": st.column_config.LinkColumn("post_url"),
        "comments_visible": st.column_config.NumberColumn(
            "comments_visible",
            min_value=0,
            step=1,
            help="Можно менять вручную",
        ),
    },
    key="comments_editor_table",
)

col1, col2 = st.columns([1, 5])

with col1:
    if st.button("Сохранить правки", type="primary"):
        save_comment_overrides_from_editor(edited_df)
        st.success("Правки сохранены в output/comments_manual_overrides.csv")
        st.rerun()

with col2:
    st.write(f"Строк в таблице: {len(editor_df)}")
