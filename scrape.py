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
    "350": "애플TV+",
    "21": "라프텔"
}

QUERY = """
query QueryRanking($rankingType: ContentRankingType!, $limit: Int = 100) {
  contentRankings(rankingType: $rankingType, limit: $limit) {
    content {
      titleKr
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
        headers={"Content-Type": "application/json"},
        timeout=30
    )

    data = res.json()

    items = data["data"]["contentRankings"]

    for idx, item in enumerate(items, start=1):

        content = item["content"]

        provider_ids = []

        for offer in content.get("vodOfferItems", []):
            if offer.get("isActive"):
                provider_ids.append(
                    str(offer.get("providerId"))
                )

        providers = []

        for pid in provider_ids:
            if pid in PROVIDER_MAP:
                providers.append(PROVIDER_MAP[pid])

        rows.append({
            "date": today,
            "period": period_kr,
            "rank": idx,
            "title": content.get("titleKr"),
            "is_new": item.get("isNew"),
            "delta": item.get("delta"),
            "providers": ",".join(sorted(set(providers)))
        })

new_df = pd.DataFrame(rows)

csv_path = Path("ranking_history.csv")

if csv_path.exists():
    old = pd.read_csv(csv_path)

    df = pd.concat([old, new_df], ignore_index=True)

    df = df.drop_duplicates(
        subset=["date", "period", "rank"],
        keep="last"
    )
else:
    df = new_df

df.to_csv(
    csv_path,
    index=False,
    encoding="utf-8-sig"
)

print(df.head())
