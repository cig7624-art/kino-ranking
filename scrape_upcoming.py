import re
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright


OUTPUT = Path("upcoming_releases.csv")
DEBUG_TEXT = Path("debug_upcoming_text.txt")

URLS = [
    "https://m.kinolights.com/new?tab=upcoming",
    "https://kinolights.com/new?tab=upcoming",
]

END_MARKER = "업데이트 정보를 모두 가져왔습니다"

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

    patterns = [
        r"\d+편",
        r"\d+편\s*공개예정",
        r"\d+\s*편",
        r"\d+\s*편\s*공개예정",
    ]

    return any(re.fullmatch(pattern, text) for pattern in patterns)


def is_score_line(text):
    text = normalize_line(text)

    if re.fullmatch(r"\d+\.\d+", text):
        return True

    if text == "%":
        return True

    if re.fullmatch(r"\d+\.\d+\s*%", text):
        return True

    return False


def is_date_text(text):
    text = normalize_line(text)

    if text in ["오늘", "내일"]:
        return True

    if text in WEEKDAY_MAP:
        return True

    if re.fullmatch(r"\d{1,2}[./월]\s*\d{1,2}일?", text):
        return True

    if re.fullmatch(r"20\d{2}[./-]\s*\d{1,2}[./-]\s*\d{1,2}", text):
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
        "혜택",
        "마이페이지",
        "로그인",
        "전체",
        "필터",
        "작품",
        "인물",
        "컬렉션",
        "MY",
        "ALL",
        "넷플릭스",
        "티빙",
        "웨이브",
        "디즈니+",
        "쿠팡플레이",
        "왓챠",
        "애플TV+",
        "라프텔",
        "업데이트 정보를 모두 가져왔습니다.",
        "업데이트 정보를 모두 가져왔습니다",
    }

    if text in noise:
        return True

    if text == "":
        return True

    if is_count_line(text):
        return True

    if is_score_line(text):
        return True

    if is_date_text(text):
        return True

    return False


def parse_explicit_date(text, base_year):
    text = normalize_line(text)

    m = re.fullmatch(r"(\d{1,2})[./월]\s*(\d{1,2})일?", text)
    if m:
        month = int(m.group(1))
        day = int(m.group(2))

        try:
            return datetime(base_year, month, day).date()
        except ValueError:
            return None

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


def looks_like_title(text):
    text = clean_title(text)

    if not text:
        return False

    if is_noise_line(text):
        return False

    if len(text) <= 1:
        return False

    return True


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

        if not looks_like_title(line):
            continue

        title = clean_title(line)

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

    df = df.drop_duplicates(
        subset=["release_date", "title"],
        keep="first"
    )

    df["release_date_dt"] = pd.to_datetime(df["release_date"], errors="coerce")
    df = df[df["release_date_dt"].notna()].copy()
    df = df.sort_values(["release_date_dt", "title"])
    df = df.drop(columns=["release_date_dt"])

    return df.to_dict("records")


def scroll_until_end_marker(page, max_scrolls=80):
    """
    키노라이츠 공개예정작은 맨 아래에
    '업데이트 정보를 모두 가져왔습니다.'가 나올 때까지 추가 로딩됨.
    이 문구가 나올 때까지 스크롤.
    """
    last_text_len = 0
    stable_count = 0
    found_marker = False

    for i in range(max_scrolls):
        try:
            body_text = page.locator("body").inner_text(timeout=10000)
        except Exception:
            body_text = ""

        if END_MARKER in body_text:
            found_marker = True
            print(f"end marker found at scroll {i}")
            break

        current_text_len = len(body_text)

        if current_text_len == last_text_len:
            stable_count += 1
        else:
            stable_count = 0

        last_text_len = current_text_len

        # window 스크롤
        try:
            page.evaluate("""
                () => {
                    window.scrollBy(0, window.innerHeight * 1.3);
                }
            """)
        except Exception:
            pass

        # wheel 이벤트도 같이 발생
        try:
            page.mouse.wheel(0, 1400)
        except Exception:
            pass

        page.wait_for_timeout(900)

        # 텍스트가 8번 연속 안 늘고 marker도 없으면 종료
        if stable_count >= 8:
            print("text stable too long, stop scrolling")
            break

    return found_marker


def scrape_upcoming():
    all_texts = []
    all_rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path="/usr/bin/chromium"
        )

        page = browser.new_page(
            viewport={"width": 430, "height": 900},
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/16.0 Mobile/15E148 Safari/604.1"
            )
        )

        for url in URLS:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(6000)

                # 혹시 상단 탭이 정확히 공개예정작으로 안 잡혔을 때 대비
                try:
                    if page.get_by_text("공개예정작").count() > 0:
                        page.get_by_text("공개예정작").first.click(timeout=3000)
                        page.wait_for_timeout(2500)
                except Exception:
                    pass

                found_marker = scroll_until_end_marker(page, max_scrolls=80)

                body_text = page.locator("body").inner_text(timeout=15000)

                all_texts.append(f"\n\n===== URL: {url} =====\n")
                all_texts.append(f"FOUND_END_MARKER: {found_marker}\n")
                all_texts.append(body_text)

                rows = extract_rows_from_text(body_text)

                print(f"{url} text length:", len(body_text))
                print(f"{url} found marker:", found_marker)
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

    if not df.empty:
        print(df.head(100).to_string(index=False))


if __name__ == "__main__":
    scrape_upcoming()
