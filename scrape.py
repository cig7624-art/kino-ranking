import re
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
from playwright.sync_api import sync_playwright


RANKING_URL = "https://m.kinolights.com/ranking/kino"

OUTPUT_FILE = Path("ranking_history.csv")
DEBUG_JSON_FILE = Path("debug_ranking_network.json")
DEBUG_CANDIDATES_FILE = Path("debug_ranking_candidates.csv")

OTT_NAMES = [
    "넷플릭스",
    "티빙",
    "쿠팡플레이",
    "웨이브",
    "디즈니+",
    "왓챠",
    "라프텔",
    "Apple TV",
    "아마존 프라임 비디오",
    "씨네폭스",
]

BAD_TITLES = {
    "",
    "%",
    "홈",
    "랭킹",
    "탐색",
    "혜택",
    "마이페이지",
    "전체",
    "전체 랭킹",
    "박스오피스",
    "정액제",
    "무료",
    "대여",
    "구매",
    "더보기",
    "검색",
    "공유",
    "로그인",
    "가입",
}


def normalize_space(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def is_bad_title(title):
    title = normalize_space(title)

    if title in BAD_TITLES:
        return True

    if len(title) <= 1:
        return True

    if re.fullmatch(r"\d+", title):
        return True

    if re.fullmatch(r"\d+위", title):
        return True

    if re.fullmatch(r"\d+(\.\d+)?%?", title):
        return True

    if title in OTT_NAMES:
        return True

    return False


def find_title(obj):
    if not isinstance(obj, dict):
        return ""

    candidate_keys = [
        "titleKr",
        "title",
        "nameKr",
        "name",
        "contentTitle",
        "originalTitle",
    ]

    for key in candidate_keys:
        value = obj.get(key)

        if isinstance(value, str) and not is_bad_title(value):
            return normalize_space(value)

    nested_keys = [
        "content",
        "contents",
        "contentItem",
        "item",
        "movie",
        "season",
        "titleInfo",
    ]

    for key in nested_keys:
        value = obj.get(key)

        if isinstance(value, dict):
            title = find_title(value)

            if title:
                return title

    return ""


def find_rank(obj, default_rank):
    if not isinstance(obj, dict):
        return default_rank

    for key in ["rank", "ranking", "rankNo", "position", "order", "index"]:
        value = obj.get(key)

        try:
            if value is not None:
                rank = int(value)

                if 1 <= rank <= 300:
                    return rank
        except Exception:
            pass

    return default_rank


def find_delta(obj):
    if not isinstance(obj, dict):
        return 0

    for key in ["delta", "rankDelta", "rankingDelta", "change", "rankChange"]:
        value = obj.get(key)

        try:
            if value is not None:
                return int(value)
        except Exception:
            pass

    return 0


def find_is_new(obj):
    if not isinstance(obj, dict):
        return False

    for key in ["isNew", "new", "is_new", "isNewEntry"]:
        value = obj.get(key)

        if isinstance(value, bool):
            return value

        if str(value).lower() in ["true", "1", "y", "yes"]:
            return True

    return False


def find_meta(obj):
    if not isinstance(obj, dict):
        return "", "", ""

    target = obj

    for key in ["content", "contents", "contentItem", "item", "movie", "season"]:
        if isinstance(obj.get(key), dict):
            target = obj.get(key)
            break

    media_type = target.get("mediaType") or target.get("type") or ""
    open_year = target.get("openYear") or target.get("year") or ""

    genres = target.get("genres") or target.get("genre") or ""

    if isinstance(genres, list):
        genres = ",".join([str(x) for x in genres])
    else:
        genres = str(genres or "")

    return str(media_type or ""), genres, str(open_year or "")


def find_providers(obj):
    if not isinstance(obj, dict):
        return ""

    target = obj

    for key in ["content", "contents", "contentItem", "item", "movie", "season"]:
        if isinstance(obj.get(key), dict):
            target = obj.get(key)
            break

    found = []

    # provider name이 직접 들어온 경우
    raw_text = json.dumps(target, ensure_ascii=False)

    for ott in OTT_NAMES:
        if ott in raw_text:
            found.append(ott)

    # vodOfferItems 구조인 경우
    provider_map = {
        "4": "넷플릭스",
        "8": "웨이브",
        "10": "티빙",
        "14": "쿠팡플레이",
        "16": "디즈니+",
        "5": "왓챠",
    }

    vod_items = target.get("vodOfferItems") or target.get("offers") or []

    if isinstance(vod_items, list):
        for item in vod_items:
            if not isinstance(item, dict):
                continue

            provider_id = str(item.get("providerId") or item.get("id") or "").strip()
            provider_name = item.get("providerName") or item.get("name") or ""

            if provider_name:
                for ott in OTT_NAMES:
                    if ott in str(provider_name):
                        found.append(ott)

            if provider_id in provider_map:
                found.append(provider_map[provider_id])

    result = []

    for ott in OTT_NAMES:
        if ott in found and ott not in result:
            result.append(ott)

    return ",".join(result)


def collect_arrays(obj, path="root"):
    arrays = []

    if isinstance(obj, list):
        arrays.append((path, obj))

        for idx, item in enumerate(obj[:30]):
            arrays.extend(collect_arrays(item, f"{path}[{idx}]"))

    elif isinstance(obj, dict):
        for key, value in obj.items():
            arrays.extend(collect_arrays(value, f"{path}.{key}"))

    return arrays


def score_array(arr):
    if not isinstance(arr, list):
        return 0

    if len(arr) < 10:
        return 0

    score = 0

    for item in arr[:120]:
        if not isinstance(item, dict):
            continue

        title = find_title(item)

        if title and not is_bad_title(title):
            score += 5

        rank = find_rank(item, 0)

        if rank:
            score += 2

        raw = json.dumps(item, ensure_ascii=False)

        if any(x in raw for x in ["delta", "rank", "isNew", "ranking"]):
            score += 2

        if any(x in raw for x in ["titleKr", "mediaType", "openYear", "genres"]):
            score += 2

    return score


def parse_best_ranking(network_jsons):
    candidates = []

    for item in network_jsons:
        url = item.get("url", "")
        data = item.get("data")

        arrays = collect_arrays(data)

        for path, arr in arrays:
            score = score_array(arr)

            if score <= 0:
                continue

            candidates.append({
                "url": url,
                "path": path,
                "score": score,
                "length": len(arr),
                "array": arr,
            })

    if not candidates:
        return [], pd.DataFrame()

    candidates = sorted(
        candidates,
        key=lambda x: (x["score"], x["length"]),
        reverse=True,
    )

    debug_df = pd.DataFrame([
        {
            "url": c["url"],
            "path": c["path"],
            "score": c["score"],
            "length": c["length"],
        }
        for c in candidates
    ])

    best = candidates[0]["array"]

    rows = []
    seen_titles = set()

    for idx, item in enumerate(best, start=1):
        if not isinstance(item, dict):
            continue

        title = find_title(item)

        if is_bad_title(title):
            continue

        if title in seen_titles:
            continue

        seen_titles.add(title)

        media_type, genres, open_year = find_meta(item)

        rows.append({
            "rank": find_rank(item, idx),
            "title": title,
            "delta": find_delta(item),
            "is_new": find_is_new(item),
            "providers": find_providers(item),
            "genres": genres,
            "open_year": open_year,
            "media_type": media_type,
        })

        if len(rows) >= 100:
            break

    return rows, debug_df


def scrape():
    today = datetime.today().strftime("%Y-%m-%d")

    network_jsons = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path="/usr/bin/chromium",
        )

        page = browser.new_page(
            viewport={"width": 1440, "height": 1800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
        )

        def handle_response(response):
            try:
                url = response.url
                content_type = response.headers.get("content-type", "")

                if (
                    "application/json" not in content_type
                    and "graphql" not in url.lower()
                    and "api" not in url.lower()
                ):
                    return

                data = response.json()

                network_jsons.append({
                    "url": url,
                    "data": data,
                })

            except Exception:
                pass

        page.on("response", handle_response)

        page.goto(
            RANKING_URL,
            wait_until="domcontentloaded",
            timeout=50000,
        )

        page.wait_for_timeout(4000)

        for _ in range(10):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(800)

        page.wait_for_timeout(2000)

        browser.close()

    DEBUG_JSON_FILE.write_text(
        json.dumps(network_jsons, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    parsed_rows, debug_df = parse_best_ranking(network_jsons)

    if debug_df is not None and not debug_df.empty:
        debug_df.to_csv(
            DEBUG_CANDIDATES_FILE,
            index=False,
            encoding="utf-8-sig",
        )

    if not parsed_rows:
        raise Exception("No ranking data parsed from network JSON.")

    new_df = pd.DataFrame(parsed_rows)

    new_df["date"] = today
    new_df["period"] = "일간"

    new_df = new_df[
        [
            "date",
            "period",
            "rank",
            "title",
            "delta",
            "is_new",
            "providers",
            "genres",
            "open_year",
            "media_type",
        ]
    ].copy()

    new_df = new_df.sort_values("rank").head(100)

    if OUTPUT_FILE.exists():
        old_df = pd.read_csv(OUTPUT_FILE)

        if not old_df.empty and "date" in old_df.columns:
            old_df["date"] = old_df["date"].astype(str)

            old_df = old_df[
                ~(
                    (old_df["date"] == today)
                    & (old_df["period"].astype(str) == "일간")
                )
            ].copy()

            final_df = pd.concat([old_df, new_df], ignore_index=True)
        else:
            final_df = new_df
    else:
        final_df = new_df

    final_df = final_df.drop_duplicates(
        subset=["date", "period", "rank"],
        keep="last",
    )

    final_df = final_df.sort_values(
        ["date", "period", "rank"],
        ascending=[True, True, True],
    )

    final_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print("ranking rows:", len(new_df))
    print(new_df.head(30).to_string(index=False))


if __name__ == "__main__":
    scrape()
