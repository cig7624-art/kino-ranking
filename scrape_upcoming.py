import re
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright


OUTPUT = Path("upcoming_releases.csv")
DEBUG_TEXT = Path("debug_upcoming_text.txt")

URLS = [
    "https://kinolights.com/new?tab=upcoming",
    "https://m.kinolights.com/new?tab=upcoming",
]


WEEKDAY_MAP = {
    "월요일": 0,
    "화요일": 1,
    "수요일": 2,
    "목요일": 3,
    "금요일": 4,
    "토요일": 5,
    "일요일": 6,
}


def normalize_line(text):
    return str(text).strip()


def is_count_line(text):
    text = normalize_line(text)
    return bool(re.fullmatch(r"\d+편\s*공개예정", text))


def is_score_line(text):
    text = normalize_line(text)

    # 17.4, 39.6 같은 점수/비율
    if re.fullmatch(r"\d+\.\d+", text):
        return True

    # 단독 %
    if text == "%":
        return True

    # 17.4% 형태
    if re.fullmatch(r"\d+\.\d+\s*%", text):
        return True

    return False


def is_noise_line(text):
    text = normalize_line(text)

    noise = {
        "신작",
        "공개예정작",
        "종료예정작",
        "본 작품 제외",
        "구매/대여 제외",
        "홈",
        "랭킹",
        "탐색",
        "검색",
        "마이페이지",
        "로그인",
        "전체",
        "필터",
        "작품",
        "인물",
        "컬렉션",
    }

    if text in noise:
        return True

    if text == "":
        return True

    if is_count_line(text):
        return True

    if is_score_line(text):
        return True

    return False


def parse_explicit_date(text, base_year):
    text = normalize_line(text)

    # 05.18 / 5.18 / 05/18 / 5월 18일
    m = re.fullmatch(r"(\d{1,2})[./월]\s*(\d{1,2})일?", text)
    if m:
        month = int(m.group(1))
        day = int(m.group(2))

        try:
            return datetime(base_year, month, day).date()
        except ValueError:
            return None

    # 2026.05.18 / 2026-05-18
    m = re.fullmatch(r"(20\d{2})[./-]\s*(\d{1,2})[./-]\s*(\d{1,2})", text)
    if m:
        year = int(m.group(1))
        month = int(m.group(2))
        day = int(m.group(3))

        try:
            return datetime(year, month, day).date()
        except ValueError:
            return None

    return None


def next_weekday_date(today, weekday_name):
    target = WEEKDAY_MAP[weekday_name]
    today_weekday = today.weekday()

    diff = target - today_weekday

    if diff <= 0:
        diff += 7

    return today + timedelta(days=diff)


def parse_date_heading(text, today):
    text = normalize_line(text)

    if text == "오늘":
        return today

    if text == "내일":
        return today + timedelta(days=1)

    if text in WEEKDAY_MAP:
        return next_weekday_date(today, text)

    explicit = parse_explicit_date(text, today.year)

    if explicit:
        return explicit

    return None


def clean_title(text):
    text = normalize_line(text)
    text = re.sub(r"\s+", " ", text)
    text = text.replace("공개예정", "").strip()
    return text


def extract_rows_from_text(body_text):
    today_dt = datetime.now()
    today = today_dt.date()
    collect_date = today_dt.strftime("%Y-%m-%d")

    lines = [
        normalize_line(line)
        for line in body_text.splitlines()
        if normalize_line(line)
    ]

    rows = []
    current_date = None

    for line in lines:
        date_heading = parse_date_heading(line, today)

        if date_heading:
            current_date = date_heading
            continue

        if current_date is None:
            continue

        if is_noise_line(line):
            continue

        title = clean_title(line)

        if not title:
            continue

        # 너무 짧은 한글/영문 1글자 제거
        if len(title) <= 1:
            continue

        rows.append({
            "collect_date": collect_date,
            "release_date": current_date.strftime("%Y-%m-%d"),
            "title": title,
            "provider": "",
            "genre": "",
        })

    if not rows:
        return []

    df = pd.DataFrame(rows)

    # 같은 날짜/제목 중복 제거
    df = df.drop_duplicates(
        subset=["release_date", "title"],
        keep="first"
    )

    # 날짜순 정렬
    df["release_date_dt"] = pd.to_datetime(df["release_date"], errors="coerce")
    df = df[df["release_date_dt"].notna()].copy()
    df = df.sort_values(["release_date_dt", "title"])
    df = df.drop(columns=["release_date_dt"])

    return df.to_dict("records")


def scrape_upcoming():
    all_texts = []
    all_rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path="/usr/bin/chromium"
        )

        page = browser.new_page(
            viewport={"width": 430, "height": 2200},
            user_agent="Mozilla/5.0"
        )

        for url in URLS:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(5000)

                # 스크롤해서 lazy load 유도
previous_height = 0

for _ in range(30):
    page.mouse.wheel(0, 1600)
    page.wait_for_timeout(1000)

    current_height = page.evaluate("document.body.scrollHeight")

    if current_height == previous_height:
        break

    previous_height = current_height

                body_text = page.locator("body").inner_text(timeout=15000)

                all_texts.append(f"\n\n===== URL: {url} =====\n")
                all_texts.append(body_text)

                rows = extract_rows_from_text(body_text)

                print(f"{url} text length:", len(body_text))
                print(f"{url} parsed rows:", len(rows))

                if rows:
                    all_rows.extend(rows)
                    break

            except Exception as e:
                all_texts.append(f"\n\n===== URL: {url} FAILED =====\n{e}\n")
                print(f"{url} 실패:", e)

        browser.close()

    DEBUG_TEXT.write_text("\n".join(all_texts), encoding="utf-8")

    if not all_rows:
        df = pd.DataFrame(
            columns=["collect_date", "release_date", "title", "provider", "genre"]
        )
    else:
        df = pd.DataFrame(all_rows)
        df = df.drop_duplicates(
            subset=["release_date", "title"],
            keep="first"
        )
        df["release_date_dt"] = pd.to_datetime(df["release_date"], errors="coerce")
        df = df[df["release_date_dt"].notna()].copy()
        df = df.sort_values(["release_date_dt", "title"])
        df = df.drop(columns=["release_date_dt"])

    df.to_csv(OUTPUT, index=False, encoding="utf-8-sig")

    print(f"{OUTPUT} 저장 완료: {len(df)}개")
    print(df.head(30).to_string(index=False))


if __name__ == "__main__":
    scrape_upcoming()
