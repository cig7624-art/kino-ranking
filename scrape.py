import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
from playwright.sync_api import (
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


BASE_URL = "https://m.kinolights.com"

PERIODS = ["일간", "주간", "월간"]

RANKING_URLS = {
    "전체": f"{BASE_URL}/ranking/kino",
    "넷플릭스": f"{BASE_URL}/ranking/netflix",
    "티빙": f"{BASE_URL}/ranking/tving",
    "쿠팡플레이": f"{BASE_URL}/ranking/coupangplay",
    "웨이브": f"{BASE_URL}/ranking/wavve",
    "디즈니+": f"{BASE_URL}/ranking/disneyplus",
    "왓챠": f"{BASE_URL}/ranking/watcha",
}

PERIOD_ORDER = {
    "일간": 1,
    "주간": 2,
    "월간": 3,
}

BAD_TITLES = {
    "",
    "홈",
    "랭킹",
    "전체 랭킹",
    "박스오피스",
    "넷플릭스",
    "티빙",
    "쿠팡플레이",
    "웨이브",
    "디즈니+",
    "왓챠",
    "로그인",
    "가입",
    "더보기",
    "검색",
    "공유",
    "찜하기",
    "보고 싶어요",
    "봤어요",
    "별로예요",
    "좋아요",
}


def normalize_text(value):
    """공백과 줄바꿈을 정리합니다."""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_title(value):
    """이전 순위 및 OTT별 작품을 제목으로 매칭할 때 사용합니다."""
    value = normalize_text(value).lower()
    value = re.sub(r"[\s:·\-–—_'\"“”‘’.,!?()\[\]{}]", "", value)
    return value


def normalize_href(href):
    """상세 URL을 절대 URL로 변환합니다."""
    href = str(href or "").strip()

    if not href:
        return ""

    return urljoin(BASE_URL, href)


def get_content_key(href):
    """상세 URL에서 season/숫자 또는 title/숫자 형태의 식별자를 만듭니다."""
    path = urlparse(normalize_href(href)).path

    match = re.search(r"/(season|title|movie|content)/(\d+)", path)

    if not match:
        return ""

    return f"{match.group(1)}:{match.group(2)}"


def is_valid_content_href(href):
    path = urlparse(normalize_href(href)).path

    return bool(
        re.search(
            r"/(season|title|movie|content)/\d+",
            path,
        )
    )


def get_card_text(link):
    """
    작품 링크의 가까운 상위 요소에서 카드 전체 텍스트를 가져옵니다.
    키노라이츠 DOM 클래스명이 변경돼도 최대한 버티도록 클래스명에 의존하지 않습니다.
    """
    try:
        return link.evaluate(
            """
            (element) => {
                const original = (element.innerText || "").trim();
                let current = element;
                let best = original;

                for (let depth = 0; depth < 7 && current; depth += 1) {
                    const text = (current.innerText || "").trim();
                    const lineCount = text
                        .split("\\n")
                        .map(v => v.trim())
                        .filter(Boolean)
                        .length;

                    if (
                        text &&
                        text.length >= best.length &&
                        text.length <= 500 &&
                        lineCount <= 15
                    ) {
                        best = text;
                    }

                    current = current.parentElement;
                }

                return best;
            }
            """
        )
    except Exception:
        return ""


def clean_title_candidate(value):
    value = normalize_text(value)

    # 앞쪽 순위 제거: "1 작품명", "#1 작품명"
    value = re.sub(r"^\s*#?\d{1,3}\s*[.)]?\s*", "", value)

    # 등락 및 NEW 문구 제거
    value = re.sub(r"^(NEW|신규)\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^[▲▼]\s*\d+\s*", "", value)

    return value.strip()


def extract_title(link_text, card_text, image_alt):
    """
    링크 텍스트 → 이미지 alt → 카드 텍스트 순서로 작품명을 찾습니다.
    """
    candidates = []

    for source in [link_text, image_alt, card_text]:
        for line in str(source or "").splitlines():
            line = clean_title_candidate(line)

            if not line:
                continue

            if line in BAD_TITLES:
                continue

            if re.fullmatch(r"#?\d{1,3}", line):
                continue

            if re.fullmatch(r"(19|20)\d{2}", line):
                continue

            if re.fullmatch(r"\d+(\.\d+)?%", line):
                continue

            if re.fullmatch(r"[▲▼]\s*\d+", line):
                continue

            if len(line) > 100:
                continue

            candidates.append(line)

    if not candidates:
        return ""

    # 일반적으로 링크 자체의 첫 텍스트가 작품명
    return candidates[0]


def extract_year(card_text):
    matches = re.findall(r"\b(19\d{2}|20\d{2})\b", str(card_text or ""))

    if not matches:
        return ""

    return matches[-1]


def extract_media_type(card_text):
    text = str(card_text or "")

    media_types = [
        ("애니메이션", "ANIMATION"),
        ("애니", "ANIMATION"),
        ("드라마", "DRAMA"),
        ("시리즈", "SERIES"),
        ("예능", "SHOW"),
        ("영화", "MOVIE"),
    ]

    for keyword, result in media_types:
        if keyword in text:
            return result

    return ""


def extract_genres(card_text, title, open_year):
    """
    카드에서 '영화 · 액션/드라마 · 2026' 같은 문구를 최대한 추출합니다.
    구조가 불명확하면 빈 값으로 둡니다.
    """
    lines = [
        normalize_text(line)
        for line in str(card_text or "").splitlines()
        if normalize_text(line)
    ]

    genre_candidates = []

    for line in lines:
        if normalize_title(line) == normalize_title(title):
            continue

        if "·" not in line and "/" not in line:
            continue

        parts = [
            normalize_text(part)
            for part in re.split(r"[·|]", line)
            if normalize_text(part)
        ]

        cleaned_parts = []

        for part in parts:
            if part == str(open_year):
                continue

            if re.fullmatch(r"(19|20)\d{2}", part):
                continue

            if re.fullmatch(r"\d+\+?", part):
                continue

            if re.fullmatch(r"\d+(\.\d+)?%", part):
                continue

            if part in {
                "영화",
                "드라마",
                "시리즈",
                "예능",
                "애니",
                "애니메이션",
            }:
                continue

            if len(part) > 40:
                continue

            cleaned_parts.append(part)

        if cleaned_parts:
            genre_candidates.extend(cleaned_parts)

    unique = []

    for genre in genre_candidates:
        for item in genre.split("/"):
            item = normalize_text(item)

            if item and item not in unique:
                unique.append(item)

    return ",".join(unique[:8])


def click_period(page: Page, period):
    """
    일간/주간/월간 버튼 또는 탭을 클릭합니다.
    못 찾으면 현재 기본 화면을 사용하고 로그만 남깁니다.
    """
    candidates = [
        page.get_by_role("button", name=period, exact=True),
        page.get_by_role("tab", name=period, exact=True),
        page.get_by_role("link", name=period, exact=True),
        page.get_by_text(period, exact=True),
    ]

    for locator in candidates:
        try:
            count = locator.count()

            for index in range(count):
                target = locator.nth(index)

                if not target.is_visible():
                    continue

                target.click(force=True, timeout=5000)
                page.wait_for_timeout(2000)
                return True

        except Exception:
            continue

    print(f"[경고] '{period}' 선택 요소를 찾지 못했습니다.")
    return False


def scroll_until_loaded(page: Page, minimum_count=100):
    """
    무한 스크롤 또는 지연 로딩에 대응합니다.
    """
    locator = page.locator(
        "a[href*='/season/'], "
        "a[href*='/title/'], "
        "a[href*='/movie/'], "
        "a[href*='/content/']"
    )

    last_count = 0
    stable_count = 0

    for _ in range(25):
        current_count = locator.count()

        if current_count >= minimum_count:
            break

        if current_count == last_count:
            stable_count += 1
        else:
            stable_count = 0

        if stable_count >= 4:
            break

        last_count = current_count

        page.evaluate(
            """
            window.scrollTo({
                top: document.body.scrollHeight,
                behavior: "instant"
            });
            """
        )
        page.wait_for_timeout(900)

    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(300)


def extract_ranking_items(page: Page, limit=100):
    scroll_until_loaded(page, minimum_count=limit)

    links = page.locator(
        "a[href*='/season/'], "
        "a[href*='/title/'], "
        "a[href*='/movie/'], "
        "a[href*='/content/']"
    )

    items = []
    seen_keys = set()

    count = links.count()

    for index in range(count):
        if len(items) >= limit:
            break

        link = links.nth(index)

        try:
            href = normalize_href(link.get_attribute("href"))

            if not is_valid_content_href(href):
                continue

            content_key = get_content_key(href)

            if not content_key or content_key in seen_keys:
                continue

            link_text = ""

            try:
                link_text = link.inner_text(timeout=2000)
            except Exception:
                pass

            image_alt = ""

            try:
                image_alt = (
                    link.locator("img")
                    .first
                    .get_attribute("alt", timeout=1000)
                    or ""
                )
            except Exception:
                pass

            card_text = get_card_text(link)

            title = extract_title(
                link_text=link_text,
                card_text=card_text,
                image_alt=image_alt,
            )

            if not title:
                continue

            if title in BAD_TITLES:
                continue

            open_year = extract_year(card_text)
            media_type = extract_media_type(card_text)
            genres = extract_genres(
                card_text=card_text,
                title=title,
                open_year=open_year,
            )

            seen_keys.add(content_key)

            items.append(
                {
                    "content_key": content_key,
                    "url": href,
                    "title": title,
                    "media_type": media_type,
                    "genres": genres,
                    "open_year": open_year,
                }
            )

        except Exception as error:
            print(f"[링크 파싱 오류] index={index}: {error}")
            continue

    return items


def collect_ranking(
    context: BrowserContext,
    provider_name,
    url,
    period,
    limit=100,
):
    page = context.new_page()

    try:
        print(f"[수집 시작] {provider_name} / {period} / {url}")

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        page.wait_for_timeout(3000)

        click_period(page, period)
        page.wait_for_timeout(1500)

        items = extract_ranking_items(page, limit=limit)

        print(
            f"[수집 완료] {provider_name} / {period}: "
            f"{len(items)}개"
        )

        return items

    except PlaywrightTimeoutError as error:
        print(f"[페이지 시간 초과] {provider_name} / {period}: {error}")
        return []

    except Exception as error:
        print(f"[수집 오류] {provider_name} / {period}: {error}")
        return []

    finally:
        page.close()


def load_previous_ranks(today):
    """
    기존 ranking_history.csv에서 오늘 이전 가장 최근 날짜의 순위를 불러옵니다.
    """
    path = Path("ranking_history.csv")

    if not path.exists():
        return {}, {}, False

    try:
        old_df = pd.read_csv(path).fillna("")
    except Exception as error:
        print(f"[이전 데이터 로드 실패] {error}")
        return {}, {}, False

    required = {"date", "period", "rank", "title"}

    if old_df.empty or not required.issubset(old_df.columns):
        return {}, {}, False

    old_df["date"] = old_df["date"].astype(str)
    previous_dates = sorted(
        date
        for date in old_df["date"].unique()
        if date and date < today
    )

    if not previous_dates:
        return {}, {}, False

    previous_date = previous_dates[-1]
    previous_df = old_df[old_df["date"] == previous_date].copy()

    exact_lookup = {}
    title_lookup = {}

    for _, row in previous_df.iterrows():
        period = str(row.get("period", "")).strip()
        title = normalize_title(row.get("title", ""))
        open_year = str(row.get("open_year", "")).strip()

        try:
            rank = int(float(row.get("rank")))
        except Exception:
            continue

        if not title:
            continue

        exact_lookup[(period, title, open_year)] = rank
        title_lookup[(period, title)] = rank

    print(f"[이전 순위 기준] {previous_date}")

    return exact_lookup, title_lookup, True


def save_ranking_history(new_df):
    """
    기존 이력을 유지하면서 오늘 수집 결과를 병합합니다.
    같은 날짜·기간·작품은 최신 결과로 교체합니다.
    """
    path = Path("ranking_history.csv")

    if path.exists():
        try:
            old_df = pd.read_csv(path).fillna("")
        except Exception:
            old_df = pd.DataFrame()
    else:
        old_df = pd.DataFrame()

    if old_df.empty:
        combined = new_df.copy()
    else:
        for column in new_df.columns:
            if column not in old_df.columns:
                old_df[column] = ""

        for column in old_df.columns:
            if column not in new_df.columns:
                new_df[column] = ""

        new_df = new_df[old_df.columns]

        combined = pd.concat(
            [old_df, new_df],
            ignore_index=True,
        )

        combined = combined.drop_duplicates(
            subset=["date", "period", "title"],
            keep="last",
        )

    combined["period_order"] = (
        combined["period"]
        .map(PERIOD_ORDER)
        .fillna(99)
    )

    combined["rank_numeric"] = pd.to_numeric(
        combined["rank"],
        errors="coerce",
    ).fillna(9999)

    combined = combined.sort_values(
        ["date", "period_order", "rank_numeric"],
        ascending=[True, True, True],
    )

    combined = combined.drop(
        columns=["period_order", "rank_numeric"],
        errors="ignore",
    )

    combined.to_csv(
        path,
        index=False,
        encoding="utf-8-sig",
    )


def main():
    today = datetime.now().strftime("%Y-%m-%d")

    previous_exact, previous_title, has_previous = (
        load_previous_ranks(today)
    )

    overall_by_period = {}
    provider_items_by_period = {
        period: {}
        for period in PERIODS
    }

    debug_rows = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )

        context = browser.new_context(
            viewport={
                "width": 1440,
                "height": 1600,
            },
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/150.0.0.0 Safari/537.36"
            ),
        )

        context.set_default_timeout(15000)

        # 1. 전체 랭킹 수집
        for period in PERIODS:
            overall_by_period[period] = collect_ranking(
                context=context,
                provider_name="전체",
                url=RANKING_URLS["전체"],
                period=period,
                limit=100,
            )

        # 2. OTT별 랭킹 수집
        for provider_name, url in RANKING_URLS.items():
            if provider_name == "전체":
                continue

            for period in PERIODS:
                items = collect_ranking(
                    context=context,
                    provider_name=provider_name,
                    url=url,
                    period=period,
                    limit=100,
                )

                for rank, item in enumerate(items, start=1):
                    content_key = item["content_key"]
                    title_key = normalize_title(item["title"])

                    provider_items_by_period[period].setdefault(
                        ("content_key", content_key),
                        set(),
                    ).add(provider_name)

                    provider_items_by_period[period].setdefault(
                        ("title", title_key),
                        set(),
                    ).add(provider_name)

                    debug_rows.append(
                        {
                            "date": today,
                            "period": period,
                            "rank": rank,
                            "title": item["title"],
                            "content_key": content_key,
                            "providerId": "",
                            "providerNameMapped": provider_name,
                            "isActive": True,
                            "source_url": item["url"],
                            "raw_offer": "",
                        }
                    )

        context.close()
        browser.close()

    rows = []

    for period in PERIODS:
        items = overall_by_period.get(period, [])

        for rank, item in enumerate(items, start=1):
            title = item["title"]
            title_key = normalize_title(title)
            open_year = str(item.get("open_year", "")).strip()
            content_key = item.get("content_key", "")

            providers = set()

            providers.update(
                provider_items_by_period[period].get(
                    ("content_key", content_key),
                    set(),
                )
            )

            providers.update(
                provider_items_by_period[period].get(
                    ("title", title_key),
                    set(),
                )
            )

            previous_rank = previous_exact.get(
                (period, title_key, open_year)
            )

            if previous_rank is None:
                previous_rank = previous_title.get(
                    (period, title_key)
                )

            if previous_rank is None:
                delta = 0
                is_new = has_previous
            else:
                # 이전 순위 20위 → 현재 10위인 경우 +10
                delta = previous_rank - rank
                is_new = False

            rows.append(
                {
                    "date": today,
                    "period": period,
                    "rank": rank,
                    "title": title,
                    "media_type": item.get("media_type", ""),
                    "genres": item.get("genres", ""),
                    "open_year": open_year,
                    "is_new": is_new,
                    "delta": delta,
                    "providers": ",".join(sorted(providers)),
                    "content_key": content_key,
                    "url": item.get("url", ""),
                }
            )

    if not rows:
        raise RuntimeError(
            "랭킹 데이터를 한 건도 수집하지 못했습니다. "
            "GitHub Actions 로그에서 기간별 수집 개수를 확인하세요."
        )

    result_df = pd.DataFrame(rows)

    save_ranking_history(result_df)

    debug_df = pd.DataFrame(debug_rows)

    debug_df.to_csv(
        "debug_provider_ids.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print("")
    print("========================================")
    print("ranking_history.csv 저장 완료")
    print("========================================")
    print(result_df.groupby("period").size())
    print("")
    print(result_df.head(30).to_string(index=False))
    print("")
    print("OTT별 수집 건수")
    print(
        debug_df.groupby(
            ["period", "providerNameMapped"]
        ).size()
    )


if __name__ == "__main__":
    main()
