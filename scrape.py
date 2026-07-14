import re
import html
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from playwright.sync_api import sync_playwright


RANKING_URL = "https://m.kinolights.com/ranking/kino"

OUTPUT_FILE = Path("ranking_history.csv")
DEBUG_PROVIDER_FILE = Path("debug_provider_ids.csv")

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

    if "리뷰" in title and len(title) <= 24:
        return True

    if title.startswith("▲") or title.startswith("▼"):
        return True

    if title in OTT_NAMES:
        return True

    return False


def extract_title(raw_text, image_alt=""):
    alt = normalize_space(image_alt)

    if alt:
        alt = alt.replace("포스터", "").replace("이미지", "").strip()
        if not is_bad_title(alt):
            return alt

    lines = [
        normalize_space(x)
        for x in str(raw_text or "").splitlines()
        if normalize_space(x)
    ]

    for line in lines:
        if is_bad_title(line):
            continue

        if "·" in line and re.search(r"(19\d{2}|20\d{2})", line):
            continue

        if any(x in line for x in ["영화", "드라마", "예능", "애니메이션", "다큐멘터리"]):
            if re.search(r"(19\d{2}|20\d{2})", line) or "·" in line:
                continue

        if len(line) > 60:
            continue

        return line

    return ""


def extract_meta(raw_text):
    lines = [
        normalize_space(x)
        for x in str(raw_text or "").splitlines()
        if normalize_space(x)
    ]

    media_type = ""
    genres = ""
    open_year = ""

    for line in lines:
        if re.search(r"(19\d{2}|20\d{2})", line):
            year_match = re.search(r"(19\d{2}|20\d{2})", line)
            open_year = year_match.group(1) if year_match else ""
            parts = [x.strip() for x in re.split(r"[·/]", line) if x.strip()]

            if parts:
                media_type = parts[0]

            if len(parts) >= 2:
                genres = ",".join(parts[1:])

            break

    return media_type, genres, open_year


def extract_dom_delta(raw_text):
    text = str(raw_text or "")

    if "NEW" in text:
        return 0, True

    up = re.search(r"[▲△]\s*(\d+)", text)
    if up:
        return int(up.group(1)), False

    down = re.search(r"[▼▽]\s*(\d+)", text)
    if down:
        return -int(down.group(1)), False

    return 0, False


def extract_providers_from_detail(url):
    found = []

    try:
        res = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                )
            },
            timeout=10,
        )

        if res.status_code >= 400:
            return ""

        text = html.unescape(res.text)
        text = re.sub(r"<[^>]+>", " ", text)
        text = normalize_space(text)

        section = ""
        if "정액제" in text:
            section = text.split("정액제", 1)[1]
            for stop_word in [
                "무료",
                "대여",
                "구매",
                "시청 주의 가이드",
                "작품 정보",
                "비슷한 작품",
                "리뷰",
                "출연",
                "감독",
            ]:
                if stop_word in section:
                    section = section.split(stop_word, 1)[0]

        for ott in OTT_NAMES:
            if section and ott in section:
                found.append(ott)
            if f"{ott} 바로 보기" in text:
                found.append(ott)

        result = []
        for ott in OTT_NAMES:
            if ott in found and ott not in result:
                result.append(ott)

        return ",".join(result)

    except Exception:
        return ""


def collect_ranking_cards(page):
    return page.evaluate(
        """
        () => {
            const rows = [];
            const seen = new Set();
            const anchors = Array.from(document.querySelectorAll('a[href]'));

            for (const a of anchors) {
                const href = a.href || "";
                const rawText = (a.innerText || "").trim();
                const img = a.querySelector("img");
                const imageAlt = img?.alt || "";
                const looksLikeContent =
                    href.includes("/season/") ||
                    href.includes("/title/") ||
                    href.includes("/content/") ||
                    href.includes("/contents/");

                if (!looksLikeContent) continue;

                const key = href + "|" + rawText.slice(0, 100) + "|" + imageAlt;
                if (seen.has(key)) continue;
                seen.add(key);

                rows.push({ href, rawText, imageAlt });
            }

            return rows;
        }
        """
    )


