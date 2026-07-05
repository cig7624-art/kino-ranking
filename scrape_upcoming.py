import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
from playwright.sync_api import sync_playwright


UPCOMING_URL = "https://m.kinolights.com/new?tab=upcoming"

OUTPUT_FILE = Path("upcoming_releases.csv")
DEBUG_CARDS_FILE = Path("debug_upcoming_cards.csv")
DEBUG_TEXT_FILE = Path("debug_upcoming_text.txt")

PROVIDERS = [
    "넷플릭스",
    "티빙",
    "쿠팡플레이",
    "디즈니+",
    "웨이브",
    "라프텔",
    "왓챠",
    "Apple TV",
    "아마존 프라임 비디오",
    "씨네폭스",
]

BAD_TITLES = {
    "",
    "홈",
    "랭킹",
    "탐색",
    "혜택",
    "마이페이지",
    "주메뉴",
    "신작",
    "공개 예정작",
    "공개예정작",
    "종료 예정작",
    "종료예정작",
    "본 작품 제외",
    "구매/대여 제외",
    "업데이트 정보를 모두 가져왔습니다",
    "업데이트 정보를 모두 가져왔습니다.",
    "전체",
    "MY",
    "ALL",
    "검색",
    "공유",
    "로그인",
    "가입",
    "작품",
    "인물",
    "컬렉션",
}


