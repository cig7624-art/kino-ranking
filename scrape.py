from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime
from pathlib import Path
import re

URL = "https://m.kinolights.com/ranking/kino"

PERIODS = ["일간", "주간", "월간"]
PLATFORMS = ["전체", "넷플릭스", "티빙", "쿠팡플레이", "웨이브", "디즈니+", "왓챠", "박스오피스"]

EXCLUDE = set(PERIODS + PLATFORMS + [
    "트렌드 랭킹",
    "성별 · 연령 전체",
    "성별과 연령을 선택하고",
    "꼭 맞는 랭킹을 확인해 보세요",
    "홈", "랭킹", "탐색", "혜택", "마이페이지"
])

def is_title(line):
    if not line or line in EXCLUDE:
        return False
    if re.fullmatch(r"\d{1,3}", line):
        return False
    if re.fullmatch(r"\d+[▲▼]?", line):
        return False
    if re.fullmatch(r"\d+(\.\d+)?%", line):
        return False
    if re.search(r"(드라마|영화|예능|애니메이션|다큐멘터리|시사교양)\s*·\s*\d{4}", line):
        return False
    if "기준" in line:
        return False
    return True

def click_text(page, text):
    try:
        page.get_by_text(text, exact=True).first.click(force=True)
        page.wait_for_timeout(1800)
        return True
    except Exception:
        return False

def scroll_load(page):
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(500)

    for _ in range(8):
        page.mouse.wheel(0, 1800)
        page.wait_for_timeout(600)

def extract_titles(page):
    scroll_load(page)

    text = page.locator("body").inner_text()
    lines = [x.strip() for x in text.split("\n") if x.strip()]

    titles = []

    for line in lines:
        if is_title(line) and line not in titles:
            titles.append(line)

    return titles[:100]

today = datetime.today().strftime("%Y-%m-%d")
rows = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    page = browser.new_page(
        viewport={"width": 430, "height": 1800},
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
    )

    page.goto(URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(4000)

    for period in PERIODS:
        click_text(page, period)

        for platform in PLATFORMS:
            click_text(page, platform)

            titles = extract_titles(page)

            print(f"{period} / {platform} / {len(titles)}개 수집")

            for idx, title in enumerate(titles, start=1):
                rows.append({
                    "date": today,
                    "period": period,
                    "platform": platform,
                    "rank": idx,
                    "title": title
                })

    browser.close()

new_df = pd.DataFrame(rows)

csv_path = Path("ranking_history.csv")

if csv_path.exists():
    old = pd.read_csv(csv_path)

    for col in ["period", "platform"]:
        if col not in old.columns:
            old[col] = "전체"

    df = pd.concat([old, new_df], ignore_index=True)

    df = df.drop_duplicates(
        subset=["date", "period", "platform", "rank"],
        keep="last"
    )
else:
    df = new_df

df.to_csv(csv_path, index=False, encoding="utf-8-sig")

print(df.tail(50))
