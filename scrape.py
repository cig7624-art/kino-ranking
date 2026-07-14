import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import pandas as pd
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

BASE_URL = "https://m.kinolights.com"
PERIODS = ["일간", "주간", "월간"]
PERIOD_ORDER = {"일간": 1, "주간": 2, "월간": 3}

RANKING_URLS = {
    "전체": f"{BASE_URL}/ranking/kino",
    "넷플릭스": f"{BASE_URL}/ranking/netflix",
    "티빙": f"{BASE_URL}/ranking/tving",
    "쿠팡플레이": f"{BASE_URL}/ranking/coupangplay",
    "웨이브": f"{BASE_URL}/ranking/wavve",
    "디즈니+": f"{BASE_URL}/ranking/disneyplus",
    "왓챠": f"{BASE_URL}/ranking/watcha",
}

BAD_TITLES = {
    "",
    "%",
    "NEW",
    "신규",
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
    "순위",
    "평점",
    "별점",
    "작품",
    "포스터",
    "영화",
    "드라마",
    "시리즈",
    "예능",
    "애니",
    "애니메이션",
    "다큐멘터리",
}


def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_title(value):
    return re.sub(
        r"[\s:·\-–—_'\"“”‘’.,!?()\[\]{}]",
        "",
        normalize_text(value).lower(),
    )


def normalize_href(href):
    href = str(href or "").strip()
    return urljoin(BASE_URL, href) if href else ""


def get_content_key(href):
    match = re.search(
        r"/(season|title|movie|content)/(\d+)",
        urlparse(normalize_href(href)).path,
    )

    return f"{match.group(1)}:{match.group(2)}" if match else ""


def is_valid_content_href(href):
    return bool(
        re.search(
            r"/(season|title|movie|content)/\d+",
            urlparse(normalize_href(href)).path,
        )
    )


