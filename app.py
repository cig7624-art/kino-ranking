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
.stApp { background:#090d1a; }
h1,h2,h3,p,label,div,span { color:#f8fafc !important; }
.block-container { padding-top:1.3rem; }

.base-label {
    color:#94a3b8 !important;
    font-size:14px;
    margin-top:8px;
    margin-bottom:10px;
}

.rank-card {
    background:#0f172a;
    border:1px solid #1e293b;
    border-radius:12px;
    padding:8px 10px;
    margin-bottom:7px;
    display:flex;
    align-items:center;
    justify-content:space-between;
}
.rank-left {
    display:flex;
    align-items:center;
    gap:10px;
    min-width:0;
}
.rank-num {
    font-size:17px;
    font-weight:900;
    color:#f8fafc !important;
    min-width:30px;
    text-align:right;
    font-style:italic;
}
.title {
    font-size:15px;
    font-weight:800;
}
.meta {
    color:#64748b !important;
    font-size:12px;
    margin-top:3px;
}
.badge-new { color:#f97316 !important; font-weight:900; font-size:13px; }
.badge-up { color:#22c55e !important; font-weight:900; font-size:13px; }
.badge-down { color:#ef4444 !important; font-weight:900; font-size:13px; }

.side-card {
    background:#0f172a;
    border:1px solid #1e293b;
    border-radius:12px;
    padding:9px 11px;
    margin-bottom:8px;
}
.small { color:#94a3b8 !important; font-size:12px; }

.release-row {
    background:#0f172a;
    border:1px solid #1e293b;
    border-radius:12px;
    padding:10px 11px;
    margin-bottom:8px;
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap:10px;
}

.release-left {
    min-width:0;
    flex:1;
}

.release-title {
    font-size:14px;
    font-weight:800;
    color:#f8fafc !important;
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
    max-width:250px;
}

.release-meta {
    color:#94a3b8 !important;
    font-size:12px;
    margin-top:4px;
}

.release-date {
    background:#1e293b;
    border:1px solid #334155;
    border-radius:9px;
    padding:6px 8px;
    color:#f8fafc !important;
    font-size:12px;
    font-weight:900;
    white-space:nowrap;
}

.release-empty {
    background:#0f172a;
    border:1px solid #1e293b;
    border-radius:12px;
    padding:12px;
    color:#94a3b8 !important;
    font-size:13px;
}

.ott-logo {
    display:inline-block;
    min-width:22px;
    text-align:center;
    border-radius:6px;
    padding:2px 5px;
    margin-right:6px;
    font-size:10px;
    font-weight:900;
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

OTT_NAMES = [
    "넷플릭스", "티빙", "웨이브", "디즈니+",
    "쿠팡플레이", "왓챠", "애플TV+", "라프텔"
]

RELEASE_PROVIDERS = [
    "전체", "넷플릭스", "티빙", "쿠팡플레이",
    "웨이브", "디즈니+", "왓챠", "애플TV+", "라프텔"
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

    # 1편, 2편, 3편, 1편공개예정 등 제거
    if re.fullmatch(r"\d+\s*편(\s*공개예정)?", title):
        return True

    # 점수/퍼센트 제거
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
    df["title"] = df["title"].astype(str)
    df["providers"] = df["providers"].fillna("").astype(str)
    df["genres"] = df["genres"].fillna("").astype(str)
    df["open_year"] = df["open_year"].fillna("").astype(str)
    df["media_type"] = df["media_type"].fillna("").astype(str)

    df["rank"] = pd.to_numeric(df["rank"], errors="coerce")
    df["delta"] = pd.to_numeric(df["delta"], errors="coerce").fillna(0)
    df["is_new"] = df["is_new"].astype(str).str.lower().isin(["true", "1"])

    return df


@st.cache_data(ttl=60)
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

    df["collect_date"] = df["collect_date"].fillna("").astype(str)
    df["release_date"] = df["release_date"].fillna("").astype(str)
    df["title"] = df["title"].fillna("").astype(str).str.strip()
    df["provider"] = df["provider"].fillna("").astype(str).str.strip()
    df["genre"] = df["genre"].fillna("").astype(str).str.strip()

    df = df[~df["title"].apply(is_bad_release_title)].copy()

    df["release_date_dt"] = pd.to_datetime(df["release_date"], errors="coerce")

    df = df[df["title"].str.strip() != ""].copy()
    df = df[df["release_date_dt"].notna()].copy()

    df = df.drop_duplicates(
        subset=["release_date", "title"],
        keep="first"
    )

    df = df.sort_values(
        ["release_date_dt", "title"],
        ascending=[True, True]
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
    if "애플" in p:
        return '<span class="ott-logo logo-apple"></span>'
    if "라프텔" in p:
        return '<span class="ott-logo logo-laftel">L</span>'

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


def render_upcoming_releases(release_df, max_items=80):
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
        logo = get_provider_logo(provider)

        safe_title = html.escape(title)
        safe_provider = html.escape(provider)
        safe_genre = html.escape(genre)
        safe_date = html.escape(date_text)

        meta_parts = []

        if safe_provider:
            meta_parts.append(safe_provider)

        if safe_genre:
            meta_parts.append(safe_genre)

        if meta_parts:
            meta_html = '<div class="release-meta">' + " · ".join(meta_parts) + '</div>'
        else:
            meta_html = ""

        row_html = (
            '<div class="release-row">'
            '<div class="release-left">'
            f'<div class="release-title">{logo}{safe_title}</div>'
            f'{meta_html}'
            '</div>'
            f'<div class="release-date">{safe_date}</div>'
            '</div>'
        )

        st.markdown(row_html, unsafe_allow_html=True)


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

    top1, top2, top3 = st.columns([1, 1, 1])

    with top1:
        selected_period = st.selectbox(
            "기간 선택",
            ["일간", "주간", "월간"],
            index=1
        )

    with top2:
        selected_ott = st.selectbox(
            "OTT 선택",
            ["전체"] + OTT_NAMES,
            index=0
        )

    with top3:
        selected_release_provider = st.selectbox(
            "공개예정작 OTT",
            RELEASE_PROVIDERS,
            index=0
        )

    display_base_label = get_kino_base_label(selected_period, latest_date)
    base_tooltip = get_kino_base_tooltip(selected_period)

    st.markdown(
        f"""
        <div class="base-label" title="{base_tooltip}">
            ⓘ 랭킹 기준: {display_base_label} &nbsp;&nbsp; | &nbsp;&nbsp; 공개예정작 기준: 키노라이츠 공개예정작
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

        # provider 값이 실제로 있을 때만 OTT 필터 적용
        if selected_release_provider != "전체":
            has_provider = release_df["provider"].astype(str).str.strip() != ""

            if has_provider.any():
                release_df = release_df[
                    release_df["provider"].str.contains(
                        selected_release_provider,
                        na=False
                    )
                ].copy()

        release_df = release_df.sort_values(
            ["release_date_dt", "title"],
            ascending=[True, True]
        )

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns([1.1, 1, 1, 1])

    with col1:
        st.subheader(f"🏆 {selected_ott} {selected_period} TOP100")

        if base.empty:
            st.warning("데이터 없음")
        else:
            for _, row in base.head(100).iterrows():
                render_rank_card(row)

    with col2:
        st.subheader("🚀 급상승 콘텐츠")

        if up_df.empty:
            st.info("급상승 콘텐츠 없음")
        else:
            for _, row in up_df.head(30).iterrows():
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

    with col3:
        st.subheader("🔥 신규 진입 콘텐츠")

        if new_df.empty:
            st.info("신규 진입 콘텐츠 없음")
        else:
            for _, row in new_df.head(30).iterrows():
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

    with col4:
        st.subheader("🗓 공개 예정작")
        render_upcoming_releases(release_df, max_items=80)

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
