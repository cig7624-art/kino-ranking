import streamlit as st
import requests
from playwright.sync_api import sync_playwright

st.set_page_config(
    page_title="OTT 제공처 검색",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background:#0f172a;
    color:white;
}

h1, h2, h3, p, label, div, span {
    color:#f8fafc !important;
}

.card{
    background:#111827;
    border:1px solid #334155;
    border-radius:12px;
    padding:14px;
    margin-bottom:10px;
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

.small{
    color:#94a3b8 !important;
    font-size:13px;
}

input {
    color:#111827 !important;
}
</style>
""", unsafe_allow_html=True)

st.title("🎬 키노라이츠 OTT 제공처 검색")

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
      contents(
        keyword: $keyword
        limit: 5
      ) {
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
                    wait_until="networkidle",
                    timeout=25000
                )

                page.wait_for_timeout(1800)

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


keyword = st.text_input(
    "작품명을 입력하세요",
    placeholder="예: 멋진 신세계"
)

if keyword:
    with st.spinner("OTT 제공처 확인 중..."):
        results = search_contents(keyword)

        if not results:
            st.warning("검색 결과 없음")
            st.stop()

        # 속도 개선: 첫 번째 검색 결과만 상세 조회
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
        <div class="card">
            <h3>{title}</h3>
            <div class="small">연도: {open_year}</div>
            <div style="margin-top:10px;">
                {provider_html}
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("다른 검색 후보 보기"):
            for other in results[1:]:
                st.markdown(
                    f"- {other.get('titleKr')} ({other.get('openYear')})"
                )
