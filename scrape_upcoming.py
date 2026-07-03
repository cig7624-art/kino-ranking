import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
from playwright.sync_api import sync_playwright


OUTPUT = Path("upcoming_releases.csv")
DEBUG_TEXT = Path("debug_upcoming_text.txt")
DEBUG_CARDS = Path("debug_upcoming_cards.csv")

BASE_URL = "https://m.kinolights.com"
UPCOMING_URL = "https://m.kinolights.com/new?tab=upcoming"
END_MARKER = "업데이트 정보를 모두 가져왔습니다"

PROVIDERS = {
    "netflix": "넷플릭스",
    "넷플릭스": "넷플릭스",
    "tving": "티빙",
    "티빙": "티빙",
    "wavve": "웨이브",
    "웨이브": "웨이브",
    "disney": "디즈니+",
    "디즈니": "디즈니+",
    "watcha": "왓챠",
    "왓챠": "왓챠",
    "coupang": "쿠팡플레이",
    "쿠팡": "쿠팡플레이",
    "apple": "애플TV+",
    "애플": "애플TV+",
    "laftel": "라프텔",
    "라프텔": "라프텔",
}

WEEKDAY_MAP = {
    "월요일": 0,
    "화요일": 1,
    "수요일": 2,
    "목요일": 3,
    "금요일": 4,
    "토요일": 5,
    "일요일": 6,
}


def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def is_bad_title(title):
    title = normalize_text(title)

    bad_titles = {
        "",
        "홈",
        "랭킹",
        "탐색",
        "혜택",
        "마이페이지",
        "주메뉴",
        "상단으로",
        "맨 위로",
        "뒤로가기",
        "공유",
        "검색",
        "신작",
        "공개예정작",
        "종료예정작",
        "본 작품 제외",
        "구매/대여 제외",
        "업데이트 정보를 모두 가져왔습니다",
        "업데이트 정보를 모두 가져왔습니다.",
        "전체",
        "MY",
        "ALL",
        "작품",
        "인물",
        "컬렉션",
        "필터",
        "로그인",
        "가입",
    }

    if title in bad_titles:
        return True

    if re.fullmatch(r"\d+\s*편(\s*공개예정)?", title):
        return True

    if re.fullmatch(r"\d+\.\d+%?", title):
        return True

    if title == "%":
        return True

    if len(title) <= 1:
        return True

    return False


def detect_provider_from_text(text):
    text = str(text or "").lower()

    for key, provider in PROVIDERS.items():
        if key.lower() in text:
            return provider

    return ""


def detect_provider_from_attrs(attrs):
    joined = " ".join([str(v or "") for v in attrs.values()]).lower()
    return detect_provider_from_text(joined)


def parse_explicit_date(text, base_year):
    text = normalize_text(text)

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
    text = normalize_text(text)

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


def scroll_until_end(page, max_scrolls=80):
    found_marker = False
    stable_count = 0
    last_text_len = 0

    for i in range(max_scrolls):
        try:
            body_text = page.locator("body").inner_text(timeout=10000)
        except Exception:
            body_text = ""

        if END_MARKER in body_text:
            found_marker = True
            print(f"END_MARKER found at scroll {i}")
            break

        current_text_len = len(body_text)

        if current_text_len == last_text_len:
            stable_count += 1
        else:
            stable_count = 0

        last_text_len = current_text_len

        try:
            page.evaluate("window.scrollBy(0, window.innerHeight * 1.3)")
        except Exception:
            pass

        try:
            page.mouse.wheel(0, 1400)
        except Exception:
            pass

        page.wait_for_timeout(900)

        if stable_count >= 8:
            print("Text length stable too long. Stop scrolling.")
            break

    return found_marker


def extract_date_blocks_from_text(body_text):
    """
    텍스트 기준으로 날짜별 작품명 후보를 만든다.
    DOM 수집이 실패하거나 부족할 때 보조 기준으로 사용.
    """
    today_dt = datetime.now()
    today = today_dt.date()

    lines = [
        normalize_text(line)
        for line in str(body_text).splitlines()
        if normalize_text(line)
    ]

    current_date = None
    rows = []

    for line in lines:
        date_heading = parse_date_heading(line, today)

        if date_heading:
            current_date = date_heading
            continue

        if current_date is None:
            continue

        if is_bad_title(line):
            continue

        rows.append({
            "release_date": current_date.strftime("%Y-%m-%d"),
            "title": line,
        })

    if not rows:
        return pd.DataFrame(columns=["release_date", "title"])

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["release_date", "title"], keep="first")
    return df


