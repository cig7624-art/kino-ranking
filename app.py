import streamlit as st
import pandas as pd
import requests
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

st.set_page_config(
    page_title="키노라이츠 랭킹/OTT 검색",
    page_icon="🎬",
    layout="wide"
)

st.markdown("""
<style>
.stApp { background:#090d1a; }
h1,h2,h3,p,label,div,span { color:#f8fafc !important; }
.block-container { padding-top:1.3rem; }

.top-tabs {
    display:flex;
    gap:28px;
    border-bottom:1px solid #1e293b;
    margin-bottom:18px;
}
.tab-active {
    color:#bfdbfe !important;
    font-weight:900;
    padding:10px 0;
    border-bottom:3px solid #3b82f6;
}
.tab-inactive {
    color:#94a3b8 !important;
    font-weight:700;
    padding:10px 0;
}

.filter-card {
    background:#0f172a;
    border:1px solid #1e293b;
    border-radius:14px;
    padding:14px 16px;
    min-height:84px;
}

.release-filter-card {
    background:linear-gradient(135deg,#0f172a,#101a2e);
    border:1px solid #2563eb;
    box-shadow:0 0 20px rgba(37,99,235,0.18);
    border-radius:16px;
    padding:14px 16px;
    min-height:84px;
}

.release-filter-title {
    color:#bfdbfe !important;
    font-size:13px;
    font-weight:900;
    margin-bottom:10px;
}

.release-filter-row {
    display:flex;
    align-items:center;
    gap:8px;
    flex-wrap:wrap;
}

.filter-chip {
    display:inline-flex;
    align-items:center;
    gap:6px;
    padding:7px 11px;
    border-radius:999px;
    background:#111827;
    border:1px solid #334155;
    color:#e5e7eb !important;
    font-size:12px;
    font-weight:800;
    white-space:nowrap;
}
.filter-chip-active {
    background:#2563eb;
    border:1px solid #60a5fa;
    color:#ffffff !important;
    box-shadow:0 0 12px rgba(37,99,235,0.35);
}
.filter-chip-date {
    display:inline-flex;
    align-items:center;
    padding:7px 11px;
    border-radius:10px;
    background:#111827;
    border:1px solid #334155;
    color:#cbd5e1 !important;
    font-size:12px;
    font-weight:800;
}
.filter-chip-date-active {
    background:#1d4ed8;
    color:#ffffff !important;
    border:1px solid #60a5fa;
}

.logo-mini {
    display:inline-flex;
    align-items:center;
    justify-content:center;
    width:18px;
    height:18px;
    border-radius:50%;
    font-size:10px;
    font-weight:900;
    color:#ffffff !important;
}
.logo-netflix { background:#000000; color:#ef4444 !important; }
.logo-tving { background:#0b0b0b; color:#ef4444 !important; }
.logo-coupang { background:#0ea5e9; color:#ffffff !important; }
.logo-wave { background:#2563eb; color:#ffffff !important; }
.logo-disney { background:#083344; color:#93c5fd !important; }
.logo-watcha { background:#111827; color:#ec4899 !important; }
.logo-apple { background:#111827; color:#f8fafc !important; }
.logo-laftel { background:#4c1d95; color:#ffffff !important; }
.logo-etc { background:#475569; color:#ffffff !important; }

.base-label {
    background:#0f172a;
    border:1px solid #1e293b;
    border-radius:12px;
    padding:10px 14px;
    color:#94a3b8 !important;
    font-size:13px;
    margin-top:10px;
    margin-bottom:14px;
}

.panel {
    background:#0f172a;
    border:1px solid #1e293b;
    border-radius:14px;
    padding:12px 12px;
    min-height:570px;
}
.panel-release {
    background:linear-gradient(180deg,#0f172a,#0b1220);
    border:1px solid #2563eb;
    box-shadow:0 0 18px rgba(37,99,235,0.16);
    border-radius:14px;
    padding:12px 12px;
    min-height:570px;
}

.panel-head {
    display:flex;
    align-items:center;
    justify-content:space-between;
    margin-bottom:10px;
}
.panel-title {
    font-size:21px;
    font-weight:900;
    color:#f8fafc !important;
}
.more {
    color:#94a3b8 !important;
    font-size:13px;
    font-weight:800;
}

.rank-card {
    background:#111827;
    border:1px solid #263244;
    border-radius:12px;
    padding:10px 11px;
    margin-bottom:8px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    min-height:72px;
}
.rank-left {
    display:flex;
    align-items:center;
    gap:10px;
    min-width:0;
}
.rank-num {
    font-size:24px;
    font-weight:900;
    color:#f8fafc !important;
    min-width:28px;
    text-align:center;
}
.title {
    font-size:15px;
    font-weight:900;
    color:#f8fafc !important;
}
.meta {
    color:#94a3b8 !important;
    font-size:12px;
    margin-top:4px;
    line-height:1.35;
}
.badge-new { color:#f97316 !important; font-weight:900; font-size:13px; }
.badge-up { color:#22c55e !important; font-weight:900; font-size:13px; }
.badge-down { color:#ef4444 !important; font-weight:900; font-size:13px; }

.side-card {
    background:#111827;
    border:1px solid #263244;
    border-radius:12px;
    padding:10px 11px;
    margin-bottom:8px;
    min-height:62px;
}
.small { color:#94a3b8 !important; font-size:12px; }

.release-row {
    background:#111827;
    border:1px solid #263244;
    border-radius:12px;
    padding:10px 11px;
    margin-bottom:8px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:10px;
    min-height:62px;
}
.release-left {
    display:flex;
    align-items:center;
    gap:9px;
    min-width:0;
}
.release-icon {
    width:34px;
    height:34px;
    border-radius:10px;
    background:#0b1220;
    border:1px solid #334155;
    display:flex;
    align-items:center;
    justify-content:center;
    flex-shrink:0;
}
.release-title {
    font-size:14px;
    font-weight:900;
    color:#f8fafc !important;
    line-height:1.25;
    max-width:190px;
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
}
.release-provider {
    color:#94a3b8 !important;
    font-size:12px;
    margin-top:3px;
}
.release-date {
    flex-shrink:0;
    background:#1e293b;
    border:1px solid #334155;
    border-radius:10px;
    padding:7px 9px;
    color:#f8fafc !important;
    font-size:13px;
    font-weight:900;
}
.release-empty {
    background:#111827;
    border:1px solid #263244;
    border-radius:12px;
    padding:14px;
    color:#94a3b8 !important;
    font-size:13px;
}

.bottom-button {
    margin-top:12px;
    background:#111827;
    border:1px solid #263244;
    border-radius:12px;
    padding:12px;
    text-align:center;
    color:#cbd5e1 !important;
    font-weight:800;
}

.ott-badge{
    display:inline-block;
    background:#1e293b;
    border:1px solid #475569;
    border-radius:999px;
    padding:5px 10px;
    margin-right:6px;
    margin-top:6px;
    font-weight:700;
}

[data-baseweb="select"] * { color:#111827 !important; }
[data-baseweb="popover"] * {
    color:#111827 !important;
    background:#ffffff !important;
}
input { color:#111827 !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>🎬 키노라이츠 랭킹 / OTT 편성 검색</h1>", unsafe_allow_html=True)

st.markdown("""
<div class="top-tabs">
    <div class="tab-active">📊 랭킹 대시보드</div>
    <div class="tab-inactive">🔎 OTT 제공처 검색</div>
</div>
""", unsafe_allow_html=True)

OTT_NAMES = [
    "넷플릭스", "티빙", "웨이브", "디즈니+",
    "쿠팡플레이", "왓챠", "애플TV+", "라프텔"
]

RELEASE_PROVIDERS = [
    "전체", "넷플릭스", "티빙", "쿠팡플레이", "웨이브",
    "디즈니+", "왓챠", "애플TV+", "라프텔"
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


def provider_logo_class(provider):
    p = str(provider).lower()

    if "넷플" in p or "netflix" in p:
        return "logo-netflix", "N"
    if "티빙" in p or "tving" in p:
        return "logo-tving", "T"
    if "쿠팡" in p or "coupang" in p:
        return "logo-coupang", "▶"
    if "웨이브" in p or "wavve" in p:
        return "logo-wave", "W"
    if "디즈니" in p or "disney" in p:
        return "logo-disney", "D+"
    if "왓챠" in p or "watcha" in p:
        return "logo-watcha", "W"
    if "애플" in p or "apple" in p:
        return "logo-apple", ""
    if "라프텔" in p or "laftel" in p:
        return "logo-laftel", "L"

    return "logo-etc", "OTT"


def provider_logo_html(provider):
    cls, label = provider_logo_class(provider)
    return f'<span class="logo-mini {cls}">{label}</span>'


@st.cache_data(ttl=300)
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
    df["title"] = df["title"].astype(str)
    df["providers"] = df["providers"].fillna("").astype(str)
    df["genres"] = df["genres"].fillna("").astype(str)
    df["open_year"] = df["open_year"].fillna("").astype(str)
    df["media_type"] = df["media_type"].fillna("").astype(str)

    df["rank"] = pd.to_numeric(df["rank"], errors="coerce")
    df["delta"] = pd.to_numeric(df["delta"], errors="coerce").fillna(0)
    df["is_new"] = df["is_new"].astype(str).str.lower().isin(["true", "1"])

    return df


@st.cache_data(ttl=300)
def load_upcoming_releases():
    file = Path("upcoming_releases.csv")

    if not file.exists():
        return pd.DataFrame(columns=["collect_date", "release_date", "title", "provider", "genre"])

    df = pd.read_csv(file)

    if df.empty:
        return pd.DataFrame(columns=["collect_date", "release_date", "title", "provider", "genre"])

    for col in ["collect_date", "release_date", "title", "provider", "genre"]:
        if col not in df.columns:
            df[col] = ""

    df["title"] = df["title"].fillna("").astype(str)
    df["provider"] = df["provider"].fillna("").astype(str)
    df["genre"] = df["genre"].fillna("").astype(str)
    df["release_date_dt"] = pd.to_datetime(df["release_date"], errors="coerce")

    df = df[df["title"].str.strip() != ""].copy()
    df = df.sort_values(["release_date_dt", "title"], ascending=[True, True])

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

    meta = make_meta(row)

    st.markdown(f"""
    <div class="rank-card">
        <div class="rank-left">
            <div class="rank-num">{rank_text}</div>
            <div>
                <div class="title">{row.get('title', '')}</div>
                <div class="meta">{meta}</div>
            </div>
        </div>
        <div>{badge}</div>
    </div>
    """, unsafe_allow_html=True)


def format_release_date(value):
    dt = pd.to_datetime(value, errors="coerce")

    if pd.isna(dt):
        return str(value)

    return f"{dt.month}/{dt.day}"


def render_release_rows(release_df, max_items=8):
    if release_df.empty:
        st.markdown('<div class="release-empty">공개예정작 데이터가 없습니다.</div>', unsafe_allow_html=True)
        return

    for _, row in release_df.head(max_items).iterrows():
        title = str(row.get("title", "")).strip()
        provider = str(row.get("provider", "")).strip()
        genre = str(row.get("genre", "")).strip()
        release_date = format_release_date(row.get("release_date_dt", row.get("release_date", "")))
        logo = provider_logo_html(provider)

        sub = provider
        if genre:
            sub = f"{provider} · {genre}"

        st.markdown(f"""
        <div class="release-row">
            <div class="release-left">
                <div class="release-icon">{logo}</div>
                <div>
                    <div class="release-title">{title}</div>
                    <div class="release-provider">{sub}</div>
                </div>
            </div>
            <div class="release-date">{release_date}</div>
        </div>
        """, unsafe_allow_html=True)


def search_contents(keyword):
    query = """
    query SearchContents($keyword: String!) {
      contents(keyword: $keyword, limit: 5) {
        id
        titleKr
        openYear
      }
    }
    """

    payload = {
        "operationName": "SearchContents",
        "variables": {"keyword": keyword},
        "query": query,
    }

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

    return data["data"]["contents"]


def get_ott_providers(content_id):
    urls = [
        f"https://m.kinolights.com/title/{content_id}",
        f"https://m.kinolights.com/content/{content_id}",
        f"https://m.kinolights.com/contents/{content_id}",
    ]

    found = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path="/usr/bin/chromium"
        )

        page = browser.new_page(
            viewport={"width": 430, "height": 1600},
            user_agent="Mozilla/5.0"
        )

        for url in urls:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(1200)

                text = page.locator("body").inner_text()

                if "보러가기" not in text:
                    continue

                section = text.split("보러가기", 1)[1]

                if "시청 주의 가이드" in section:
                    section = section.split("시청 주의 가이드", 1)[0]

                for ott in OTT_NAMES:
                    if ott in section:
                        found.append(ott)

                if found:
                    break

            except Exception:
                continue

        browser.close()

    return sorted(set(found))


tab1, tab2 = st.tabs(["📈 랭킹 대시보드", "🔎 OTT 제공처 검색"])

with tab1:
    df = load_ranking_data()

    if df.empty:
        st.error("ranking_history.csv가 없거나 수집된 랭킹 데이터가 없습니다.")
        st.stop()

    latest_date = sorted(df["date"].unique(), reverse=True)[0]
    latest = df[df["date"] == latest_date].copy()

    release_df = load_upcoming_releases()

    top_left, top_right = st.columns([1.05, 1.25])

    with top_left:
        c1, c2 = st.columns([1, 1])

        with c1:
            selected_period = st.selectbox(
                "기간 선택",
                ["일간", "주간", "월간"],
                index=1
            )

        with c2:
            selected_ott = st.selectbox(
                "OTT 선택",
                ["전체"] + OTT_NAMES,
                index=0
            )

        btv_only = st.checkbox("B tv+ 편성작만 보기", value=False, disabled=True)

    with top_right:
        st.markdown('<div class="release-filter-card">', unsafe_allow_html=True)
        st.markdown('<div class="release-filter-title">공개예정작 필터</div>', unsafe_allow_html=True)

        selected_release_provider = st.session_state.get("selected_release_provider", "전체")
        selected_release_range = st.session_state.get("selected_release_range", "7일")

        provider_cols = st.columns([0.55, 0.8, 0.65, 0.95, 0.7, 0.8, 0.65, 0.5, 0.5, 0.5])

        provider_list = ["전체", "넷플릭스", "티빙", "쿠팡플레이", "웨이브", "디즈니+", "왓챠"]
        for i, provider in enumerate(provider_list):
            with provider_cols[i]:
                active = selected_release_provider == provider
                label_html = provider if provider == "전체" else f"{provider_logo_html(provider)} {provider}"
                chip_class = "filter-chip filter-chip-active" if active else "filter-chip"

                if st.button(provider, key=f"release_provider_{provider}", use_container_width=True):
                    st.session_state["selected_release_provider"] = provider
                    selected_release_provider = provider

        range_cols = st.columns([1, 1, 1, 6])
        for label in ["오늘", "7일", "14일"]:
            with range_cols[["오늘", "7일", "14일"].index(label)]:
                if st.button(label, key=f"release_range_{label}", use_container_width=True):
                    st.session_state["selected_release_range"] = label
                    selected_release_range = label

        st.markdown('</div>', unsafe_allow_html=True)

    display_base_label = get_kino_base_label(selected_period, latest_date)
    base_tooltip = get_kino_base_tooltip(selected_period)

    st.markdown(
        f"""
        <div class="base-label" title="{base_tooltip}">
            ⓘ 랭킹 기준: {display_base_label} &nbsp;&nbsp; | &nbsp;&nbsp; 공개예정작 기준: 오늘 이후
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

    filtered_release_df = release_df.copy()

    today = pd.Timestamp.today().normalize()

    if not filtered_release_df.empty:
        filtered_release_df = filtered_release_df[
            filtered_release_df["release_date_dt"].notna()
        ].copy()

        if selected_release_provider != "전체":
            filtered_release_df = filtered_release_df[
                filtered_release_df["provider"].str.contains(selected_release_provider, na=False)
            ].copy()

        if selected_release_range == "오늘":
            end_date = today
        elif selected_release_range == "14일":
            end_date = today + pd.Timedelta(days=14)
        else:
            end_date = today + pd.Timedelta(days=7)

        filtered_release_df = filtered_release_df[
            (filtered_release_df["release_date_dt"] >= today) &
            (filtered_release_df["release_date_dt"] <= end_date)
        ].copy()

        filtered_release_df = filtered_release_df.sort_values(
            ["release_date_dt", "title"],
            ascending=[True, True]
        )

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns([1.05, 1.05, 1.05, 1.1])

    with col1:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown("""
        <div class="panel-head">
            <div class="panel-title">🏆 전체 주간 TOP100</div>
            <div class="more">더보기 〉</div>
        </div>
        """, unsafe_allow_html=True)

        if base.empty:
            st.warning("데이터 없음")
        else:
            for _, row in base.head(5).iterrows():
                render_rank_card(row)

        st.markdown('<div class="bottom-button">TOP100 전체 보기 〉</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown("""
        <div class="panel-head">
            <div class="panel-title">🚀 급상승 콘텐츠</div>
            <div class="more">더보기 〉</div>
        </div>
        """, unsafe_allow_html=True)

        if up_df.empty:
            st.info("급상승 콘텐츠 없음")
        else:
            for _, row in up_df.head(5).iterrows():
                meta = make_meta(row)

                try:
                    rank_text = str(int(row["rank"]))
                except Exception:
                    rank_text = "-"

                st.markdown(f"""
                <div class="side-card">
                    <span class="badge-up">▲{int(row['delta'])}</span>
                    &nbsp;
                    <b>{row['title']}</b><br>
                    <span class="small">#{rank_text} · {meta}</span>
                </div>
                """, unsafe_allow_html=True)

        st.markdown('<div class="bottom-button">급상승 콘텐츠 더보기 〉</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col3:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown("""
        <div class="panel-head">
            <div class="panel-title">🔥 신규 진입 콘텐츠</div>
            <div class="more">더보기 〉</div>
        </div>
        """, unsafe_allow_html=True)

        if new_df.empty:
            st.info("신규 진입 콘텐츠 없음")
        else:
            for _, row in new_df.head(5).iterrows():
                meta = make_meta(row)

                try:
                    rank_text = str(int(row["rank"]))
                except Exception:
                    rank_text = "-"

                st.markdown(f"""
                <div class="side-card">
                    <span class="badge-new">NEW</span>
                    &nbsp;
                    #{rank_text}
                    &nbsp;
                    <b>{row['title']}</b><br>
                    <span class="small">{meta}</span>
                </div>
                """, unsafe_allow_html=True)

        st.markdown('<div class="bottom-button">신규 진입 콘텐츠 더보기 〉</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="panel-release">', unsafe_allow_html=True)
        st.markdown("""
        <div class="panel-head">
            <div class="panel-title">🗓 공개 예정작</div>
            <div class="more">더보기 〉</div>
        </div>
        """, unsafe_allow_html=True)

        render_release_rows(filtered_release_df, max_items=7)

        st.markdown('<div class="bottom-button">공개 예정작 전체 보기 〉</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.subheader("🔎 타이틀로 OTT 제공처 검색")

    keyword = st.text_input(
        "작품명을 입력하세요",
        placeholder="예: 멋진 신세계"
    )

    if keyword:
        with st.spinner("키노라이츠에서 정액제 제공처 확인 중..."):
            results = search_contents(keyword)

            if not results:
                st.warning("검색 결과 없음")
                st.stop()

            item = results[0]
            title = item.get("titleKr")
            open_year = item.get("openYear")
            content_id = item.get("id")

            providers = get_ott_providers(content_id)

            if providers:
                provider_html = "".join(
                    [f'<span class="ott-badge">{p}</span>' for p in providers]
                )
            else:
                provider_html = '<span class="small">정액제 OTT 없음</span>'

            st.markdown(f"""
            <div class="side-card">
                <h3>{title}</h3>
                <div class="small">연도: {open_year}</div>
                <div style="margin-top:10px;">{provider_html}</div>
            </div>
            """, unsafe_allow_html=True)

            with st.expander("다른 검색 후보 보기"):
                for other in results[1:]:
                    st.markdown(
                        f"- {other.get('titleKr')} ({other.get('openYear')})"
                    )