def normalize_space(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def is_bad_title(title):
    title = normalize_space(title)

    if title in BAD_TITLES:
        return True

    if re.fullmatch(r"\d{4}", title):
        return True

    if re.fullmatch(r"\d+\s*편(\s*공개예정)?", title):
        return True

    if re.fullmatch(r"\d+(\.\d+)?\s*%?", title):
        return True

    if len(title) <= 1:
        return True

    return False


def parse_release_date(raw_text, collect_date):
    text = str(raw_text or "")
    base = datetime.strptime(collect_date, "%Y-%m-%d")

    if "오늘 공개" in text or "오늘" in text:
        return base.strftime("%Y-%m-%d")

    if "내일 공개" in text or "내일" in text:
        return (base + timedelta(days=1)).strftime("%Y-%m-%d")

    m = re.search(r"(\d{1,2})[./](\d{1,2})", text)

    if m:
        month = int(m.group(1))
        day = int(m.group(2))
        year = base.year

        try:
            dt = datetime(year, month, day)

            if dt < base - timedelta(days=60):
                dt = datetime(year + 1, month, day)

            return dt.strftime("%Y-%m-%d")
        except Exception:
            return ""

    return ""


def extract_title(raw_text, image_alt=""):
    alt = normalize_space(image_alt)

    if alt and not is_bad_title(alt):
        return alt

    lines = [
        normalize_space(x)
        for x in str(raw_text or "").splitlines()
        if normalize_space(x)
    ]

    for line in lines:
        if is_bad_title(line):
            continue

        if line in PROVIDERS:
            continue

        if re.fullmatch(r"\d{1,2}[./]\d{1,2}", line):
            continue

        if "공개" in line and len(line) <= 10:
            continue

        if re.search(r"\d{4}\s*·", line):
            continue

        if any(x in line for x in ["영화", "드라마", "예능", "애니메이션", "다큐멘터리"]):
            if len(line) <= 20:
                continue

        return line

    return ""


def extract_genre(raw_text):
    lines = [
        normalize_space(x)
        for x in str(raw_text or "").splitlines()
        if normalize_space(x)
    ]

    for line in lines:
        if re.search(r"\d{4}\s*·", line):
            return line

    for line in lines:
        if any(x in line for x in ["영화", "드라마", "예능", "애니메이션", "다큐멘터리"]):
            return line

    return ""


def click_upcoming_tab(page):
    candidates = ["공개 예정작", "공개예정작"]

    for text in candidates:
        try:
            page.get_by_text(text, exact=True).first.click(timeout=3000)
            page.wait_for_timeout(1000)
            return
        except Exception:
            pass


def click_provider(page, provider):
    candidates = [provider]

    if provider == "Apple TV":
        candidates = ["Apple TV", "Apple TV+", "애플TV+", "애플 TV"]
    elif provider == "아마존 프라임 비디오":
        candidates = ["아마존 프라임 비디오", "Prime Video", "아마존"]
    elif provider == "씨네폭스":
        candidates = ["씨네폭스", "CINEFOX"]

    for name in candidates:
        try:
            page.get_by_text(name, exact=True).first.click(timeout=4000)
            page.wait_for_timeout(1500)
            return True
        except Exception:
            pass

    print(f"WARNING: provider button not found - {provider}")
    return False


def scroll_until_loaded(page):
    last_height = 0
    stable_count = 0

    for _ in range(20):
        try:
            body_text = page.locator("body").inner_text(timeout=3000)
        except Exception:
            body_text = ""

        if "업데이트 정보를 모두 가져왔습니다" in body_text:
            break

        try:
            height = page.evaluate("document.body.scrollHeight")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(900)
        except Exception:
            break

        if height == last_height:
            stable_count += 1
        else:
            stable_count = 0

        last_height = height

        if stable_count >= 4:
            break


def collect_candidates(page):
    return page.evaluate(
        """
        () => {
            const results = [];
            const seen = new Set();

            const nodes = Array.from(document.querySelectorAll('a[href], article, li, div'));

            for (const el of nodes) {
                const text = (el.innerText || '').trim();
                const img = el.querySelector('img');
                const a = el.tagName.toLowerCase() === 'a' ? el : el.querySelector('a[href]');

                const href = a ? a.href : '';
                const imageUrl =
                    img?.src ||
                    img?.getAttribute('data-src') ||
                    img?.getAttribute('data-original') ||
                    '';

                const imageAlt = img?.alt || '';

                const looksLikeContent =
                    href.includes('/title/') ||
                    href.includes('/content/') ||
                    href.includes('/contents/') ||
                    imageUrl.includes('kinolights') ||
                    imageUrl.includes('image') ||
                    imageUrl.includes('poster');

                if (!looksLikeContent) continue;

                const key = href + '|' + imageUrl + '|' + text.slice(0, 80);
                if (seen.has(key)) continue;
                seen.add(key);

                results.push({
                    href,
                    rawText: text,
                    imageUrl,
                    imageAlt
                });
            }

            return results;
        }
        """
    )


def scrape_provider(page, provider, collect_date):
    rows = []
    debug_rows = []

    candidates = collect_candidates(page)

    for idx, item in enumerate(candidates):
        raw_text = item.get("rawText", "")
        image_alt = item.get("imageAlt", "")
        href = item.get("href", "")
        image_url = item.get("imageUrl", "")

        title = extract_title(raw_text, image_alt)
        release_date = parse_release_date(raw_text, collect_date)
        genre = extract_genre(raw_text)

        skip_reason = ""

        if is_bad_title(title):
            skip_reason = "bad_title"
        elif not release_date:
            skip_reason = "no_release_date"

        debug_rows.append({
            "provider": provider,
            "idx": idx,
            "title": title,
            "release_date": release_date,
            "skip_reason": skip_reason,
            "url": href,
            "image_url": image_url,
            "image_alt": image_alt,
            "raw_text": raw_text,
        })

        if skip_reason:
            continue

        rows.append({
            "collect_date": collect_date,
            "release_date": release_date,
            "title": title,
            "provider": provider,
            "genre": genre,
            "url": href,
            "image_url": image_url,
        })

    return rows, debug_rows


def scrape_upcoming():
    collect_date = datetime.today().strftime("%Y-%m-%d")

    all_rows = []
    all_debug_rows = []
    debug_texts = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path="/usr/bin/chromium"
        )

        page = browser.new_page(
            viewport={"width": 1440, "height": 1600},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
        )

        for provider in PROVIDERS:
            print(f"==== {provider} ====")

            page.goto(
                UPCOMING_URL,
                wait_until="networkidle",
                timeout=50000
            )

            page.wait_for_timeout(2000)

            click_upcoming_tab(page)

            clicked = click_provider(page, provider)

            if not clicked:
                continue

            scroll_until_loaded(page)

            try:
                body_text = page.locator("body").inner_text(timeout=5000)
            except Exception:
                body_text = ""

            debug_texts.append(f"\n\n===== {provider} =====\n{body_text[:10000]}")

            rows, debug_rows = scrape_provider(
                page,
                provider,
                collect_date
            )

            print(provider, "rows:", len(rows))

            all_rows.extend(rows)
            all_debug_rows.extend(debug_rows)

        browser.close()

    if all_rows:
        df = pd.DataFrame(all_rows)

        df = df[~df["title"].apply(is_bad_title)].copy()

        df["release_date_dt"] = pd.to_datetime(
            df["release_date"],
            errors="coerce"
        )

        df = df[df["release_date_dt"].notna()].copy()

        df = df.drop_duplicates(
            subset=["release_date", "title", "provider"],
            keep="first"
        )

        df = df.sort_values(
            ["release_date_dt", "provider", "title"],
            ascending=[True, True, True]
        )

        df = df.drop(columns=["release_date_dt"])
    else:
        df = pd.DataFrame(columns=[
            "collect_date",
            "release_date",
            "title",
            "provider",
            "genre",
            "url",
            "image_url",
        ])

    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    debug_df = pd.DataFrame(all_debug_rows)
    debug_df.to_csv(
        DEBUG_CARDS_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    DEBUG_TEXT_FILE.write_text(
        "\n".join(debug_texts),
        encoding="utf-8"
    )

    print("upcoming rows:", len(df))
    print(df.head(50).to_string(index=False))


if __name__ == "__main__":
    scrape_upcoming()
