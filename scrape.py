from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime
from pathlib import Path
import re

URL = "https://m.kinolights.com/ranking/kino"

EXCLUDE = {
    "트렌드 랭킹", "일간", "주간", "월간", "전체",
    "넷플릭스", "티빙", "쿠팡플레이", "웨이브", "디즈니+", "왓챠", "박스오피스",
    "성별 · 연령 전체", "홈", "랭킹", "탐색", "혜택", "마이페이지"
}

def is_title(line):
    if not line:
        return False
    if line in EXCLUDE:
        return False
    if re.fullmatch(r"\d{1,3}", line):
        return False
    if re.fullmatch(r"\d+[▲▼]?", line):
        return False
    if re.fullmatch(r"\d+(\.\d+)?%", line):
        return False
    if re.search(r"(드라마|영화|예능|애니메이션|다큐멘터리)\s*·\s*\d{4}", line):
        return False
    if "기준" in line:
        return False
    return True

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(
        viewport={"width": 390, "height": 1200},
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
    )

    page.goto(URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(5000)

    text = page.locator("body").inner_text()
    browser.close()

lines = [x.strip() for x in text.split("\n") if x.strip()]

titles = []
for line in lines:
    if is_title(line) and line not in titles:
        titles.append(line)

titles = titles[:20]

today = datetime.today().strftime("%Y-%m-%d")

df = pd.DataFrame({
    "date": [today] * len(titles),
    "rank": range(1, len(titles) + 1),
    "title": titles
})

csv_path = Path("ranking_history.csv")

if csv_path.exists():
    old = pd.read_csv(csv_path)
    df = pd.concat([old, df], ignore_index=True)
    df = df.drop_duplicates(subset=["date", "title"], keep="last")

df.to_csv(csv_path, index=False, encoding="utf-8-sig")

print(df.tail(20))
