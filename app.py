import json
import streamlit as st
import pandas as pd
import requests
import re
import html
from pathlib import Path
from playwright.sync_api import sync_playwright

st.set_page_config(
    page_title="키노라이츠 랭킹/OTT 검색",
    page_icon="🎬",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background:
        radial-gradient(circle at 12% 0%, rgba(37,99,235,0.22), transparent 30%),
        radial-gradient(circle at 92% 0%, rgba(59,130,246,0.14), transparent 28%),
        linear-gradient(180deg, #071326 0%, #050b18 48%, #050b18 100%);
}

.block-container {
    padding-top:1.05rem;
    padding-left:1.25rem;
    padding-right:1.25rem;
    max-width:100%;
}

h1,h2,h3,p,label {
    color:#f8fafc !important;
}

[data-baseweb="popover"] div,
[data-baseweb="popover"] span,
[data-baseweb="popover"] li,
[data-baseweb="popover"] * {
    color:#111827 !important;
    opacity:1 !important;
}
header, footer {
    visibility:hidden;
}

/* 상단 헤더 */
.kino-header {
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:16px;
    margin-bottom:12px;
}

.kino-title {
    display:flex;
    align-items:center;
    gap:10px;
    font-size:30px;
    font-weight:950;
    letter-spacing:-0.7px;
    color:#f8fbff !important;
}

.kino-actions {
    display:flex;
    align-items:center;
    justify-content:flex-end;
    gap:12px;
}

.update-pill {
    display:inline-flex;
    align-items:center;
    gap:7px;
    color:#9fb0ca !important;
    background:rgba(15,28,50,0.78);
    border:1px solid rgba(111,139,178,0.24);
    border-radius:999px;
    padding:9px 13px;
    font-size:13px;
    font-weight:700;
}

.export-fake {
    display:inline-flex;
    align-items:center;
    gap:7px;
    color:#d7e3f7 !important;
    background:#0f1a2b;
    border:1px solid rgba(115,144,184,0.38);
    border-radius:10px;
    padding:9px 14px;
    font-size:13px;
    font-weight:800;
}

/* 탭 */
.stTabs [data-baseweb="tab-list"] {
    gap:30px;
    border-bottom:1px solid rgba(116,142,180,0.24);
    margin-bottom:14px;
}

.stTabs [data-baseweb="tab"] {
    color:#94a3b8 !important;
    font-weight:850;
    padding-bottom:10px;
}

.stTabs [aria-selected="true"] {
    color:#93c5fd !important;
    border-bottom:3px solid #3b82f6;
}

/* Streamlit border container */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background:rgba(10,21,39,0.82) !important;
    border:1px solid rgba(113,142,181,0.20) !important;
    border-radius:16px !important;
    box-shadow:0 12px 28px rgba(0,0,0,0.16);
    padding:14px 14px 16px 14px !important;
}

/* selectbox */
div[data-testid="stSelectbox"] label {
    color:#cbd5e1 !important;
    font-weight:850 !important;
    font-size:13px !important;
}

[data-baseweb="select"] {
    border-radius:10px !important;
}

[data-baseweb="select"] > div {
    background:#0f1a2b !important;
    border:1px solid rgba(115,144,184,0.34) !important;
    border-radius:10px !important;
}

[data-baseweb="select"] * {
    color:#f8fafc !important;
}

[data-baseweb="select"] svg {
    fill:#cbd5e1 !important;
}

[data-baseweb="popover"] * {
    color:#111827 !important;
}

[data-baseweb="popover"] [role="option"],
[data-baseweb="popover"] li {
    color:#111827 !important;
    background:#ffffff !important;
}

[data-baseweb="popover"] [role="option"] *,
[data-baseweb="popover"] li * {
    color:#111827 !important;
    background:transparent !important;
}

[data-baseweb="popover"] [aria-selected="true"],
[data-baseweb="popover"] li:hover {
    background:#e5e7eb !important;
}

[data-baseweb="popover"] [aria-selected="true"] *,
[data-baseweb="popover"] li:hover * {
    color:#111827 !important;
}

/* 공개예정작 필터: 큰 박스/테두리 제거 */
.release-filter-area {
    padding:0 !important;
    margin:0 !important;
    background:transparent !important;
    border:none !important;
    box-shadow:none !important;
}

