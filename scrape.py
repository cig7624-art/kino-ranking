import requests
import pandas as pd
from datetime import datetime
from pathlib import Path

API_URL = "https://gateway.kinolights.com/graphql"

PERIODS = {
    "일간": "DAILY",
    "주간": "WEEKLY",
    "월간": "MONTHLY"
}

PROVIDER_MAP = {
    "8": "넷플릭스",
    "119": "티빙",
    "356": "웨이브",
    "337": "디즈니+",
    "128": "쿠팡플레이",
    "97": "왓챠",
    "10": "영화관",
    "350": "애플TV+",
    "11": "네이버 시리즈온",
    "12": "구글플레이",
    "13": "유튜브",
    "20": "U+모바일tv",
    "21": "라프텔"
}

OTT_ONLY = [
    "넷플릭스",
    "티빙",
    "웨이브",
    "디즈니+",
    "쿠팡플레이",
    "왓챠",
    "애플TV+",
    "라프텔"
]

QUERY = """
query QueryRanking($rankingType: ContentRankingType!, $limit: Int = 100) {
  contentRankings(rankingType: $rankingType, limit: $limit) {
    content {
      id
      titleKr
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

headers = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0"
}

today = datetime.today().strftime("%Y-%m-%d")
rows = []

for period_kr, period_api in PERIODS.items():
    payload = {
        "operationName": "QueryRanking",
        "variables": {
            "limit": 100,
            "rankingType": period_api
        },
        "query": QUERY
    }

    res = requests.post(API_URL, json=payload, headers=headers, timeout=30)
    res.raise_for_status()

    data = res.json()
    items = data["data"]["contentRankings"]

    for idx, item in enumerate(items, start=1):
        content = item["content"]

        provider_ids = []

        for offer in content.get("vodOfferItems", []):
            if offer.get("isActive"):
                provider_ids.append(str(offer.get("providerId")))

        all_providers = [
            PROVIDER_MAP.get(pid, f"provider_{pid}")
            for pid in provider_ids
        ]

        ott_providers = [
            x for x in all_providers
            if x in OTT_ONLY
        ]

        is_theater = "영화관" in all_providers

        rows.append({
            "date": today,
            "period": period_kr,
            "rank": idx,
            "title": content.get("titleKr"),
            "content_id": content.get("id"),
            "genres": ",".join(content.get("genres") or []),
            "open_year": content.get("openYear"),
            "is_new": item.get("isNew"),
            "delta": item.get("delta"),
            "providers": ",".join(sorted(set(ott_providers))),
            "is_theater": is_theater
        })

new_df = pd.DataFrame(rows)

csv_path = Path("ranking_history.csv")

if csv_path.exists():
    old = pd.read_csv(csv_path)

    if "is_theater" not in old.columns:
        old["is_theater"] = False

    df = pd.concat([old, new_df], ignore_index=True)

    df = df.drop_duplicates(
        subset=["date", "period", "rank"],
        keep="last"
    )
else:
    df = new_df

df.to_csv(csv_path, index=False, encoding="utf-8-sig")

print(new_df.head(30))
