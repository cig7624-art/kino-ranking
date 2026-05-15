import re
from datetime import datetime
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright


OUTPUT = Path("upcoming_releases.csv")

KINOLIGHTS_UPCOMING_URLS = [
    "https://kinolights.com/new?tab=upcoming",
    "https://m.kinolights.com/new?tab=upcoming",
]

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


def detect_provider(text: str) -> str:
    text = str(text).strip()
    upper = text.upper()

    direct = {
        "넷플릭스": "넷플릭스",
        "티빙": "티빙",
        "쿠팡플레이": "쿠팡플레이",
        "쿠팡": "쿠팡플레이",
        "웨이브": "웨이브",
        "디즈니+": "디즈니+",
        "디즈니": "디즈니+",
        "왓챠": "왓챠",
        "애플TV+": "애플TV+",
        "애플": "애플TV+",
        "라프텔": "라프텔",
    }

    for key, value in direct.items():
        if key in text:
            return value

    english = {
        "NETFLIX": "넷플릭스",
        "TVING": "티빙",
        "COUPANG": "쿠팡플레이",
        "WAVVE": "웨이브",
        "DISNEY": "디즈니+",
        "WATCHA": "왓챠",
        "APPLE": "애플TV+",
        "LAFTEL": "라프텔",
    }

    for key, value in english.items():
        if key in upper:
            return value

    return ""


def parse_date_from_text(text: str, year: int) -> str:
    text = str(text).strip()

    # 2026.05.16 / 2026-05-16
    m = re.search(r"(20\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})", text)
    if m:
        y, month, day = map(int, m.groups())
        try:
            return datetime(y, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return ""

    # 05.16 / 5/16 / 5월 16일
    m = re.search(r"(\d{1,2})\s*[.\-/월]\s*(\d{1,2})", text)
    if m:
        month, day = map(int, m.groups())
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return ""

    return ""


def looks_like_noise(text: str) -> bool:
    text = str(text).strip()

    if not text:
        return True

    noise_words = [
        "홈",
        "랭킹",
        "탐색",
        "혜택",
        "마이페이지",
        "검색",
        "신작",
        "공개예정작",
        "종료예정작",
        "작품",
        "인물",
        "컬렉션",
        "전체",
        "필터",
        "서비스",
        "광고",
        "이벤트",
        "로그인",
        "가입",
    ]

    if text in noise_words:
        return True

    if len(text) <= 1:
        return True

    return False


def clean_title(text: str) -> str:
    text = str(text).strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^\d+\s*", "", text)
    text = text.replace("공개예정", "").strip()
    return text


def extract_rows_from_text(body_text: str) -> list[dict]:
    """
    키노라이츠 공개예정작 화면 텍스트를 줄 단위로 보고,
    날짜 → 타이틀 → OTT 제공처 흐름을 추정해서 CSV화.
    """
    today = datetime.now()
    year = today.year
    collect_date = today.strftime("%Y-%m-%d")

    lines = [line.strip() for line in body_text.splitlines() if line.strip()]
    rows = []

    current_date = ""

    for i, line in enumerate(lines):
        parsed_date = parse_date_from_text(line, year)

        if parsed_date:
            current_date = parsed_date
            continue

        provider = detect_provider(line)

        if not provider:
            continue

        # provider 라인 주변에서 타이틀 후보 찾기
        title = ""

        # 일반적으로 OTT명 바로 위쪽에 타이틀이 있을 가능성이 높음
        for back in range(1, 6):
            j = i - back

            if j < 0:
                break

            candidate = clean_title(lines[j])

            if looks_like_noise(candidate):
                continue

            if detect_provider(candidate):
                continue

            if parse_date_from_text(candidate, year):
                continue

            # 점수/퍼센트/평점류 제외
            if re.fullmatch(r"[-+]?\d+(\.\d+)?%?", candidate):
                continue

            title = candidate
            break

        if not title or not current_date:
            continue

        rows.append({
            "collect_date": collect_date,
            "release_date": current_date,
            "title": title,
            "provider": provider,
            "genre": "",
        })

    # 중복 제거
    unique = {}
    for row in rows:
        key = (row["release_date"], row["title"], row["provider"])
        unique[key] = row

    return list(unique.values())


def scrape_upcoming() -> pd.DataFrame:
    all_rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path="/usr/bin/chromium",
        )

        page = browser.new_page(
            viewport={"width": 430, "height": 1800},
            user_agent="Mozilla/5.0",
        )

        for url in KINOLIGHTS_UPCOMING_URLS:
            try:
                page.goto(url, wait_until="networkidle", timeout=40000)
                page.wait_for_timeout(2500)

                body_text = page.locator("body").inner_text(timeout=10000)
                rows = extract_rows_from_text(body_text)

                if rows:
                    all_rows.extend(rows)
                    break

            except Exception as e:
                print(f"수집 실패: {url} / {e}")

        browser.close()

    if not all_rows:
        return pd.DataFrame(
            columns=["collect_date", "release_date", "title", "provider", "genre"]
        )

    df = pd.DataFrame(all_rows)
    df = df.drop_duplicates(
        subset=["release_date", "title", "provider"],
        keep="first",
    )

    df["release_date_dt"] = pd.to_datetime(df["release_date"], errors="coerce")
    df = df[df["release_date_dt"].notna()].copy()
    df = df.sort_values(["release_date_dt", "title", "provider"])
    df = df.drop(columns=["release_date_dt"])

    return df


if __name__ == "__main__":
    df = scrape_upcoming()
    df.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
    print(f"{OUTPUT} 저장 완료: {len(df)}개")
    print(df.head(20).to_string(index=False))
