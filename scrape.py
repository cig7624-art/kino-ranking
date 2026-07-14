import pandas as pd
import requests
from datetime import datetime
from pathlib import Path


GRAPHQL_URL = "https://gateway.kinolights.com/graphql"

OUTPUT_FILE = Path("ranking_history.csv")
DEBUG_PROVIDER_FILE = Path("debug_provider_ids.csv")

PROVIDER_MAP = {
    "4": "넷플릭스",
    "8": "웨이브",
    "10": "티빙",
    "14": "쿠팡플레이",
    "16": "디즈니+",
    "5": "왓챠",
}

PERIOD_MAP = {
    "DAILY": "일간",
    "WEEKLY": "주간",
    "MONTHLY": "월간",
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


def is_bad_title(title):
    title = str(title or "").strip()

    if title == "":
        return True

    if title == "%":
        return True

    if title.replace(".", "", 1).isdigit():
        return True

    if title in [
        "홈",
        "랭킹",
        "탐색",
        "혜택",
        "마이페이지",
        "전체",
        "정액제",
        "무료",
        "대여",
        "구매",
    ]:
        return True

    return False


def get_providers(vod_offer_items):
    providers = []
    debug_ids = []

    if not vod_offer_items:
        return "", ""

    for item in vod_offer_items:
        provider_id = str(item.get("providerId", "")).strip()
        is_active = item.get("isActive", True)

        debug_ids.append(provider_id)

        if not is_active:
            continue

        provider_name = PROVIDER_MAP.get(provider_id)

        if provider_name:
            providers.append(provider_name)

    providers = list(dict.fromkeys(providers))
    debug_ids = list(dict.fromkeys(debug_ids))

    return ",".join(providers), ",".join(debug_ids)


def fetch_ranking(ranking_type):
    payload = {
        "operationName": "QueryRanking",
        "variables": {
            "rankingType": ranking_type,
            "limit": 100,
        },
        "query": QUERY,
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
    }

    res = requests.post(
        GRAPHQL_URL,
        json=payload,
        headers=headers,
        timeout=30,
    )

    res.raise_for_status()

    data = res.json()

    if "errors" in data:
        raise Exception(data["errors"])

    return data.get("data", {}).get("contentRankings", []) or []


def scrape():
    today = datetime.today().strftime("%Y-%m-%d")

    rows = []
    debug_rows = []

    for ranking_type, period_name in PERIOD_MAP.items():
        print(f"Fetching {period_name} ranking...")

        items = fetch_ranking(ranking_type)

        for idx, item in enumerate(items, start=1):
            content = item.get("content") or {}

            title = str(content.get("titleKr") or "").strip()

            if is_bad_title(title):
                continue

            providers, provider_ids = get_providers(
                content.get("vodOfferItems") or []
            )

            genres = content.get("genres") or []

            if isinstance(genres, list):
                genres_text = ",".join([str(x) for x in genres])
            else:
                genres_text = str(genres or "")

            row = {
                "date": today,
                "period": period_name,
                "rank": idx,
                "title": title,
                "delta": item.get("delta", 0),
                "is_new": item.get("isNew", False),
                "providers": providers,
                "genres": genres_text,
                "open_year": content.get("openYear", ""),
                "media_type": content.get("mediaType", ""),
            }

            rows.append(row)

            debug_rows.append({
                "date": today,
                "period": period_name,
                "rank": idx,
                "title": title,
                "provider_ids": provider_ids,
                "providers": providers,
            })

    new_df = pd.DataFrame(rows)

    if new_df.empty:
        raise Exception("No ranking data collected. ranking_history.csv not updated.")

    # 기존 파일이 있으면 오늘자만 교체하고 과거 데이터는 유지
    if OUTPUT_FILE.exists():
        old_df = pd.read_csv(OUTPUT_FILE)

        if not old_df.empty and "date" in old_df.columns:
            old_df["date"] = old_df["date"].astype(str)
            old_df = old_df[old_df["date"] != today].copy()

            final_df = pd.concat([old_df, new_df], ignore_index=True)
        else:
            final_df = new_df
    else:
        final_df = new_df

    final_df = final_df.drop_duplicates(
        subset=["date", "period", "rank"],
        keep="last"
    )

    final_df = final_df.sort_values(
        ["date", "period", "rank"],
        ascending=[True, True, True]
    )

    final_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    debug_df = pd.DataFrame(debug_rows)
    debug_df.to_csv(
        DEBUG_PROVIDER_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print("ranking rows:", len(new_df))
    print(new_df.head(20).to_string(index=False))


if __name__ == "__main__":
    scrape()
