with tab2:
    import requests

    st.subheader("🔎 타이틀로 OTT 제공처 검색")

    keyword = st.text_input(
        "작품명을 입력하세요",
        placeholder="예: 멋진 신세계"
    )

    SEARCH_QUERY = """
    query SearchContents($keyword: String!) {
      searchContents(keyword: $keyword) {
        edges {
          node {
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
      }
    }
    """

    PROVIDER_MAP = {
        "8": "넷플릭스",
        "119": "티빙",
        "356": "웨이브",
        "337": "디즈니+",
        "128": "쿠팡플레이",
        "97": "왓챠",
        "350": "애플TV+",
        "21": "라프텔"
    }

    if keyword:
        payload = {
            "operationName": "SearchContents",
            "variables": {
                "keyword": keyword
            },
            "query": SEARCH_QUERY
        }

        try:
            res = requests.post(
                "https://gateway.kinolights.com/graphql",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0"
                },
                timeout=20
            )

            # 응답 확인용
            st.write("STATUS:", res.status_code)
            st.write("RAW RESPONSE:")
            st.code(res.text)

            st.stop()

            data = res.json()

            items = data["data"]["searchContents"]["edges"]

            if len(items) == 0:
                st.warning("검색 결과 없음")

            else:
                for item in items[:10]:
                    node = item["node"]

                    provider_ids = []

                    for offer in node.get("vodOfferItems", []):
                        if offer.get("isActive"):
                            provider_ids.append(
                                str(offer.get("providerId"))
                            )

                    otts = []

                    for pid in provider_ids:
                        if pid in PROVIDER_MAP:
                            otts.append(PROVIDER_MAP[pid])

                    otts = sorted(set(otts))

                    providers = ", ".join(otts)

                    if not providers:
                        providers = "OTT 정보 없음"

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
