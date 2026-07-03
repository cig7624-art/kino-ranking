import requests
import pandas as pd
from datetime import datetime

API_URL = "https://gateway.kinolights.com/graphql"

PERIODS = {
    "일간": "DAILY",
    "주간": "WEEKLY",
    "월간": "MONTHLY"
}

# 임시 매핑: 현재 debug 기준으로 4는 넷플릭스로 확인됨
# 나머지는 debug_provider_ids.csv 확인 후 확정
PROVIDER_MAP = {
    "4": "넷플릭스",
    "10": "",
    "14": "",
    "16": "",
    "17": "",
    "8": "",
}

QUERY = """
query QueryRanking($rankingType: ContentRankingType!, $limit: Int = 100) {
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

today = datetime.today().strftime("%Y-%m-%d")
rows = []
provider_debug_rows = []

for period_kr, period_api in PERIODS.items():
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
        continue

    data = res.json()

    if "errors" in data:
        print(period_kr, data["errors"])
        continue

    items = data.get("data", {}).get("contentRankings", []) or []

    print(period_kr, "items:", len(items))

    for idx, item in enumerate(items, start=1):
        content = item.get("content") or {}

        title = content.get("titleKr")
        media_type = content.get("mediaType")
        genres = content.get("genres") or []
        open_year = content.get("openYear")

        if isinstance(genres, list):
            genre_text = ",".join([str(g) for g in genres])
        else:
            genre_text = str(genres)

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
            "genres": genre_text,
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
