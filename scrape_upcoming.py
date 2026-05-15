import re
import pandas as pd
from datetime import datetime
from playwright.sync_api import sync_playwright

PROVIDERS = [
    "넷플릭스",
    "티빙",
    "쿠팡플레이",
    "웨이브",
    "디즈니+",
    "왓챠",
    "애플TV+",
    "라프텔",
]


def detect_provider(text):
    for provider in PROVIDERS:
        if provider in text:
            return provider

    provider_map = {
        "NETFLIX": "넷플릭스",
        "TVING": "티빙",
        "WAVVE": "웨이브",
        "DISNEY": "디즈니+",
        "WATCHA": "왓챠",
        "COUPANG": "쿠팡플레이",
        "APPLE": "애플TV+",
        "LAFTEL": "라프텔",
    }

    upper = text.upper()

    for key, value in provider_map.items():
        if key in upper:
            return value

    return ""


def parse_release_date(text, year):
    text = str(text)

    patterns = [
        r"(\d{1,2})[./월]\s*(\d{1,2})",
        r"(\d{1,2})\s*/\s*(\d{1,2})",
    ]

    for pattern in patterns:
        m = re.search(pattern, text)

        if m:
            month = int(m.group(1))
            day = int(m.group(2))

            try:
                return datetime(year, month, day).strftime("%Y-%m-%d")
            except Exception:
                return ""

    return ""


def clean_title(text):
    text = str(text).strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^\d+\s*", "", text)
    text = text.replace("공개예정", "").strip()
    return text


def scrape_upcoming():
    rows = []
    today = datetime.now()
    year = today.year
    collect_date = today.strftime("%Y-%m-%d")

    url = "https://m.kinolights.com/new?tab=upcoming"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path="/usr/bin/chromium"
        )

        page = browser.new_page(
            viewport={"width": 430, "height": 1600},
            user_agent="Mozilla/5.0"
        )

        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        body_text = page.locator("body").inner_text()

        lines = [
            line.strip()
            for line in body_text.splitlines()
            if line.strip()
        ]

        current_date = ""

        for idx, line in enumerate(lines):
            possible_date = parse_release_date(line, year)

            if possible_date:
                current_date = possible_date
                continue

            provider = detect_provider(line)

            if provider:
                title_candidates = []

                for back in range(1, 4):
                    if idx - back >= 0:
                        prev = lines[idx - back]
                        if (
                            len(prev) >= 2
                            and "공개예정" not in prev
                            and detect_provider(prev) == ""
                            and parse_release_date(prev, year) == ""
                            and prev not in ["신작", "공개예정작", "종료예정작"]
                        ):
                            title_candidates.append(prev)

                title = clean_title(title_candidates[0]) if title_candidates else ""

                if title and current_date:
                    rows.append({
                        "collect_date": collect_date,
                        "release_date": current_date,
                        "title": title,
                        "provider": provider,
                        "genre": "",
                    })

        browser.close()

    df = pd.DataFrame(rows)

    if df.empty:
        df = pd.DataFrame(
            columns=["collect_date", "release_date", "title", "provider", "genre"]
        )
    else:
        df = df.drop_duplicates(
            subset=["release_date", "title", "provider"],
            keep="first"
        )

    df.to_csv("upcoming_releases.csv", index=False, encoding="utf-8-sig")

    print(f"upcoming_releases.csv 저장 완료: {len(df)}개")


if __name__ == "__main__":
    scrape_upcoming()