.release-filter-title {
    color:#9fc0ff !important;
    font-weight:900;
    font-size:14px;
    margin:0 0 5px 0 !important;
    padding:0 !important;
}

/* 버튼 칩 */
div[data-testid="stButton"] {
    margin:0 !important;
}

div[data-testid="stButton"] button {
    height:31px !important;
    min-height:31px !important;
    border-radius:999px !important;
    padding:0 12px !important;
    font-size:13px !important;
    font-weight:850 !important;
    white-space:nowrap !important;
    line-height:1 !important;
    margin:0 !important;
}

div[data-testid="stButton"] button[kind="secondary"] {
    background:rgba(8,18,34,0.92) !important;
    color:#f8fafc !important;
    border:1px solid rgba(111,139,178,0.45) !important;
    box-shadow:none !important;
}

div[data-testid="stButton"] button[kind="secondary"]:hover {
    border-color:#4a80ff !important;
    background:#111c2f !important;
    color:#ffffff !important;
}

div[data-testid="stButton"] button[kind="primary"] {
    background:#4a80ff !important;
    color:#ffffff !important;
    border:1px solid #6ea0ff !important;
    box-shadow:0 0 12px rgba(74,128,255,0.32) !important;
}

/* 랭킹 기준 + B tv+ */
.base-row {
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:16px;
    color:#94a3b8 !important;
    font-size:14px;
    margin-top:10px;
    margin-bottom:14px;
    background:rgba(13,26,47,0.84);
    border:1px solid rgba(112,140,178,0.18);
    border-radius:12px;
    padding:11px 15px;
}

.base-info {
    color:#94a3b8 !important;
    font-size:14px;
}

.btv-check-wrap {
    position:relative;
    display:flex;
    align-items:center;
    gap:7px;
    color:#cbd5e1 !important;
    font-size:14px;
    font-weight:750;
    cursor:default;
    user-select:none;
    white-space:nowrap;
}

.btv-check-box {
    width:15px;
    height:15px;
    border:1px solid #94a3b8;
    border-radius:4px;
    background:#0f172a;
    display:inline-block;
}

.btv-check-wrap:hover::after {
    content:"현재는 체크박스만 노출됩니다. B tv+ 편성작 필터 기능은 추후 연결 예정입니다.";
    position:absolute;
    top:26px;
    right:0;
    width:310px;
    background:#111827;
    color:#f8fafc;
    border:1px solid #334155;
    border-radius:10px;
    padding:9px 11px;
    font-size:12px;
    font-weight:500;
    line-height:1.4;
    z-index:9999;
    box-shadow:0 8px 24px rgba(0,0,0,0.35);
}

/* 컬럼 타이틀 */
div[data-testid="stVerticalBlockBorderWrapper"] h3 {
    font-size:20px !important;
    font-weight:950 !important;
    letter-spacing:-0.4px;
    margin-bottom:12px !important;
}

/* 랭킹 카드 */
.rank-card {
    background:rgba(13,27,49,0.96);
    border:1px solid rgba(111,139,178,0.22);
    border-radius:12px;
    padding:9px 10px;
    margin-bottom:8px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    min-height:70px;
    box-shadow:0 6px 18px rgba(0,0,0,0.08);
}

.rank-card:hover {
    border-color:#3b82f6;
    background:#111c2f;
}

.rank-left {
    display:flex;
    align-items:center;
    gap:11px;
    min-width:0;
}

.rank-num {
    font-size:21px;
    font-weight:950;
    color:#dce8fb !important;
    min-width:34px;
    text-align:center;
    font-style:italic;
}

.title {
    font-size:15px;
    font-weight:850;
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
    max-width:270px;
    color:#f8fafc !important;
}

.meta {
    color:#8fa1bb !important;
    font-size:12px;
    margin-top:4px;
    line-height:1.35;
}

.badge-new {
    color:#f97316 !important;
    font-weight:950;
    font-size:13px;
}

.badge-up {
    color:#22c55e !important;
    font-weight:950;
    font-size:13px;
}

.badge-down {
    color:#ef4444 !important;
    font-weight:950;
    font-size:13px;
}

/* 급상승/신규 카드 */
.side-card {
    background:rgba(13,27,49,0.96);
    border:1px solid rgba(111,139,178,0.22);
    border-radius:12px;
    padding:10px 12px;
    margin-bottom:8px;
    min-height:62px;
    box-shadow:0 6px 18px rgba(0,0,0,0.08);
}