def get_previous_rank_map(today):
    if not OUTPUT_FILE.exists():
        return {}

    try:
        old_df = pd.read_csv(OUTPUT_FILE)
    except Exception:
        return {}

    if old_df.empty or "title" not in old_df.columns or "rank" not in old_df.columns or "date" not in old_df.columns:
        return {}

    old_df["date"] = old_df["date"].astype(str)
    old_df["title"] = old_df["title"].fillna("").astype(str).str.strip()
    old_df["rank"] = pd.to_numeric(old_df["rank"], errors="coerce")
    old_df = old_df[old_df["date"] < today].copy()
    old_df = old_df[~old_df["title"].apply(is_bad_title)].copy()
    old_df = old_df[old_df["rank"].notna()].copy()

    if old_df.empty:
        return {}

    if "period" in old_df.columns:
        daily_df = old_df[old_df["period"].astype(str).str.strip() == "일간"].copy()
        if not daily_df.empty:
            old_df = daily_df

    latest_prev_date = sorted(old_df["date"].unique(), reverse=True)[0]
    prev_df = old_df[old_df["date"] == latest_prev_date].copy()

    rank_map = {}
    for _, row in prev_df.iterrows():
        title = str(row.get("title", "")).strip()
        if title and title not in rank_map:
            rank_map[title] = int(row["rank"])

    return rank_map


def scrape():
    today = datetime.today().strftime("%Y-%m-%d")
    prev_rank_map = get_previous_rank_map(today)

    rows = []
    debug_rows = []
    provider_cache = {}

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

        page.goto(RANKING_URL, wait_until="networkidle", timeout=50000)
        page.wait_for_timeout(2500)

        for _ in range(12):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(700)

        cards = collect_ranking_cards(page)
        browser.close()

    rank = 1
    seen_titles = set()

    for item in cards:
        raw_text = item.get("rawText", "")
        image_alt = item.get("imageAlt", "")
        href = item.get("href", "")

        title = extract_title(raw_text, image_alt)

        if is_bad_title(title):
            continue

        if title in seen_titles:
            continue

        seen_titles.add(title)
        media_type, genres, open_year = extract_meta(raw_text)
        dom_delta, dom_is_new = extract_dom_delta(raw_text)

        prev_rank = prev_rank_map.get(title)
        if prev_rank is None:
            delta = 0
            is_new = True
        else:
            delta = prev_rank - rank
            is_new = False

        if delta == 0 and dom_delta != 0:
            delta = dom_delta

        if dom_is_new:
            is_new = True

        url = urljoin(RANKING_URL, href)
        if url in provider_cache:
            providers = provider_cache[url]
        else:
            providers = extract_providers_from_detail(url)
            provider_cache[url] = providers

        rows.append({
            "date": today,
            "period": "일간",
            "rank": rank,
            "title": title,
            "delta": delta,
            "is_new": is_new,
            "providers": providers,
            "genres": genres,
            "open_year": open_year,
            "media_type": media_type,
        })

        debug_rows.append({
            "date": today,
            "period": "일간",
            "rank": rank,
            "title": title,
            "url": url,
            "delta": delta,
            "is_new": is_new,
            "providers": providers,
            "raw_text": raw_text,
        })

        rank += 1
        if rank > 100:
            break

    new_df = pd.DataFrame(rows)

    if new_df.empty:
        raise Exception("No ranking data collected. ranking_history.csv not updated.")

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
        keep="last",
    )

    final_df = final_df.sort_values(
        ["date", "period", "rank"],
        ascending=[True, True, True],
    )

    final_df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    debug_df = pd.DataFrame(debug_rows)
    debug_df.to_csv(DEBUG_PROVIDER_FILE, index=False, encoding="utf-8-sig")

    print("ranking rows:", len(new_df))
    print(new_df.head(30).to_string(index=False))


if __name__ == "__main__":
    scrape()
