import streamlit as st
import pandas as pd
import requests
import subprocess
import sys
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
.small { color:#94a3b8 !important; font-size:12px; }

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

[data-baseweb="select"] * { color:#111827 !important; }
[data-baseweb="popover"] * {
    color:#111827 !important;
    background:#ffffff !important;
}
input { color:#111827 !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>🎬 키노라이츠 랭킹 / OTT 편성 검색</h1>", unsafe_allow_html=True)

PROVIDER_MAP = {
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

@st.cache_resource
def install_playwright_browser():
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=False
    )

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
    install_playwright_browser()

    urls = [
        f"https://m.kinolights.com/title/{content_id}",
        f"https://m.kinolights.com/content/{content_id}",
        f"https://m.kinolights.com/contents/{content_id}",
    ]

    providers = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            viewport={"width": 430, "height": 1600},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
        )

        for url in urls:
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                text = page.locator("body").inner_text()

                if "보러가기" not in text:
                    continue

                section = text.split("보러가기", 1)[1]

                if "시청 주의 가이드" in section:
                    section = section.split("시청 주의 가이드", 1)[0]

                for ott in OTT_NAMES:
                    if ott in section:
                        providers.append(ott)

                if providers:
                    break

            except Exception:
                continue

        browser.close()

    return sorted(set(providers))

with tab2:
    st.subheader("🔎 타이틀로 OTT 제공처 검색")

    keyword = st.text_input(
        "작품명을 입력하세요",
        placeholder="예: 멋진 신세계"
    )

    if keyword:
        with st.spinner("키노라이츠에서 제공처 확인 중..."):
            results = search_kino_contents(keyword)

            if not results:
                st.warning("검색 결과가 없습니다.")
                st.stop()

            for item in results:
                content_id = item.get("id")
                title = item.get("titleKr")
                open_year = item.get("openYear")
                genres = ", ".join(item.get("genres") or [])

                providers = get_subscription_providers_from_page(content_id)

                if providers:
                    provider_text = ", ".join(providers)
                else:
                    provider_text = "정액제 제공처 없음 또는 확인 실패"

                st.markdown(f"""
                <div class="card">
                    <b>{title}</b><br>
                    <span class="small">
                        정액제 제공처: {provider_text}<br>
                        장르: {genres} · 연도: {open_year}
                    </span>
                </div>
                """, unsafe_allow_html=True)