.side-card:hover {
    border-color:#3b82f6;
    background:#111c2f;
}

.small {
    color:#8fa1bb !important;
    font-size:12px;
}

/* 공개예정작 */
.release-row {
    background:rgba(13,27,49,0.96);
    border:1px solid rgba(111,139,178,0.22);
    border-radius:12px;
    padding:8px 9px;
    margin-bottom:8px;
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap:10px;
    min-height:66px;
    box-shadow:0 6px 18px rgba(0,0,0,0.08);
}

.release-row:hover {
    border-color:#3b82f6;
    background:#111c2f;
}

.release-left {
    display:flex;
    align-items:center;
    gap:9px;
    min-width:0;
    flex:1;
}

.release-poster {
    width:44px;
    height:54px;
    border-radius:8px;
    background:linear-gradient(145deg,#1e293b,#0b1220);
    border:1px solid #263244;
    overflow:hidden;
    flex-shrink:0;
    display:flex;
    align-items:center;
    justify-content:center;
    color:#64748b !important;
    font-size:10px;
    font-weight:900;
}

.release-poster img {
    width:100%;
    height:100%;
    object-fit:cover;
    display:block;
}

.release-info {
    min-width:0;
    flex:1;
}

.release-title {
    font-size:14px;
    font-weight:850;
    color:#f8fafc !important;
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
    max-width:210px;
    text-decoration:none;
}

.release-title a {
    color:#f8fafc !important;
    text-decoration:none;
}

.release-title a:hover {
    color:#93c5fd !important;
}

.release-meta {
    color:#8fa1bb !important;
    font-size:12px;
    margin-top:4px;
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
    max-width:210px;
}

.release-date {
    background:#1e293b;
    border:1px solid #334155;
    border-radius:9px;
    padding:6px 8px;
    color:#f8fafc !important;
    font-size:12px;
    font-weight:950;
    white-space:nowrap;
    flex-shrink:0;
}

.release-empty {
    background:rgba(13,27,49,0.96);
    border:1px solid rgba(111,139,178,0.22);
    border-radius:12px;
    padding:12px;
    color:#94a3b8 !important;
    font-size:13px;
}

/* OTT 로고 배지 */
.ott-logo {
    display:inline-block;
    min-width:22px;
    text-align:center;
    border-radius:6px;
    padding:2px 5px;
    margin-right:6px;
    font-size:10px;
    font-weight:950;
    background:#1e293b !important;
    color:#f8fafc !important;
}

.logo-netflix { color:#ef4444 !important; }
.logo-tving { color:#ef4444 !important; }
.logo-wavve { color:#60a5fa !important; }
.logo-disney { color:#93c5fd !important; }
.logo-watcha { color:#ec4899 !important; }
.logo-coupang { color:#38bdf8 !important; }
.logo-apple { color:#f8fafc !important; }
.logo-laftel { color:#c084fc !important; }

.ott-badge {
    display:inline-block;
    background:#1e293b;
    border:1px solid #475569;
    border-radius:999px;
    padding:5px 10px;
    margin-right:6px;
    margin-top:6px;
    font-weight:700;
    color:#f8fafc !important;
}

/* selectbox dropdown menu text fix */
div[data-baseweb="popover"] {
    background:#ffffff !important;
}

div[data-baseweb="popover"] * {
    color:#111827 !important;
}

ul[role="listbox"] {
    background:#ffffff !important;
}

ul[role="listbox"] li,
ul[role="listbox"] div,
ul[role="listbox"] span {
    color:#111827 !important;
    background:#ffffff !important;
}

li[role="option"] {
    color:#111827 !important;
    background:#ffffff !important;
}

li[role="option"] * {
    color:#111827 !important;
    background:transparent !important;
}

li[role="option"][aria-selected="true"],
li[role="option"]:hover {
    background:#e5e7eb !important;
}

li[role="option"][aria-selected="true"] *,
li[role="option"]:hover * {
    color:#111827 !important;
}
/* only restore card title text */
.rank-card .title,
.side-card b,
.release-title,
.release-title a {
    color:#f8fafc !important;
}

.rank-card .meta,
.side-card .small,
.release-meta {
    color:#8fa1bb !important;
}

.search-title {
    font-size:18px;
    font-weight:900;
    color:#f8fafc !important;
}

.search-meta {
    color:#8fa1bb !important;
    font-size:12px;
    margin-top:5px;
}

.search-provider-empty {
    color:#94a3b8 !important;
    font-size:13px;
    margin-top:10px;
}
</style>
""", unsafe_allow_html=True)

OTT_NAMES = [
    "넷플릭스",
    "티빙",
    "쿠팡플레이",
    "웨이브",
    "디즈니+",
    "왓챠",
]

RELEASE_PROVIDERS = [
    "전체",
    "넷플릭스",
    "티빙",
    "쿠팡플레이",
    "디즈니+",
    "웨이브",
    "라프텔",
    "왓챠",
    "Apple TV",
    "아마존 프라임 비디오",
    "씨네폭스",
]


def normalize_period(value):
    value = str(value).strip().lower()

    mapping = {
        "일간": "일간",
        "daily": "일간",
        "day": "일간",
        "d": "일간",
        "주간": "주간",
        "weekly": "주간",
        "week": "주간",
        "w": "주간",
        "월간": "월간",
        "monthly": "월간",
        "month": "월간",
        "m": "월간",
    }

    return mapping.get(value, str(value).strip())


def get_kino_base_label(selected_period, latest_date):
    latest = pd.to_datetime(latest_date)

    if selected_period == "일간":
        return latest.strftime("%m.%d 기준")

    if selected_period == "주간":
        weekday = latest.weekday()
        this_week_monday = latest - pd.Timedelta(days=weekday)
        prev_week_monday = this_week_monday - pd.Timedelta(days=7)
        prev_week_sunday = prev_week_monday + pd.Timedelta(days=6)
        return f"{prev_week_monday.strftime('%m.%d')}~{prev_week_sunday.strftime('%m.%d')} 기준"

    if selected_period == "월간":
        prev_month = latest - pd.DateOffset(months=1)
        return prev_month.strftime("%Y.%m 기준")

    return str(latest_date)


def get_kino_base_tooltip(selected_period):
    if selected_period == "일간":
        return "집계 기준: 일간 · 전일 기준, 매일 오후 2시 업데이트"

    if selected_period == "주간":
        return "집계 기준: 주간 · 전주 월요일~일요일"

    if selected_period == "월간":
        return "집계 기준: 월간 · 전월 1일~말일"

    return "키노라이츠 트렌드 랭킹 기준"


def is_bad_release_title(title):
    title = str(title).strip()

    bad_titles = {
        "",
        "홈",
        "랭킹",
        "탐색",
        "혜택",
        "마이페이지",
        "주메뉴",
        "상단으로",
        "맨 위로",
        "뒤로가기",
        "공유",
        "검색",
        "신작",
        "공개예정작",
        "종료예정작",
        "본 작품 제외",
        "구매/대여 제외",
        "업데이트 정보를 모두 가져왔습니다",
        "업데이트 정보를 모두 가져왔습니다.",
        "전체",
        "MY",
        "ALL",
        "작품",
        "인물",
        "컬렉션",
        "필터",
        "로그인",
        "가입",
    }

    if title in bad_titles:
        return True

    if re.fullmatch(r"\d+\s*편(\s*공개예정)?", title):
        return True

    if re.fullmatch(r"\d+\.\d+%?", title):
        return True

    if title == "%":
        return True

    return False


@st.cache_data(ttl=60)
def load_ranking_data():
    file = Path("ranking_history.csv")

    if not file.exists():
        return pd.DataFrame()

    df = pd.read_csv(file)

    if df.empty:
        return df

    required_cols = [
        "date", "period", "title", "rank", "delta", "is_new",
        "providers", "genres", "open_year", "media_type"
    ]

    for col in required_cols:
        if col not in df.columns:
            df[col] = ""

    df["date"] = df["date"].astype(str)
    df["period"] = df["period"].apply(normalize_period)
    df["title"] = df["title"].fillna("").astype(str)
    df["providers"] = df["providers"].fillna("").astype(str)
    df["genres"] = df["genres"].fillna("").astype(str)
    df["open_year"] = df["open_year"].fillna("").astype(str)
    df["media_type"] = df["media_type"].fillna("").astype(str)

    df["rank"] = pd.to_numeric(df["rank"], errors="coerce")
    df["delta"] = pd.to_numeric(df["delta"], errors="coerce").fillna(0)
    df["is_new"] = df["is_new"].astype(str).str.lower().isin(["true", "1"])

    df = df[df["title"].str.strip() != ""].copy()

    return df


@st.cache_data(ttl=60)
def load_upcoming_releases():
    file = Path("upcoming_releases.csv")

    columns = [
        "collect_date", "release_date", "title",
        "provider", "genre", "url", "image_url"
    ]

    if not file.exists():
        return pd.DataFrame(columns=columns)

    df = pd.read_csv(file)

    if df.empty:
        return pd.DataFrame(columns=columns)

    for col in columns:
        if col not in df.columns:
            df[col] = ""

    df["collect_date"] = df["collect_date"].fillna("").astype(str)
    df["release_date"] = df["release_date"].fillna("").astype(str)
    df["title"] = df["title"].fillna("").astype(str).str.strip()
    df["provider"] = df["provider"].fillna("").astype(str).str.strip()
    df["genre"] = df["genre"].fillna("").astype(str).str.strip()
    df["url"] = df["url"].fillna("").astype(str).str.strip()
    df["image_url"] = df["image_url"].fillna("").astype(str).str.strip()

    df = df[~df["title"].apply(is_bad_release_title)].copy()

    df["release_date_dt"] = pd.to_datetime(df["release_date"], errors="coerce")

    df = df[df["title"].str.strip() != ""].copy()
    df = df[df["release_date_dt"].notna()].copy()

    # 중요: provider까지 포함해야 OTT별 데이터가 안 날아감
    df = df.drop_duplicates(
        subset=["release_date", "title", "provider"],
        keep="first"
    )

    df = df.sort_values(
        ["release_date_dt", "provider", "title"],
        ascending=[True, True, True]
    )

    return df

def make_meta(row):
    media_type = str(row.get("media_type", "")).upper()
    genres = str(row.get("genres", "")).replace(",", "/")
    open_year = str(row.get("open_year", ""))

    type_text = ""

    if media_type == "MOVIE":
        type_text = "영화"
    elif media_type in ["TV", "SHOW", "SERIES", "DRAMA"]:
        type_text = "드라마"
    elif media_type == "ANIMATION":
        type_text = "애니메이션"

    parts = []

    if type_text:
        parts.append(type_text)

    if genres and genres != "nan":
        parts.append(genres)

    if open_year and open_year != "nan":
        parts.append(open_year)

    return " · ".join(parts)


def get_provider_logo(provider):
    p = str(provider).strip()

    if p == "":
        return ""

    if "넷플" in p:
        return '<span class="ott-logo logo-netflix">N</span>'
    if "티빙" in p:
        return '<span class="ott-logo logo-tving">T</span>'
    if "웨이브" in p:
        return '<span class="ott-logo logo-wavve">W</span>'
    if "디즈니" in p:
        return '<span class="ott-logo logo-disney">D+</span>'
    if "왓챠" in p:
        return '<span class="ott-logo logo-watcha">W</span>'
    if "쿠팡" in p:
        return '<span class="ott-logo logo-coupang">▶</span>'
    if "Apple" in p or "애플" in p:
        return '<span class="ott-logo logo-apple"></span>'
    if "라프텔" in p:
        return '<span class="ott-logo logo-laftel">L</span>'
    if "아마존" in p:
        return '<span class="ott-logo">P</span>'
    if "씨네폭스" in p:
        return '<span class="ott-logo">C</span>'

    return ""


def format_release_date(value):
    dt = pd.to_datetime(value, errors="coerce")

    if pd.isna(dt):
        return "-"

    return f"{dt.month}/{dt.day}"


def render_rank_card(row):
    try:
        rank_text = str(int(row["rank"]))
    except Exception:
        rank_text = "-"

    if row.get("is_new", False):
        badge = '<span class="badge-new">NEW</span>'
    elif row.get("delta", 0) > 0:
        badge = f'<span class="badge-up">▲{int(row["delta"])}</span>'
    elif row.get("delta", 0) < 0:
        badge = f'<span class="badge-down">▼{abs(int(row["delta"]))}</span>'
    else:
        badge = ""

    meta = html.escape(make_meta(row))
    title = html.escape(str(row.get("title", "")))

    st.markdown(f"""
    <div class="rank-card">
        <div class="rank-left">
            <div class="rank-num">{rank_text}</div>
            <div>
                <div class="title">{title}</div>
                <div class="meta">{meta}</div>
            </div>
        </div>
        <div>{badge}</div>
    </div>
    """, unsafe_allow_html=True)


def render_upcoming_releases(release_df, max_items=80, hide_provider=False):
    if release_df.empty:
        st.markdown(
            '<div class="release-empty">공개예정작 데이터가 없습니다.</div>',
            unsafe_allow_html=True
        )
        return

    for _, row in release_df.head(max_items).iterrows():
        title = str(row.get("title", "")).strip()

        if is_bad_release_title(title):
            continue

        provider = str(row.get("provider", "")).strip()
        genre = str(row.get("genre", "")).strip()
        date_text = format_release_date(row.get("release_date_dt"))
        url = str(row.get("url", "")).strip()
        image_url = str(row.get("image_url", "")).strip()

        logo = "" if hide_provider else get_provider_logo(provider)

        safe_title = html.escape(title)
        safe_provider = html.escape(provider)
        safe_genre = html.escape(genre)
        safe_date = html.escape(date_text)
        safe_url = html.escape(url)
        safe_image_url = html.escape(image_url)

        meta_parts = []

        if safe_provider and not hide_provider:
            meta_parts.append(safe_provider)

        if safe_genre:
            meta_parts.append(safe_genre)

        meta_html = ""

        if meta_parts:
            meta_text = " · ".join(meta_parts)
            meta_html = f'<div class="release-meta">{meta_text}</div>'

        if safe_image_url:
            poster_html = f'<img src="{safe_image_url}" onerror="this.style.display=\'none\';" />'
        else:
            poster_html = "IMG"

        if safe_url:
            title_html = f'<a href="{safe_url}" target="_self">{logo}{safe_title}</a>'
        else:
            title_html = f'{logo}{safe_title}'

        row_html = (
            '<div class="release-row">'
            '<div class="release-left">'
            f'<div class="release-poster">{poster_html}</div>'
            '<div class="release-info">'
            f'<div class="release-title">{title_html}</div>'
            f'{meta_html}'
            '</div>'
            '</div>'
            f'<div class="release-date">{safe_date}</div>'
            '</div>'
        )

        st.markdown(row_html, unsafe_allow_html=True)

def search_contents(keyword):
    query = """
    query SearchContents($keyword: String!) {
      contents(keyword: $keyword, limit: 8) {
        id
        titleKr
        titleEn
        openYear
      }
    }
    """

    payload = {
        "operationName": "SearchContents",
        "variables": {"keyword": keyword},
        "query": query,
    }

    try:
        res = requests.post(
            "https://gateway.kinolights.com/graphql",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=20,
        )
        data = res.json()

        if "errors" in data:
            return []

        return data.get("data", {}).get("contents", []) or []

    except Exception:
        return []


def extract_subscription_section(text):
    text = str(text)

    start_keys = ["정액제", "보러가기"]
    end_keys = [
        "구매",
        "대여",
        "시청 주의 가이드",
        "작품 정보",
        "비슷한 작품",
        "관련 콘텐츠",
        "코멘트",
        "리뷰",
        "출연",
        "감독",
    ]

    start = -1
    for key in start_keys:
        idx = text.find(key)
        if idx != -1:
            start = idx
            break

    if start == -1:
        return ""

    section = text[start:]

    cut = len(section)
    for key in end_keys:
        idx = section.find(key)
        if idx != -1:
            cut = min(cut, idx)

    return section[:cut]


def detect_ott_from_section(section):
    section = html.unescape(str(section))

    found = []

    direct_matches = re.findall(
        r"(넷플릭스|티빙|쿠팡플레이|웨이브|디즈니\+|디즈니 플러스|왓챠|라프텔|Apple TV|아마존 프라임 비디오|씨네폭스)\s*바로 보기",
        section
    )

    for name in direct_matches:
        if name == "디즈니 플러스":
            name = "디즈니+"
        found.append(name)

    return sorted(set(found))

def get_ott_providers_from_api(content_id):
    urls = [
        f"https://m.kinolights.com/season/{content_id}",
        f"https://m.kinolights.com/title/{content_id}",
        f"https://m.kinolights.com/movie/{content_id}",
        f"https://m.kinolights.com/content/{content_id}",
    ]

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
            "Mobile/15E148 Safari/604.1"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    all_providers = []

    for url in urls:
        try:
            res = requests.get(url, headers=headers, timeout=20)

            if res.status_code != 200:
                continue

            text = html.unescape(res.text)

            providers = detect_ott_from_section(text)

            for p in providers:
                if p not in all_providers:
                    all_providers.append(p)

        except Exception:
            continue

    return all_providers
        
def set_release_provider(provider):
    st.session_state.selected_release_provider = provider


df_for_header = load_ranking_data()
latest_label = "-"

if not df_for_header.empty:
    try:
        latest_date_for_header = sorted(df_for_header["date"].astype(str).unique(), reverse=True)[0]
        latest_label = pd.to_datetime(latest_date_for_header).strftime("%m.%d 10:00")
    except Exception:
        latest_label = "-"

if "selected_release_provider" not in st.session_state:
    st.session_state.selected_release_provider = "전체"

st.markdown(f"""
<div class="kino-header">
    <div class="kino-title">
        <span>🎬</span>
        <span>키노라이츠 랭킹 / OTT 편성 검색</span>
    </div>
    <div class="kino-actions">
        <div class="update-pill">↻ 데이터 업데이트: {latest_label}</div>
        <div class="export-fake">⇩ 내보내기</div>
    </div>
</div>
""", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📈 랭킹 대시보드", "🔎 OTT 제공처 검색"])

with tab1:
    df = df_for_header

    if df.empty:
        st.error("ranking_history.csv가 없거나 수집된 랭킹 데이터가 없습니다.")
        st.stop()

    latest_date = sorted(df["date"].unique(), reverse=True)[0]
    latest = df[df["date"] == latest_date].copy()

    filter_left, filter_right = st.columns([0.46, 0.54])

    with filter_left:
        with st.container(border=True):
            f1, f2 = st.columns([1, 1])

            with f1:
                selected_period = st.selectbox(
                    "기간 선택",
                    ["일간", "주간", "월간"],
                    index=1
                )

            with f2:
                selected_ott = st.selectbox(
                    "OTT 선택",
                    ["전체"] + OTT_NAMES,
                    index=0
                )

            st.markdown(
                """
                <div class="btv-check-wrap" style="margin-top:10px;">
                    <span class="btv-check-box"></span>
                    <span>B tv+ 편성작만 보기</span>
                </div>
                """,
                unsafe_allow_html=True
            )

    with filter_right:
        st.markdown(
            '<div class="release-filter-area"><div class="release-filter-title">공개예정작 필터</div></div>',
            unsafe_allow_html=True
        )

        chip_cols_1 = st.columns([0.7, 1, 0.8, 1.2, 1, 0.8])
        chip_cols_2 = st.columns([0.8, 0.8, 1, 1.6, 1])

        for col, provider in zip(chip_cols_1, RELEASE_PROVIDERS[:6]):
            with col:
                active = st.session_state.selected_release_provider == provider
                st.button(
                    provider,
                    key=f"release_provider_{provider}",
                    type="primary" if active else "secondary",
                    use_container_width=True,
                    on_click=set_release_provider,
                    args=(provider,)
                )

        for col, provider in zip(chip_cols_2, RELEASE_PROVIDERS[6:]):
            with col:
                active = st.session_state.selected_release_provider == provider
                st.button(
                    provider,
                    key=f"release_provider_{provider}",
                    type="primary" if active else "secondary",
                    use_container_width=True,
                    on_click=set_release_provider,
                    args=(provider,)
                )

        selected_release_provider = st.session_state.selected_release_provider

    display_base_label = get_kino_base_label(selected_period, latest_date)
    base_tooltip = get_kino_base_tooltip(selected_period)

    st.markdown(
        f"""
        <div class="base-row">
            <div class="base-info" title="{base_tooltip}">
                ⓘ 랭킹 기준: {display_base_label}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    base = latest[latest["period"] == selected_period].copy()

    if selected_ott != "전체":
        base = base[base["providers"].str.contains(selected_ott, na=False)].copy()

    if base.empty:
        st.warning(f"'{selected_period}' 기간 데이터가 없어 최신일자 전체 데이터를 표시합니다.")
        base = latest.copy()

        if selected_ott != "전체":
            base = base[base["providers"].str.contains(selected_ott, na=False)].copy()

    base = base.sort_values("rank")
    new_df = base[base["is_new"] == True].copy()
    up_df = base[base["delta"] > 0].copy().sort_values("delta", ascending=False)

    release_df = load_upcoming_releases()

    if not release_df.empty:
        release_df = release_df[release_df["release_date_dt"].notna()].copy()

        if selected_release_provider == "전체":
            release_df = (
                release_df
                .sort_values(["release_date_dt", "title", "provider"], ascending=[True, True, True])
                .drop_duplicates(subset=["release_date", "title"], keep="first")
            )
        else:
            release_df = release_df[
                release_df["provider"]
                .astype(str)
                .str.contains(selected_release_provider, na=False, regex=False)
            ].copy()

        release_df = release_df.sort_values(
            ["release_date_dt", "title"],
            ascending=[True, True]
        )

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns([1.1, 1, 1, 1])

    with col1:
        with st.container(border=True):
            st.subheader(f"🏆 {selected_ott} {selected_period} TOP100")

            if base.empty:
                st.warning("데이터 없음")
            else:
                for _, row in base.head(100).iterrows():
                    render_rank_card(row)

    with col2:
        with st.container(border=True):
            st.subheader("🚀 급상승 콘텐츠")

            if up_df.empty:
                st.info("급상승 콘텐츠 없음")
            else:
                for _, row in up_df.head(30).iterrows():
                    meta = html.escape(make_meta(row))

                    try:
                        rank_text = str(int(row["rank"]))
                    except Exception:
                        rank_text = "-"

                    title = html.escape(str(row["title"]))
                    delta = int(row["delta"])

                    st.markdown(f"""
                    <div class="side-card">
                        <span class="badge-up">▲{delta}</span>
                        &nbsp;
                        <b>{title}</b><br>
                        <span class="small">#{rank_text} · {meta}</span>
                    </div>
                    """, unsafe_allow_html=True)

    with col3:
        with st.container(border=True):
            st.subheader("🔥 신규 진입 콘텐츠")

            if new_df.empty:
                st.info("신규 진입 콘텐츠 없음")
            else:
                for _, row in new_df.head(30).iterrows():
                    meta = html.escape(make_meta(row))

                    try:
                        rank_text = str(int(row["rank"]))
                    except Exception:
                        rank_text = "-"

                    title = html.escape(str(row["title"]))

                    st.markdown(f"""
                    <div class="side-card">
                        <span class="badge-new">NEW</span>
                        &nbsp;
                        #{rank_text}
                        &nbsp;
                        <b>{title}</b><br>
                        <span class="small">{meta}</span>
                    </div>
                    """, unsafe_allow_html=True)

    with col4:
        with st.container(border=True):
            st.subheader("🗓 공개 예정작")
            render_upcoming_releases(
                release_df,
                max_items=80,
                hide_provider=(selected_release_provider == "전체")
            )

with tab2:
    st.subheader("🔎 타이틀로 OTT 제공처 검색")

    keyword = st.text_input(
        "작품명을 입력하세요",
        placeholder="예: 멋진 신세계"
    )

    if keyword:
        with st.spinner("키노라이츠에서 검색 및 정액제 제공처 확인 중..."):
            results = search_contents(keyword)

            enriched_results = []
            for item in results[:5]:
                content_id = item.get("id")
                providers = get_ott_providers_from_api(content_id) if content_id else []

                enriched_results.append({
                    "title": item.get("titleKr") or "",
                    "title_en": item.get("titleEn") or "",
                    "open_year": item.get("openYear") or "",
                    "providers": providers,
                })

        if not enriched_results:
            st.warning("검색 결과 없음")
            st.stop()

        st.markdown("### 검색 결과")

        for item in enriched_results:
            title = html.escape(str(item["title"]))
            title_en = html.escape(str(item["title_en"]))
            open_year = html.escape(str(item["open_year"]))
            providers = item["providers"]

            meta_parts = []
            if title_en:
                meta_parts.append(title_en)
            if open_year:
                meta_parts.append(open_year)

            meta_text = " · ".join(meta_parts)

            if providers:
                provider_html = "".join(
                    [f'<span class="ott-badge">{html.escape(p)}</span>' for p in providers]
                )
            else:
                provider_html = '<span class="search-provider-empty">정액제 OTT 없음</span>'

            st.markdown(f"""
            <div class="side-card" style="margin-bottom:12px;">
                <div class="search-title">{title}</div>
                <div class="search-meta">{meta_text}</div>
                <div style="margin-top:10px;">
                    {provider_html}
                </div>
            </div>
            """, unsafe_allow_html=True)
