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
      id
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

    print("PERIOD:", period_kr)
    print("STATUS:", res.status_code)
    print("TEXT HEAD:", res.text[:300])

    if res.status_code != 200 or not res.text.strip().startswith("{"):
        continue

    data = res.json()

    if "errors" in data:
        print("GRAPHQL ERRORS:", data["errors"])
        continue

    items = data["data"]["contentRankings"]

    for idx, item in enumerate(items, start=1):
        content = item["content"]

        providers = []
        for offer in content.get("vodOfferItems", []):
            if offer.get("isActive"):
                pid = str(offer.get("providerId"))
                if pid in PROVIDER_MAP:
                    providers.append(PROVIDER_MAP[pid])

rows.append({
    "date": today,
    "period": period_kr,
    "rank": idx,
    "title": content.get("titleKr"),
    "content_id": content.get("id"),
    "media_type": content.get("mediaType"),
    "genres": ",".join(content.get("genres") or []),
    "open_year": content.get("openYear"),
    "is_new": item.get("isNew"),
    "delta": item.get("delta"),
    "providers": ",".join(sorted(set(providers)))
})

if not rows:
    raise Exception("랭킹 데이터를 수집하지 못했습니다.")

new_df = pd.DataFrame(rows)

csv_path = Path("ranking_history.csv")

if csv_path.exists():
    old = pd.read_csv(csv_path)

    if "media_type" not in old.columns:
        old["media_type"] = ""

    df = pd.concat([old, new_df], ignore_index=True)

    df = df.drop_duplicates(
        subset=["date", "period", "rank"],
        keep="last"
    )
else:
    df = new_df

df.to_csv(csv_path, index=False, encoding="utf-8-sig")

print(new_df.head(30))