def get_element_attrs(locator):
    attrs = {}

    for attr in [
        "href",
        "src",
        "alt",
        "title",
        "aria-label",
        "class",
        "data-src",
        "data-original",
        "style",
    ]:
        try:
            value = locator.get_attribute(attr)
            if value:
                attrs[attr] = value
        except Exception:
            pass

    return attrs


def collect_card_candidates(page):
    """
    공개예정작 카드 후보 DOM 수집.
    카드 구조를 아직 모르기 때문에 a/img 주변을 넓게 수집한다.
    """
    candidates = []

    # 1) 링크 후보
    link_locators = page.locator("a").all()

    for idx, a in enumerate(link_locators):
        try:
            text = normalize_text(a.inner_text(timeout=1000))
        except Exception:
            text = ""

        attrs = get_element_attrs(a)
        href = attrs.get("href", "")
        full_url = urljoin(BASE_URL, href) if href else ""

        # 내부 이미지 수집
        image_url = ""
        image_alt = ""

        try:
            img = a.locator("img").first
            if img.count() > 0:
                img_attrs = get_element_attrs(img)
                image_url = (
                    img_attrs.get("src")
                    or img_attrs.get("data-src")
                    or img_attrs.get("data-original")
                    or ""
                )
                image_alt = img_attrs.get("alt", "")
                if image_url:
                    image_url = urljoin(BASE_URL, image_url)
        except Exception:
            pass

        provider = detect_provider_from_text(text) or detect_provider_from_attrs(attrs)

        # title 후보
        title = ""
        text_lines = [normalize_text(x) for x in text.splitlines() if normalize_text(x)]

        for line in text_lines:
            if not is_bad_title(line):
                title = line
                break

        if not title and image_alt and not is_bad_title(image_alt):
            title = image_alt

        if title or href or image_url:
            candidates.append({
                "source": "a",
                "idx": idx,
                "raw_text": text,
                "title": title,
                "href": href,
                "url": full_url,
                "image_url": image_url,
                "image_alt": image_alt,
                "provider": provider,
                "attrs": str(attrs),
            })

    # 2) 이미지 후보
    img_locators = page.locator("img").all()

    for idx, img in enumerate(img_locators):
        attrs = get_element_attrs(img)

        image_url = (
            attrs.get("src")
            or attrs.get("data-src")
            or attrs.get("data-original")
            or ""
        )
        if image_url:
            image_url = urljoin(BASE_URL, image_url)

        image_alt = attrs.get("alt", "")
        provider = detect_provider_from_attrs(attrs) or detect_provider_from_text(image_alt)

        # 이미지 부모 링크 찾기
        url = ""
        href = ""

        try:
            parent_a = img.locator("xpath=ancestor::a[1]")
            if parent_a.count() > 0:
                href = parent_a.get_attribute("href") or ""
                url = urljoin(BASE_URL, href) if href else ""
        except Exception:
            pass

        title = image_alt if image_alt and not is_bad_title(image_alt) else ""

        if image_url or title or url:
            candidates.append({
                "source": "img",
                "idx": idx,
                "raw_text": "",
                "title": title,
                "href": href,
                "url": url,
                "image_url": image_url,
                "image_alt": image_alt,
                "provider": provider,
                "attrs": str(attrs),
            })

    return candidates


