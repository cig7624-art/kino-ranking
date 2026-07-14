import requests
import pandas as pd
from datetime import datetime

API_URL = "https://gateway.kinolights.com/graphql"

PERIODS = {
    "일간": "DAILY",
    "주간": "WEEKLY",
    "월간": "MONTHLY"
}

# 키노라이츠 개편 후 providerId 기준
# 랭킹 화면 기준: 넷플릭스 / 티빙 / 쿠팡플레이 / 웨이브 / 디즈니+ / 왓챠
PROVIDER_MAP = {
    "4": "넷플릭스",
    "8": "웨이브",
    "10": "티빙",
    "14": "쿠팡플레이",
    "5": "왓챠",
    "17": "디즈니+",
}

QUERY = """
query QueryRanking($rankingType: ContentRanking!, $limit: Int = 100) {
  contentRankings(rankingType: $rankingType, limit: $limit) {
    content {
      titleKr
      mediaType
      genres
      openYear
      vodOfferItems {
        providerId
        isActive
      }
    }
    delta
    isNew
  }
}
"""


def normalize_genres(genres):
    if not genres:
        return ""

    if isinstance(genres, list):
        return ",".join([str(g) for g in genres if g])

    return str(genres)


def fetch_ranking(period_kr, period_api):
    payload = {
        "operationName": "QueryRanking",
        "variables": {
            "limit": 100,
            "rankingType": period_api
        },
        "query": QUERY
    }

    res = requests.post(
        API_URL,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Origin": "https://m.kinolights.com",
            "Referer": "https://m.kinolights.com/ranking/kino"
        },
        timeout=30
    )

    print(period_kr, res.status_code, res.text[:200])

    if res.status_code != 200 or not res.text.strip().startswith("{"):
        return []

    data = res.json()

    if "errors" in data:
        print(period_kr, data["errors"])
        return []

    items = data.get("data", {}).get("contentRankings", []) or []

    print(period_kr, "items:", len(items))

    return items


today = datetime.today().strftime("%Y-%m-%d")
rows = []
provider_debug_rows = []

for period_kr, period_api in PERIODS.items():
    items = fetch_ranking(period_kr, period_api)

    for idx, item in enumerate(items, start=1):
        content = item.get("content") or {}

        title = content.get("titleKr")
        media_type = content.get("mediaType")
        genres = normalize_genres(content.get("genres"))
        open_year = content.get("openYear")

        providers = []

        for offer in content.get("vodOfferItems", []) or []:
            pid = str(offer.get("providerId"))
            is_active = offer.get("isActive")
            mapped_name = PROVIDER_MAP.get(pid, "")

            provider_debug_rows.append({
                "date": today,
                "period": period_kr,
                "rank": idx,
                "title": title,
                "providerId": pid,
                "providerNameMapped": mapped_name,
                "isActive": is_active,
                "raw_offer": str(offer)
            })

            if is_active and mapped_name:
                providers.append(mapped_name)

        rows.append({
            "date": today,
            "period": period_kr,
            "rank": idx,
            "title": title,
            "media_type": media_type,
            "genres": genres,
            "open_year": open_year,
            "is_new": item.get("isNew"),
            "delta": item.get("delta"),
            "providers": ",".join(sorted(set(providers)))
        })

if not rows:
    raise Exception("랭킹 데이터를 수집하지 못했습니다.")

df = pd.DataFrame(rows)

df.to_csv(
    "ranking_history.csv",
    index=False,
    encoding="utf-8-sig"
)

provider_debug_df = pd.DataFrame(provider_debug_rows)

provider_debug_df.to_csv(
    "debug_provider_ids.csv",
    index=False,
    encoding="utf-8-sig"
)

print("ranking_history.csv 저장 완료")
print(df.head(20))

print("debug_provider_ids.csv 저장 완료")
print(provider_debug_df.head(80))

print("providerId counts")
print(
    provider_debug_df
    .groupby(["providerId", "providerNameMapped"])
    .size()
    .reset_index(name="count")
    .sort_values("count", ascending=False)
)
