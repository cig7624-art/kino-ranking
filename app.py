import streamlit as st
import pandas as pd
import requests
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
    background:#090d1a;
}

h1,h2,h3,p,label,div,span {
    color:#f8fafc !important;
}

.block-container {
    padding-top:1.3rem;
    max-width:1800px;
}

.metric {
    background:#111827;
    border:1px solid #263244;
    border-radius:16px;
    padding:14px 16px;
    min-height:72px;
}

.metric-title {
    color:#94a3b8 !important;
    font-size:13px;
    margin-bottom:6px;
}

.metric-text {
    color:#f8fafc !important;
    font-size:18px;
    font-weight:800;
}

.section-title {
    margin-top:22px;
    margin-bottom:12px;
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

.badge-new {
    color:#f97316 !important;
    font-weight:900;
    font-size:13px;
}

.badge-up {
    color:#22c55e !important;
    font-weight:900;
    font-size:13px;
}

.badge-down {
    color:#ef4444 !important;
    font-weight:900;
    font-size:13px;
}

.side-card {
    background:#0f172a;
    border:1px solid #1e293b;
    border-radius:12px;
    padding:9px 11px;
    margin-bottom:8px;
}

.small {
    color:#94a3b8 !important;
    font-size:12px;
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

[data-baseweb="select"] * {
    color:#111827 !important;
}

[data-baseweb="popover"] * {
    color:#111827 !important;
    background:#ffffff !important;
}

input {
    color:#111827 !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown(
    "<h1>🎬 키노라이츠 랭킹 / OTT 편성 검색</h1>",
    unsafe_allow_html=True
)

OTT_NAMES = [
    "넷플릭스",
    "티빙",
    "웨이브",
    "디즈니+",
    "쿠팡플레이",
    "왓챠",
    "애플TV+",
    "라프텔"
]

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
                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=20000
                )

                page.wait_for_timeout(1200)

                text = page.locator("body").inner_text()

                if "보러가기" not in text:
                    continue

                section = text.split("보러가기", 1)[1]

                if "시청 주의 가이드" in section:
                    section = section.split(
                        "시청 주의 가이드",
                        1
                    )[0]

                for ott in OTT_NAMES:
                    if ott in section:
                        found.append(ott)

                if found:
                    break

            except Exception:
                continue

        browser.close()

    return sorted(set(found))

def make_meta(row):

    media_type = str(
        row.get("media_type", "")
    ).upper()

    genres = str(
        row.get("genres", "")
    ).replace(",", "/")

    open_year = str(
        row.get("open_year", "")
    )

    type_text = ""

    if media_type == "MOVIE":
        type_text = "영화"

    elif media_type in [
        "TV",
        "SHOW",
        "SERIES",
        "DRAMA"
    ]:
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

tab1, tab2 = st.tabs([
    "📈 랭킹 대시보드",
    "🔎 OTT 제공처 검색"
])

with tab1:

    file = Path("ranking_history.csv")

    if not file.exists():
        st.error(
            "ranking_history.csv가 없습니다."
        )
        st.stop()

    df = pd.read_csv(file)

    if df.empty:
        st.error(
            "수집된 랭킹 데이터가 없습니다."
        )
        st.stop()

    for col in [
        "providers",
        "genres",
        "open_year",
        "media_type"
    ]:
        if col not in df.columns:
            df[col] = ""

    df["date"] = df["date"].astype(str)
    df["period"] = df["period"].astype(str)
    df["title"] = df["title"].astype(str)

    df["providers"] = (
        df["providers"]
        .fillna("")
        .astype(str)
    )

    df["genres"] = (
        df["genres"]
        .fillna("")
        .astype(str)
    )

    df["open_year"] = (
        df["open_year"]
        .fillna("")
        .astype(str)
    )

    df["media_type"] = (
        df["media_type"]
        .fillna("")
        .astype(str)
    )

    df["rank"] = pd.to_numeric(
        df["rank"],
        errors="coerce"
    )

    df["delta"] = pd.to_numeric(
        df["delta"],
        errors="coerce"
    ).fillna(0)

    df["is_new"] = (
        df["is_new"]
        .astype(str)
        .str.lower()
        .isin(["true", "1"])
    )

    latest_date = sorted(
        df["date"].unique(),
        reverse=True
    )[0]

    latest = df[
        df["date"] == latest_date
    ].copy()

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

        st.markdown(f"""
        <div class="metric">
            <div class="metric-title">
                기준일
            </div>

            <div class="metric-text">
                {latest_date}
            </div>
        </div>
        """, unsafe_allow_html=True)

    base = latest[
        latest["period"] == selected_period
    ].copy()

    if selected_ott != "전체":

        base = base[
            base["providers"]
            .str.contains(selected_ott, na=False)
        ].copy()

    base = base.sort_values("rank")

    new_df = base[
        base["is_new"] == True
    ].copy()

    up_df = (
        base[base["delta"] > 0]
        .copy()
        .sort_values("delta", ascending=False)
    )

    col1, col2, col3 = st.columns([1.15, 1, 1])

    # 전체 TOP100
    with col1:

        st.markdown(
            f"<div class='section-title'><h2>🏆 {selected_ott} {selected_period} TOP100</h2></div>",
            unsafe_allow_html=True
        )

        if base.empty:

            st.warning("데이터 없음")

        else:

            for _, row in base.head(100).iterrows():

                if row["is_new"]:

                    badge = '''
                    <span class="badge-new">
                        NEW
                    </span>
                    '''

                elif row["delta"] > 0:

                    badge = f'''
                    <span class="badge-up">
                        ▲{int(row["delta"])}
                    </span>
                    '''

                elif row["delta"] < 0:

                    badge = f'''
                    <span class="badge-down">
                        ▼{abs(int(row["delta"]))}
                    </span>
                    '''

                else:

                    badge = ""

                meta = make_meta(row)

                st.markdown(f"""
                <div class="rank-card">

                    <div class="rank-left">

                        <div class="rank-num">
                            {int(row["rank"])}
                        </div>

                        <div>

                            <div class="title">
                                {row["title"]}
                            </div>

                            <div class="meta">
                                {meta}
                            </div>

                        </div>

                    </div>

                    <div>
                        {badge}
                    </div>

                </div>
                """, unsafe_allow_html=True)

    # 급상승
    with col2:

        st.markdown(
            "<div class='section-title'><h2>🚀 급상승 콘텐츠</h2></div>",
            unsafe_allow_html=True
        )

        if up_df.empty:

            st.info("급상승 콘텐츠 없음")

        else:

            for _, row in up_df.head(30).iterrows():

                meta = make_meta(row)

                st.markdown(f"""
                <div class="side-card">

                    <span class="badge-up">
                        ▲{int(row["delta"])}
                    </span>

                    &nbsp;

                    <b>
                        {row["title"]}
                    </b>

                    <br>

                    <span class="small">
                        #{int(row["rank"])}
                        ·
                        {meta}
                    </span>

                </div>
                """, unsafe_allow_html=True)

    # 신규 진입
    with col3:

        st.markdown(
            "<div class='section-title'><h2>🔥 신규 진입 콘텐츠</h2></div>",
            unsafe_allow_html=True
        )

        if new_df.empty:

            st.info("신규 진입 콘텐츠 없음")

        else:

            for _, row in new_df.head(30).iterrows():

                meta = make_meta(row)

                st.markdown(f"""
                <div class="side-card">

                    <span class="badge-new">
                        NEW
                    </span>

                    &nbsp;

                    #{int(row["rank"])}

                    &nbsp;

                    <b>
                        {row["title"]}
                    </b>

                    <br>

                    <span class="small">
                        {meta}
                    </span>

                </div>
                """, unsafe_allow_html=True)

with tab2:

    st.subheader(
        "🔎 타이틀로 OTT 제공처 검색"
    )

    keyword = st.text_input(
        "작품명을 입력하세요",
        placeholder="예: 멋진 신세계"
    )

    if keyword:

        with st.spinner(
            "키노라이츠에서 정액제 제공처 확인 중..."
        ):

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

                provider_html = "".join([
                    f'<span class="ott-badge">{p}</span>'
                    for p in providers
                ])

            else:

                provider_html = '''
                <span class="small">
                    정액제 OTT 없음
                </span>
                '''

            st.markdown(f"""
            <div class="side-card">

                <h3>
                    {title}
                </h3>

                <div class="small">
                    연도: {open_year}
                </div>

                <div style="margin-top:10px;">
                    {provider_html}
                </div>

            </div>
            """, unsafe_allow_html=True)

            with st.expander(
                "다른 검색 후보 보기"
            ):

                for other in results[1:]:

                    st.markdown(
                        f"- {other.get('titleKr')} ({other.get('openYear')})"
                    )
