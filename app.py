import streamlit as st
import pandas as pd
import requests
from pathlib import Path

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
    "8": "넷플릭스",
    "119": "티빙",
    "356": "웨이브",
    "337": "디즈니+",
    "128": "쿠팡플레이",
    "97": "왓챠",
    "350": "애플TV+",
    "21": "라프텔",
}

tab1, tab2 = st.tabs(["📈 랭킹 대시보드", "🔎 OTT 제공처 검색"])

with tab2:
    st.subheader("🔎 타이틀로 OTT 제공처 검색")

    keyword = st.text_input(
        "작품명을 입력하세요",
        placeholder="예: 멋진 신세계"
    )

    SEARCH_QUERY = """
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

    DETAIL_QUERY = """
    query ContentDetail($id: ID!) {
      content(id: $id) {
        id
        titleKr
        openYear
        genres
        vodOfferItems {
          providerId
          isActive
        }
      }
    }
    """

    if keyword:
        try:
            search_payload = {
                "operationName": "SearchContents",
                "variables": {"keyword": keyword},
                "query": SEARCH_QUERY,
            }

            search_res = requests.post(
                "https://gateway.kinolights.com/graphql",
                json=search_payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0",
                },
                timeout=20,
            )

            search_data = search_res.json()

            if "errors" in search_data:
                st.error(search_data["errors"])
                st.stop()

            items = search_data["data"]["contents"]

            if len(items) == 0:
                st.warning("검색 결과 없음")
                st.stop()

            for item in items:
                content_id = item["id"]

                detail_payload = {
                    "operationName": "ContentDetail",
                    "variables": {"id": content_id},
                    "query": DETAIL_QUERY,
                }

                detail_res = requests.post(
                    "https://gateway.kinolights.com/graphql",
                    json=detail_payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Mozilla/5.0",
                    },
                    timeout=20,
                )

                detail_data = detail_res.json()

                if "errors" in detail_data:
                    node = item
                    offers = []
                else:
                    node = detail_data["data"]["content"]
                    offers = node.get("vodOfferItems", [])

                provider_ids = []

                for offer in offers:
                    if offer.get("isActive"):
                        provider_ids.append(str(offer.get("providerId")))

                otts = []

                for pid in provider_ids:
                    if pid in PROVIDER_MAP:
                        otts.append(PROVIDER_MAP[pid])

                otts = sorted(set(otts))

                providers = ", ".join(otts) if otts else "OTT 정보 없음"
                genres = ", ".join(node.get("genres") or [])

                st.markdown(f"""
                <div class="card">
                    <b>{node.get('titleKr')}</b><br>
                    <span class="small">
                        제공 OTT: {providers}<br>
                        장르: {genres} · 연도: {node.get('openYear')}
                    </span>
                </div>
                """, unsafe_allow_html=True)

        except Exception as e:
            st.error(str(e))
