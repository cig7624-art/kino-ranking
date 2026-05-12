import streamlit as st
import pandas as pd
import requests
import subprocess
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

st.set_page_config(
    page_title="키노라이츠 랭킹/OTT 검색",
    page_icon="🎬",
    layout="wide"
)

st.markdown("""
<style>
.stApp { background:#0f172a; }
h1,h2,h3,p,label,div,span { color:#f8fafc !important; }
.block-container { padding-top:1.5rem; }

.card {
    background:#111827;
    border:1px solid #334155;
    border-radius:12px;
    padding:10px 14px;
    margin-bottom:7px;
}

.rank { color:#38bdf8 !important; font-weight:900; }
.new { color:#f97316 !important; font-weight:900; }
.up { color:#22c55e !important; font-weight:900; }
.down { color:#ef4444 !important; font-weight:900; }

.small {
    color:#94a3b8 !important;
    font-size:12px;
}

.metric {
    background:#1e293b;
    border:1px solid #334155;
    border-radius:16px;
    padding:16px;
}

.metric-num {
    color:#38bdf8 !important;
    font-size:32px;
    font-weight:900;
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

PROVIDER_MAP = {
    "8": "넷플릭스",
    "119": "티빙",
    "356": "웨이브",
    "337": "디즈니+",
    "128": "쿠팡플레이",
    "97": "왓챠",
    "350": "애플TV+",
    "21": "라프텔",
}

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


def search_kino_contents(keyword):
    query = """
    query SearchContents($keyword: String!) {
      contents(
        keyword: $keyword
        limit: 10
      ) {
        id
        titleKr
        openYear
        genres
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

def get_subscription_providers_from_page(content_id):

    urls = [
        f"https://m.kinolights.com/title/{content_id}",
        f"https://m.kinolights.com/content/{content_id}",
        f"https://m.kinolights.com/contents/{content_id}",
    ]

    providers = []

  with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        executable_path="/usr/bin/chromium"
    )

    page = browser.new_page(
        viewport={"width": 430, "height": 1600},
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
    )

        for url in urls:
            try:
                page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=30000
                )

                page.wait_for_timeout(3000)

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
                        providers.append(ott)

                if providers:
                    break

            except Exception:
                continue

        browser.close()

    return sorted(set(providers))

tab1, tab2 = st.tabs([
    "📈 랭킹 대시보드",
    "🔎 OTT 제공처 검색"
])

with tab1:
    file = Path("ranking_history.csv")

    if not file.exists():
        st.error(
            "ranking_history.csv가 없습니다. "
            "먼저 Actions에서 수집을 실행하세요."
        )
        st.stop()

    df = pd.read_csv(file)

    if df.empty:
        st.error("수집된 데이터가 없습니다.")
        st.stop()

    if "is_theater" not in df.columns:
        df["is_theater"] = False

    df["date"] = df["date"].astype(str)
    df["period"] = df["period"].astype(str)
    df["title"] = df["title"].astype(str)
    df["providers"] = df["providers"].fillna("").astype(str)

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

    df["is_theater"] = (
        df["is_theater"]
        .astype(str)
        .str.lower()
        .isin(["true", "1"])
    )

    latest_date = sorted(
        df["date"].unique(),
        reverse=True
    )[0]

    latest = df[df["date"] == latest_date].copy()

    c1, c2 = st.columns(2)

    with c1:
        selected_period = st.selectbox(
            "기간 선택",
            ["일간", "주간", "월간"],
            index=1
        )

    with c2:
        selected_ott = st.selectbox(
            "OTT 선택",
            [
                "전체",
                "넷플릭스",
                "티빙",
                "웨이브",
                "디즈니+",
                "쿠팡플레이",
                "왓챠",
                "애플TV+",
                "라프텔",
                "극장상영"
            ],
            index=0
        )

    base = latest[
        latest["period"] == selected_period
    ].copy()

    if selected_ott == "극장상영":
        base = base[
            base["is_theater"] == True
        ]
    elif selected_ott != "전체":
        base = base[
            base["providers"]
            .str.contains(selected_ott, na=False)
        ]

    base = base.sort_values("rank")

    new_df = base[
        base["is_new"] == True
    ]

    up_df = (
        base[base["delta"] > 0]
        .sort_values("delta", ascending=False)
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"""
        <div class="metric">
            <div>신규 진입 콘텐츠</div>
            <div class="metric-num">{len(new_df)}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric">
            <div>급상승 콘텐츠</div>
            <div class="metric-num">{len(up_df)}</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric">
            <div>표시 기준</div>
            <div class="metric-num">{selected_period}</div>
            <div class="small">{selected_ott}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    left, right = st.columns([1.3, 1])

    with left:
        st.subheader(
            f"🏆 {selected_ott} {selected_period} TOP100"
        )

        for _, row in base.head(100).iterrows():
            if row["is_new"]:
                badge = '<span class="new">NEW</span>'
            elif row["delta"] > 0:
                badge = f'<span class="up">▲{int(row["delta"])}</span>'
            elif row["delta"] < 0:
                badge = f'<span class="down">▼{abs(int(row["delta"]))}</span>'
            else:
                badge = '<span class="small">-</span>'

            providers = (
                row["providers"]
                if row["providers"]
                else "OTT 없음"
            )

            theater_badge = (
                " · 🎬 극장상영"
                if row["is_theater"]
                else ""
            )

            st.markdown(f"""
            <div class="card">
                <span class="rank">
                    #{int(row['rank'])}
                </span>
                &nbsp;
                <b>{row['title']}</b>
                &nbsp;
                {badge}<br>

                <span class="small">
                    {providers}{theater_badge}
                </span>
            </div>
            """, unsafe_allow_html=True)

    with right:
        st.subheader("🔥 신규 진입 콘텐츠")

        for _, row in new_df.head(20).iterrows():
            providers = (
                row["providers"]
                if row["providers"]
                else "OTT 없음"
            )

            theater_badge = (
                " · 🎬 극장상영"
                if row["is_theater"]
                else ""
            )

            st.markdown(f"""
            <div class="card">
                <span class="new">NEW</span>
                &nbsp;
                #{int(row['rank'])}
                &nbsp;
                <b>{row['title']}</b><br>

                <span class="small">
                    {providers}{theater_badge}
                </span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        st.subheader("🚀 급상승 콘텐츠")

        for _, row in up_df.head(20).iterrows():
            providers = (
                row["providers"]
                if row["providers"]
                else "OTT 없음"
            )

            theater_badge = (
                " · 🎬 극장상영"
                if row["is_theater"]
                else ""
            )

            st.markdown(f"""
            <div class="card">
                <span class="up">
                    ▲{int(row['delta'])}
                </span>
                &nbsp;
                <b>{row['title']}</b><br>

                <span class="small">
                    #{int(row['rank'])}
                    ·
                    {providers}{theater_badge}
                </span>
            </div>
            """, unsafe_allow_html=True)

with tab2:
    st.subheader("🔎 타이틀로 OTT 제공처 검색")

    keyword = st.text_input(
        "작품명을 입력하세요",
        placeholder="예: 멋진 신세계"
    )

    if keyword:
        with st.spinner(
            "키노라이츠에서 정액제 제공처 확인 중..."
        ):
            results = search_kino_contents(keyword)

            if not results:
                st.warning("검색 결과가 없습니다.")
                st.stop()

            for item in results:
                content_id = item.get("id")
                title = item.get("titleKr")
                open_year = item.get("openYear")

                genres = ", ".join(
                    item.get("genres") or []
                )

                providers = (
                    get_subscription_providers_from_page(
                        content_id
                    )
                )

                if providers:
                    provider_text = ", ".join(providers)
                else:
                    provider_text = (
                        "정액제 제공처 없음 또는 확인 실패"
                    )

                st.markdown(f"""
                <div class="card">
                    <b>{title}</b><br>

                    <span class="small">
                        정액제 제공처:
                        {provider_text}<br>

                        장르:
                        {genres}
                        ·
                        연도:
                        {open_year}
                    </span>
                </div>
                """, unsafe_allow_html=True)