def merge_text_dates_with_cards(text_df, card_df):
    """
    날짜는 텍스트 파싱이 가장 안정적이고,
    링크/이미지/provider는 DOM 카드 후보에서 보강한다.
    키노라이츠 개편으로 날짜 파싱이 실패해도 Actions가 죽지 않게 방어한다.
    """
    collect_date = datetime.now().strftime("%Y-%m-%d")

    required_cols = ["release_date", "title"]

    if text_df is None or text_df.empty:
        print("WARNING: 공개예정작 날짜/타이틀 텍스트 파싱 실패")
        return pd.DataFrame(columns=[
            "collect_date", "release_date", "title", "provider", "genre", "url", "image_url"
        ])

    for col in required_cols:
        if col not in text_df.columns:
            print(f"WARNING: text_df에 {col} 컬럼이 없습니다.")
            return pd.DataFrame(columns=[
                "collect_date", "release_date", "title", "provider", "genre", "url", "image_url"
            ])

    base = text_df.copy()

    if card_df is None or card_df.empty:
        card_df = pd.DataFrame(columns=["title", "provider", "url", "image_url"])

    for col in ["title", "provider", "url", "image_url"]:
        if col not in card_df.columns:
            card_df[col] = ""

    base["title"] = base["title"].fillna("").astype(str).str.strip()
    base["release_date"] = base["release_date"].fillna("").astype(str).str.strip()

    base = base[base["title"] != ""].copy()
    base = base[base["release_date"] != ""].copy()

    if base.empty:
        print("WARNING: 공개예정작 유효 데이터 없음")
        return pd.DataFrame(columns=[
            "collect_date", "release_date", "title", "provider", "genre", "url", "image_url"
        ])

    base["title_key"] = base["title"].astype(str).map(
        lambda x: re.sub(r"\s+", "", x).lower()
    )

    card_df["title"] = card_df["title"].fillna("").astype(str).str.strip()
    card_df["title_key"] = card_df["title"].astype(str).map(
        lambda x: re.sub(r"\s+", "", x).lower()
    )

    valid_cards = card_df[card_df["title"] != ""].copy()

    if not valid_cards.empty:
        valid_cards["score"] = 0
        valid_cards.loc[valid_cards["url"].astype(str).str.strip() != "", "score"] += 3
        valid_cards.loc[valid_cards["image_url"].astype(str).str.strip() != "", "score"] += 3
        valid_cards.loc[valid_cards["provider"].astype(str).str.strip() != "", "score"] += 2

        valid_cards = valid_cards.sort_values("score", ascending=False)
        valid_cards = valid_cards.drop_duplicates(subset=["title_key"], keep="first")

        merged = base.merge(
            valid_cards[["title_key", "provider", "url", "image_url"]],
            on="title_key",
            how="left",
        )
    else:
        merged = base.copy()
        merged["provider"] = ""
        merged["url"] = ""
        merged["image_url"] = ""

    merged["collect_date"] = collect_date
    merged["genre"] = ""

    for col in ["provider", "url", "image_url"]:
        if col not in merged.columns:
            merged[col] = ""
        merged[col] = merged[col].fillna("").astype(str)

    merged = merged[
        ["collect_date", "release_date", "title", "provider", "genre", "url", "image_url"]
    ].copy()

    merged = merged[~merged["title"].apply(is_bad_title)].copy()

    merged["release_date_dt"] = pd.to_datetime(merged["release_date"], errors="coerce")
    merged = merged[merged["release_date_dt"].notna()].copy()

    if merged.empty:
        print("WARNING: 공개예정작 날짜 변환 후 유효 데이터 없음")
        return pd.DataFrame(columns=[
            "collect_date", "release_date", "title", "provider", "genre", "url", "image_url"
        ])

    merged = merged.drop_duplicates(subset=["release_date", "title"], keep="first")
    merged = merged.sort_values(["release_date_dt", "title"])
    merged = merged.drop(columns=["release_date_dt"])

    return merged


def scrape_upcoming():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path="/usr/bin/chromium",
        )

        page = browser.new_page(
            viewport={"width": 430, "height": 900},
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/16.0 Mobile/15E148 Safari/604.1"
            ),
        )

        page.goto(UPCOMING_URL, wait_until="domcontentloaded", timeout=40000)
        page.wait_for_timeout(6000)

        # 공개예정작 탭 보정
        try:
            if page.get_by_text("공개예정작").count() > 0:
                page.get_by_text("공개예정작").first.click(timeout=3000)
                page.wait_for_timeout(2500)
        except Exception:
            pass

        found_marker = scroll_until_end(page, max_scrolls=80)

        body_text = page.locator("body").inner_text(timeout=15000)
        DEBUG_TEXT.write_text(
            f"FOUND_END_MARKER: {found_marker}\n\n{body_text}",
            encoding="utf-8",
        )

        text_df = extract_date_blocks_from_text(body_text)

        candidates = collect_card_candidates(page)
        card_df = pd.DataFrame(candidates)

        if card_df.empty:
            card_df = pd.DataFrame(
                columns=[
                    "source", "idx", "raw_text", "title", "href", "url",
                    "image_url", "image_alt", "provider", "attrs"
                ]
            )

        card_df.to_csv(DEBUG_CARDS, index=False, encoding="utf-8-sig")

        final_df = merge_text_dates_with_cards(text_df, card_df)

        browser.close()

    final_df.to_csv(OUTPUT, index=False, encoding="utf-8-sig")

    print(f"FOUND_END_MARKER: {found_marker}")
    print(f"text rows: {len(text_df)}")
    print(f"card candidates: {len(card_df)}")
    print(f"{OUTPUT} 저장 완료: {len(final_df)}개")

    if not final_df.empty:
        print(final_df.head(80).to_string(index=False))


if __name__ == "__main__":
    scrape_upcoming()