def get_card_text(link):
    try:
        return link.evaluate(
            """
            (element) => {
                let current = element;
                let best = (element.innerText || '').trim();

                for (let depth = 0; depth < 7 && current; depth += 1) {
                    const text = (current.innerText || '').trim();
                    const lines = text
                        .split('\\n')
                        .map(v => v.trim())
                        .filter(Boolean);

                    if (
                        text &&
                        text.length >= best.length &&
                        text.length <= 500 &&
                        lines.length <= 15
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


def get_dom_title_candidates(link):
    try:
        values = link.evaluate(
            """
            (element) => {
                const values = [];

                const push = (value) => {
                    if (!value) return;

                    const text = String(value).trim();

                    if (text && !values.includes(text)) {
                        values.push(text);
                    }
                };

                let current = element;

                for (let depth = 0; depth < 5 && current; depth += 1) {
                    push(current.getAttribute?.('aria-label'));
                    push(current.getAttribute?.('title'));

                    current.querySelectorAll?.(
                        'img[alt],' +
                        '[aria-label],' +
                        '[title],' +
                        'h1,h2,h3,h4,' +
                        '[data-testid*="title"],' +
                        '[class*="title"]'
                    ).forEach((node) => {
                        push(node.getAttribute?.('alt'));
                        push(node.getAttribute?.('aria-label'));
                        push(node.getAttribute?.('title'));
                        push(node.innerText || node.textContent);
                    });

                    if ((current.innerText || '').trim().length > 700) {
                        break;
                    }

                    current = current.parentElement;
                }

                return values.slice(0, 80);
            }
            """
        )

        return values if isinstance(values, list) else []

    except Exception:
        return []


def clean_title_candidate(value):
    value = normalize_text(value)

    value = re.sub(
        r"^\s*#?\d{1,3}\s*[.)]?\s*",
        "",
        value,
    )

    value = re.sub(
        r"^(NEW|신규)\s*",
        "",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"^[▲▼]\s*\d+\s*",
        "",
        value,
    )

    value = re.sub(
        r"\s*(포스터|작품 이미지|이미지)$",
        "",
        value,
    )

    return value.strip()


def is_bad_title_candidate(value):
    text = clean_title_candidate(value)
    compact = re.sub(r"\s+", "", text)

    if not text:
        return True

    if text in BAD_TITLES:
        return True

    if compact.upper() in BAD_TITLES:
        return True

    if re.fullmatch(
        r"[\d.,%+\-▲▼★☆⭐]+",
        compact,
    ):
        return True

    if re.fullmatch(
        r"#?\d{1,3}위?",
        compact,
    ):
        return True

    if re.fullmatch(
        r"(?:19|20)\d{2}",
        compact,
    ):
        return True

    if re.fullmatch(
        r"\d{1,2}\+",
        compact,
    ):
        return True

    if re.fullmatch(
        r"\d+(?:\.\d+)?점",
        compact,
    ):
        return True

    if re.fullmatch(
        r"\d+개",
        compact,
    ):
        return True

    bad_phrases = [
        "키노라이츠 지수",
        "신선도",
        "평점",
        "별점",
        "리뷰",
        "코멘트",
        "보고 싶어요",
        "봤어요",
    ]

    if any(
        word in text
        for word in bad_phrases
    ):
        return True

    if "·" in text or "/" in text:
        if re.search(
            r"\b(?:19|20)\d{2}\b",
            text,
        ):
            return True

        if any(
            word in text
            for word in [
                "영화",
                "드라마",
                "시리즈",
                "예능",
                "애니메이션",
                "다큐멘터리",
            ]
        ):
            return True

    if not re.search(
        r"[가-힣A-Za-z一-龥ぁ-んァ-ヶ]",
        text,
    ):
        return True

    if len(text) > 100:
        return True

    return False


def extract_title(
    link_text,
    card_text,
    image_alt,
    dom_candidates,
):
    sources = [
        (
            "image_alt",
            image_alt,
            80,
        ),
        (
            "dom",
            "\n".join(dom_candidates or []),
            65,
        ),
        (
            "card_text",
            card_text,
            45,
        ),
        (
            "link_text",
            link_text,
            25,
        ),
    ]

    candidates = []
    seen = set()

    for _, source_value, base_score in sources:
        for line_index, raw_line in enumerate(
            str(source_value or "").splitlines()
        ):
            candidate = clean_title_candidate(
                raw_line
            )

            if is_bad_title_candidate(
                candidate
            ):
                continue

            normalized = normalize_title(
                candidate
            )

            if not normalized:
                continue

            if normalized in seen:
                continue

            seen.add(normalized)

            score = (
                base_score
                + max(
                    0,
                    20 - line_index,
                )
            )

            if re.search(
                r"[가-힣A-Za-z一-龥ぁ-んァ-ヶ]",
                candidate,
            ):
                score += 20

            if 1 <= len(candidate) <= 50:
                score += 15

            elif len(candidate) > 70:
                score -= 25

            if (
                "·" in candidate
                or "/" in candidate
            ):
                score -= 20

            if re.search(
                r"\b(?:19|20)\d{2}\b",
                candidate,
            ):
                score -= 20

            candidates.append(
                (
                    score,
                    candidate,
                )
            )

    if not candidates:
        return ""

    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return candidates[0][1]


def extract_year(card_text):
    matches = re.findall(
        r"\b(?:19|20)\d{2}\b",
        str(card_text or ""),
    )

    return matches[-1] if matches else ""


def extract_media_type(card_text):
    text = str(card_text or "")

    media_types = [
        (
            "애니메이션",
            "ANIMATION",
        ),
        (
            "애니",
            "ANIMATION",
        ),
        (
            "드라마",
            "DRAMA",
        ),
        (
            "시리즈",
            "SERIES",
        ),
        (
            "예능",
            "SHOW",
        ),
        (
            "영화",
            "MOVIE",
        ),
    ]

    for keyword, result in media_types:
        if keyword in text:
            return result

    return ""


def extract_genres(
    card_text,
    title,
    open_year,
):
    genres = []

    for line in str(
        card_text or ""
    ).splitlines():
        line = normalize_text(
            line
        )

        if not line:
            continue

        if normalize_title(
            line
        ) == normalize_title(
            title
        ):
            continue

        if (
            "·" not in line
            and "/" not in line
        ):
            continue

        parts = [
            normalize_text(part)
            for part in re.split(
                r"[·|]",
                line,
            )
        ]

        for part in parts:
            if not part:
                continue

            if part == str(
                open_year
            ):
                continue

            if re.fullmatch(
                r"(?:19|20)\d{2}",
                part,
            ):
                continue

            if re.fullmatch(
                r"\d+\+?",
                part,
            ):
                continue

            if re.fullmatch(
                r"\d+(?:\.\d+)?%",
                part,
            ):
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

            for item in part.split("/"):
                item = normalize_text(
                    item
                )

                if (
                    item
                    and item not in genres
                ):
                    genres.append(
                        item
                    )

    return ",".join(
        genres[:8]
    )


def click_period(
    page,
    period,
):
    locators = [
        page.get_by_role(
            "button",
            name=period,
            exact=True,
        ),
        page.get_by_role(
            "tab",
            name=period,
            exact=True,
        ),
        page.get_by_role(
            "link",
            name=period,
            exact=True,
        ),
        page.get_by_text(
            period,
            exact=True,
        ),
    ]

    for locator in locators:
        try:
            for index in range(
                locator.count()
            ):
                target = locator.nth(
                    index
                )

                if target.is_visible():
                    target.click(
                        force=True,
                        timeout=5000,
                    )

                    page.wait_for_timeout(
                        2000
                    )

                    return True

        except Exception:
            continue

    print(
        f"[경고] '{period}' 선택 요소를 찾지 못했습니다."
    )

    return False


def scroll_until_loaded(
    page,
    minimum_count=100,
):
    locator = page.locator(
        "a[href*='/season/'],"
        "a[href*='/title/'],"
        "a[href*='/movie/'],"
        "a[href*='/content/']"
    )

    last_count = -1
    stable_count = 0

    for _ in range(30):
        current_count = locator.count()

        if current_count >= minimum_count:
            break

        if current_count == last_count:
            stable_count += 1
        else:
            stable_count = 0

        if stable_count >= 5:
            break

        last_count = current_count

        page.evaluate(
            "window.scrollTo("
            "0, document.body.scrollHeight"
            ")"
        )

        page.wait_for_timeout(
            900
        )

    page.evaluate(
        "window.scrollTo(0, 0)"
    )

    page.wait_for_timeout(
        300
    )


def extract_ranking_items(
    page,
    limit=100,
):
    scroll_until_loaded(
        page,
        minimum_count=limit,
    )

    links = page.locator(
        "a[href*='/season/'],"
        "a[href*='/title/'],"
        "a[href*='/movie/'],"
        "a[href*='/content/']"
    )

    items = []
    seen_keys = set()

    for index in range(
        links.count()
    ):
        if len(items) >= limit:
            break

        link = links.nth(
            index
        )

        try:
            href = normalize_href(
                link.get_attribute(
                    "href"
                )
            )

            if not is_valid_content_href(
                href
            ):
                continue

            content_key = get_content_key(
                href
            )

            if not content_key:
                continue

            if content_key in seen_keys:
                continue

            try:
                link_text = link.inner_text(
                    timeout=2000
                )

            except Exception:
                link_text = ""

            try:
                image_alt = (
                    link
                    .locator("img")
                    .first
                    .get_attribute(
                        "alt",
                        timeout=1000,
                    )
                    or ""
                )

            except Exception:
                image_alt = ""

            card_text = get_card_text(
                link
            )

            dom_candidates = (
                get_dom_title_candidates(
                    link
                )
            )

            title = extract_title(
                link_text=link_text,
                card_text=card_text,
                image_alt=image_alt,
                dom_candidates=dom_candidates,
            )

            if not title:
                print(
                    f"[제목 없음] "
                    f"href={href}, "
                    f"link={repr(link_text[:80])}, "
                    f"alt={repr(image_alt[:80])}, "
                    f"card={repr(card_text[:120])}"
                )

                continue

            if is_bad_title_candidate(
                title
            ):
                print(
                    f"[잘못된 제목 제외] "
                    f"href={href}, "
                    f"title={repr(title)}, "
                    f"link={repr(link_text[:80])}, "
                    f"alt={repr(image_alt[:80])}, "
                    f"card={repr(card_text[:120])}"
                )

                continue

            open_year = extract_year(
                card_text
            )

            seen_keys.add(
                content_key
            )

            items.append(
                {
                    "content_key": content_key,
                    "url": href,
                    "title": title,
                    "media_type": extract_media_type(
                        card_text
                    ),
                    "genres": extract_genres(
                        card_text,
                        title,
                        open_year,
                    ),
                    "open_year": open_year,
                }
            )

        except Exception as error:
            print(
                f"[링크 파싱 오류] "
                f"index={index}: {error}"
            )

    return items


def collect_ranking(
    context,
    provider_name,
    url,
    period,
    limit=100,
):
    page = context.new_page()

    try:
        print(
            f"[수집 시작] "
            f"{provider_name} / "
            f"{period} / "
            f"{url}"
        )

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        page.wait_for_timeout(
            3000
        )

        click_period(
            page,
            period,
        )

        page.wait_for_timeout(
            1500
        )

        items = extract_ranking_items(
            page,
            limit=limit,
        )

        print(
            f"[수집 완료] "
            f"{provider_name} / "
            f"{period}: "
            f"{len(items)}개"
        )

        print(
            "[제목 샘플]",
            [
                item["title"]
                for item in items[:10]
            ],
        )

        return items

    except PlaywrightTimeoutError as error:
        print(
            f"[페이지 시간 초과] "
            f"{provider_name} / "
            f"{period}: "
            f"{error}"
        )

        return []

    except Exception as error:
        print(
            f"[수집 오류] "
            f"{provider_name} / "
            f"{period}: "
            f"{error}"
        )

        return []

    finally:
        page.close()


def load_previous_ranks(
    today,
):
    path = Path(
        "ranking_history.csv"
    )

    if not path.exists():
        return {}, {}, False

    try:
        old_df = pd.read_csv(
            path
        ).fillna("")

    except Exception as error:
        print(
            f"[이전 데이터 로드 실패] "
            f"{error}"
        )

        return {}, {}, False

    required_columns = {
        "date",
        "period",
        "rank",
        "title",
    }

    if old_df.empty:
        return {}, {}, False

    if not required_columns.issubset(
        old_df.columns
    ):
        return {}, {}, False

    old_df["date"] = (
        old_df["date"]
        .astype(str)
    )

    previous_dates = sorted(
        date
        for date in old_df["date"].unique()
        if date and date < today
    )

    if not previous_dates:
        return {}, {}, False

    previous_date = (
        previous_dates[-1]
    )

    previous_df = old_df[
        old_df["date"] == previous_date
    ]

    exact_lookup = {}
    title_lookup = {}

    for _, row in previous_df.iterrows():
        raw_title = row.get(
            "title",
            "",
        )

        if is_bad_title_candidate(
            raw_title
        ):
            continue

        try:
            rank = int(
                float(
                    row.get("rank")
                )
            )

        except Exception:
            continue

        period = str(
            row.get(
                "period",
                "",
            )
        ).strip()

        title = normalize_title(
            raw_title
        )

        open_year = str(
            row.get(
                "open_year",
                "",
            )
        ).strip()

        if not title:
            continue

        exact_lookup[
            (
                period,
                title,
                open_year,
            )
        ] = rank

        title_lookup[
            (
                period,
                title,
            )
        ] = rank

    print(
        f"[이전 순위 기준] "
        f"{previous_date}"
    )

    return (
        exact_lookup,
        title_lookup,
        True,
    )


def validate_result(
    result_df,
):
    if result_df.empty:
        raise RuntimeError(
            "수집 결과가 비어 있습니다."
        )

    invalid_mask = (
        result_df["title"]
        .apply(
            is_bad_title_candidate
        )
    )

    invalid_df = result_df[
        invalid_mask
    ]

    if not invalid_df.empty:
        print(
            "[오류] 잘못 추출된 제목"
        )

        print(
            invalid_df[
                [
                    "period",
                    "rank",
                    "title",
                    "url",
                ]
            ]
            .head(30)
            .to_string(
                index=False
            )
        )

        raise RuntimeError(
            "작품명 대신 평점·기호·"
            "메타정보가 추출되어 "
            "저장을 중단했습니다."
        )

    for period in PERIODS:
        period_df = result_df[
            result_df["period"] == period
        ]

        row_count = len(
            period_df
        )

        unique_count = (
            period_df["title"]
            .nunique()
        )

        print(
            f"[검증] {period}: "
            f"행 {row_count}개 / "
            f"고유 제목 "
            f"{unique_count}개"
        )

        if (
            row_count < 10
            or unique_count < 10
        ):
            raise RuntimeError(
                f"{period} 랭킹 정상 작품명이 "
                f"부족합니다. "
                f"행={row_count}, "
                f"고유제목={unique_count}"
            )

        duplicate_ratio = (
            1
            - unique_count
            / max(
                row_count,
                1,
            )
        )

        if duplicate_ratio > 0.25:
            raise RuntimeError(
                f"{period} 제목 중복률이 "
                f"너무 높습니다: "
                f"{duplicate_ratio:.1%}"
            )


def save_ranking_history(
    new_df,
):
    path = Path(
        "ranking_history.csv"
    )

    new_df = new_df.copy()

    new_df["date"] = (
        new_df["date"]
        .astype(str)
    )

    collected_dates = set(
        new_df["date"].unique()
    )

    if path.exists():
        try:
            old_df = pd.read_csv(
                path
            ).fillna("")

            old_df["date"] = (
                old_df["date"]
                .astype(str)
            )

            old_df = old_df[
                ~old_df["date"].isin(
                    collected_dates
                )
            ].copy()

        except Exception as error:
            print(
                f"[기존 데이터 로드 실패] "
                f"{error}"
            )

            old_df = pd.DataFrame()

    else:
        old_df = pd.DataFrame()

    if old_df.empty:
        combined = new_df

    else:
        columns = list(
            dict.fromkeys(
                list(old_df.columns)
                + list(new_df.columns)
            )
        )

        for column in columns:
            if column not in old_df.columns:
                old_df[column] = ""

            if column not in new_df.columns:
                new_df[column] = ""

        combined = pd.concat(
            [
                old_df[columns],
                new_df[columns],
            ],
            ignore_index=True,
        )

    combined["_period"] = (
        combined["period"]
        .map(PERIOD_ORDER)
        .fillna(99)
    )

    combined["_rank"] = pd.to_numeric(
        combined["rank"],
        errors="coerce",
    ).fillna(9999)

    combined = combined.sort_values(
        [
            "date",
            "_period",
            "_rank",
        ],
        ascending=[
            True,
            True,
            True,
        ],
    )

    combined = combined.drop(
        columns=[
            "_period",
            "_rank",
        ],
        errors="ignore",
    )

    combined.to_csv(
        path,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        "[저장 완료]"
    )

    print(
        combined.groupby(
            [
                "date",
                "period",
            ]
        )
        .size()
        .tail(12)
    )


def main():
    today = datetime.now(
        ZoneInfo("Asia/Seoul")
    ).strftime(
        "%Y-%m-%d"
    )

    (
        previous_exact,
        previous_title,
        has_previous,
    ) = load_previous_ranks(
        today
    )

    overall_by_period = {}

    provider_map = {
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
                "Mozilla/5.0 "
                "(Windows NT 10.0; "
                "Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/150.0.0.0 "
                "Safari/537.36"
            ),
        )

        context.set_default_timeout(
            15000
        )

        for period in PERIODS:
            overall_by_period[
                period
            ] = collect_ranking(
                context=context,
                provider_name="전체",
                url=RANKING_URLS[
                    "전체"
                ],
                period=period,
                limit=100,
            )

        for provider, url in (
            RANKING_URLS.items()
        ):
            if provider == "전체":
                continue

            for period in PERIODS:
                items = collect_ranking(
                    context=context,
                    provider_name=provider,
                    url=url,
                    period=period,
                    limit=100,
                )

                for rank, item in enumerate(
                    items,
                    start=1,
                ):
                    content_key = item[
                        "content_key"
                    ]

                    title_key = normalize_title(
                        item["title"]
                    )

                    provider_map[
                        period
                    ].setdefault(
                        (
                            "content_key",
                            content_key,
                        ),
                        set(),
                    ).add(
                        provider
                    )

                    provider_map[
                        period
                    ].setdefault(
                        (
                            "title",
                            title_key,
                        ),
                        set(),
                    ).add(
                        provider
                    )

                    debug_rows.append(
                        {
                            "date": today,
                            "period": period,
                            "rank": rank,
                            "title": item[
                                "title"
                            ],
                            "content_key": (
                                content_key
                            ),
                            "providerId": "",
                            "providerNameMapped": (
                                provider
                            ),
                            "isActive": True,
                            "source_url": item[
                                "url"
                            ],
                            "raw_offer": "",
                        }
                    )

        context.close()
        browser.close()

    rows = []

    for period in PERIODS:
        items = overall_by_period.get(
            period,
            [],
        )

        for rank, item in enumerate(
            items,
            start=1,
        ):
            title = item["title"]

            title_key = normalize_title(
                title
            )

            open_year = str(
                item.get(
                    "open_year",
                    "",
                )
            ).strip()

            content_key = item.get(
                "content_key",
                "",
            )

            providers = set()

            providers.update(
                provider_map[
                    period
                ].get(
                    (
                        "content_key",
                        content_key,
                    ),
                    set(),
                )
            )

            providers.update(
                provider_map[
                    period
                ].get(
                    (
                        "title",
                        title_key,
                    ),
                    set(),
                )
            )

            previous_rank = (
                previous_exact.get(
                    (
                        period,
                        title_key,
                        open_year,
                    )
                )
            )

            if previous_rank is None:
                previous_rank = (
                    previous_title.get(
                        (
                            period,
                            title_key,
                        )
                    )
                )

            if previous_rank is None:
                delta = 0
                is_new = has_previous

            else:
                delta = (
                    previous_rank
                    - rank
                )

                is_new = False

            rows.append(
                {
                    "date": today,
                    "period": period,
                    "rank": rank,
                    "title": title,
                    "media_type": item.get(
                        "media_type",
                        "",
                    ),
                    "genres": item.get(
                        "genres",
                        "",
                    ),
                    "open_year": open_year,
                    "is_new": is_new,
                    "delta": delta,
                    "providers": ",".join(
                        sorted(
                            providers
                        )
                    ),
                    "content_key": content_key,
                    "url": item.get(
                        "url",
                        "",
                    ),
                }
            )

    if not rows:
        raise RuntimeError(
            "랭킹 데이터를 한 건도 "
            "수집하지 못했습니다."
        )

    result_df = pd.DataFrame(
        rows
    )

    validate_result(
        result_df
    )

    save_ranking_history(
        result_df
    )

    debug_columns = [
        "date",
        "period",
        "rank",
        "title",
        "content_key",
        "providerId",
        "providerNameMapped",
        "isActive",
        "source_url",
        "raw_offer",
    ]

    debug_df = pd.DataFrame(
        debug_rows,
        columns=debug_columns,
    )

    debug_df.to_csv(
        "debug_provider_ids.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print("")
    print(
        "========================================"
    )
    print(
        "ranking_history.csv 저장 완료"
    )
    print(
        "========================================"
    )

    print(
        result_df.groupby(
            "period"
        ).size()
    )

    print("")

    print(
        result_df
        .head(30)
        .to_string(
            index=False
        )
    )

    print("")
    print(
        "OTT별 수집 건수"
    )

    if debug_df.empty:
        print(
            "OTT별 수집 결과 없음"
        )

    else:
        print(
            debug_df.groupby(
                [
                    "period",
                    "providerNameMapped",
                ]
            )
            .size()
            .to_string()
        )


if __name__ == "__main__":
    main()
