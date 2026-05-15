import streamlit as st
import pandas as pd
import json
import html
import re
from pathlib import Path
import streamlit.components.v1 as components

st.set_page_config(
    page_title="키노라이츠 랭킹 / OTT 편성 검색",
    page_icon="🎬",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background:#050b18;
}
.block-container {
    padding-top:0.6rem;
    padding-left:1.1rem;
    padding-right:1.1rem;
    max-width:100%;
}
header, footer {
    visibility:hidden;
}
</style>
""", unsafe_allow_html=True)


OTT_NAMES = [
    "넷플릭스", "티빙", "웨이브", "디즈니+",
    "쿠팡플레이", "왓챠", "애플TV+", "라프텔"
]

RELEASE_PROVIDERS = [
    "전체", "넷플릭스", "티빙", "쿠팡플레이",
    "웨이브", "디즈니+", "왓챠", "애플TV+", "라프텔"
]


def normalize_period(value):
    value = str(value).strip().lower()

    mapping = {
        "일간": "일간",
        "daily": "일간",
        "day": "일간",
        "d": "일간",
        "주간": "주간",
        "weekly": "주간",
        "week": "주간",
        "w": "주간",
        "월간": "월간",
        "monthly": "월간",
        "month": "월간",
        "m": "월간",
    }

    return mapping.get(value, str(value).strip())


def get_kino_base_label(selected_period, latest_date):
    latest = pd.to_datetime(latest_date)

    if selected_period == "일간":
        return latest.strftime("%m.%d 기준")

    if selected_period == "주간":
        weekday = latest.weekday()
        this_week_monday = latest - pd.Timedelta(days=weekday)
        prev_week_monday = this_week_monday - pd.Timedelta(days=7)
        prev_week_sunday = prev_week_monday + pd.Timedelta(days=6)
        return f"{prev_week_monday.strftime('%m.%d')}~{prev_week_sunday.strftime('%m.%d')} 기준"

    if selected_period == "월간":
        prev_month = latest - pd.DateOffset(months=1)
        return prev_month.strftime("%Y.%m 기준")

    return str(latest_date)


def make_meta(row):
    media_type = str(row.get("media_type", "")).upper()
    genres = str(row.get("genres", "")).replace(",", "/")
    open_year = str(row.get("open_year", ""))

    type_text = ""

    if media_type == "MOVIE":
        type_text = "영화"
    elif media_type in ["TV", "SHOW", "SERIES", "DRAMA"]:
        type_text = "드라마"
    elif media_type == "ANIMATION":
        type_text = "애니메이션"

    parts = []

    if type_text:
        parts.append(type_text)

    if genres and genres != "nan":
        parts.append(genres)

    if open_year and open_year != "nan":
        parts.append(open_year)

    return " · ".join(parts)


def is_bad_release_title(title):
    title = str(title).strip()

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

    return False


@st.cache_data(ttl=60)
def load_ranking_data():
    file = Path("ranking_history.csv")

    if not file.exists():
        return pd.DataFrame()

    df = pd.read_csv(file)

    if df.empty:
        return df

    required_cols = [
        "date", "period", "title", "rank", "delta", "is_new",
        "providers", "genres", "open_year", "media_type"
    ]

    for col in required_cols:
        if col not in df.columns:
            df[col] = ""

    df["date"] = df["date"].astype(str)
    df["period"] = df["period"].apply(normalize_period)
    df["title"] = df["title"].fillna("").astype(str)
    df["providers"] = df["providers"].fillna("").astype(str)
    df["genres"] = df["genres"].fillna("").astype(str)
    df["open_year"] = df["open_year"].fillna("").astype(str)
    df["media_type"] = df["media_type"].fillna("").astype(str)

    df["rank"] = pd.to_numeric(df["rank"], errors="coerce")
    df["delta"] = pd.to_numeric(df["delta"], errors="coerce").fillna(0)
    df["is_new"] = df["is_new"].astype(str).str.lower().isin(["true", "1"])

    df = df[df["title"].str.strip() != ""].copy()

    return df


@st.cache_data(ttl=60)
def load_upcoming_releases():
    file = Path("upcoming_releases.csv")

    if not file.exists():
        return pd.DataFrame(columns=[
            "collect_date", "release_date", "title", "provider",
            "genre", "url", "image_url"
        ])

    df = pd.read_csv(file)

    if df.empty:
        return pd.DataFrame(columns=[
            "collect_date", "release_date", "title", "provider",
            "genre", "url", "image_url"
        ])

    for col in ["collect_date", "release_date", "title", "provider", "genre", "url", "image_url"]:
        if col not in df.columns:
            df[col] = ""

    df["collect_date"] = df["collect_date"].fillna("").astype(str)
    df["release_date"] = df["release_date"].fillna("").astype(str)
    df["title"] = df["title"].fillna("").astype(str).str.strip()
    df["provider"] = df["provider"].fillna("").astype(str).str.strip()
    df["genre"] = df["genre"].fillna("").astype(str).str.strip()
    df["url"] = df["url"].fillna("").astype(str).str.strip()
    df["image_url"] = df["image_url"].fillna("").astype(str).str.strip()

    df = df[~df["title"].apply(is_bad_release_title)].copy()

    df["release_date_dt"] = pd.to_datetime(df["release_date"], errors="coerce")
    df = df[df["release_date_dt"].notna()].copy()

    df = df.drop_duplicates(
        subset=["release_date", "title"],
        keep="first"
    )

    df = df.sort_values(
        ["release_date_dt", "title"],
        ascending=[True, True]
    )

    return df


def safe_str(value):
    if pd.isna(value):
        return ""
    return str(value)


def build_payload():
    ranking_df = load_ranking_data()
    upcoming_df = load_upcoming_releases()

    if ranking_df.empty:
        return {
            "ranking": [],
            "upcoming": [],
            "latest_date": "",
            "update_label": "-",
            "base_labels": {
                "일간": "-",
                "주간": "-",
                "월간": "-"
            }
        }

    latest_date = sorted(ranking_df["date"].unique(), reverse=True)[0]

    update_label = "-"
    try:
        update_label = pd.to_datetime(latest_date).strftime("%m.%d 10:00")
    except Exception:
        update_label = str(latest_date)

    base_labels = {
        "일간": get_kino_base_label("일간", latest_date),
        "주간": get_kino_base_label("주간", latest_date),
        "월간": get_kino_base_label("월간", latest_date),
    }

    latest = ranking_df[ranking_df["date"] == latest_date].copy()

    ranking_rows = []

    for _, row in latest.iterrows():
        ranking_rows.append({
            "date": safe_str(row.get("date", "")),
            "period": safe_str(row.get("period", "")),
            "title": safe_str(row.get("title", "")),
            "rank": int(row["rank"]) if pd.notna(row.get("rank")) else None,
            "delta": int(row["delta"]) if pd.notna(row.get("delta")) else 0,
            "is_new": bool(row.get("is_new", False)),
            "providers": safe_str(row.get("providers", "")),
            "meta": make_meta(row),
            "media_type": safe_str(row.get("media_type", "")),
            "genres": safe_str(row.get("genres", "")),
            "open_year": safe_str(row.get("open_year", "")),
        })

    upcoming_rows = []

    for _, row in upcoming_df.iterrows():
        release_dt = row.get("release_date_dt")
        release_date_label = ""

        try:
            release_date_label = pd.to_datetime(release_dt).strftime("%-m/%-d")
        except Exception:
            try:
                release_date_label = pd.to_datetime(release_dt).strftime("%m/%d")
            except Exception:
                release_date_label = safe_str(row.get("release_date", ""))

        release_group = release_date_label

        today = pd.Timestamp.today().normalize()
        try:
            d = pd.to_datetime(release_dt).normalize()
            if d == today:
                release_group = "오늘"
            elif d == today + pd.Timedelta(days=1):
                release_group = "내일"
            else:
                weekday_map = ["월", "화", "수", "목", "금", "토", "일"]
                release_group = f"{d.month}/{d.day}({weekday_map[d.weekday()]})"
        except Exception:
            pass

        upcoming_rows.append({
            "collect_date": safe_str(row.get("collect_date", "")),
            "release_date": safe_str(row.get("release_date", "")),
            "release_label": release_date_label,
            "release_group": release_group,
            "title": safe_str(row.get("title", "")),
            "provider": safe_str(row.get("provider", "")),
            "genre": safe_str(row.get("genre", "")),
            "url": safe_str(row.get("url", "")),
            "image_url": safe_str(row.get("image_url", "")),
        })

    return {
        "ranking": ranking_rows,
        "upcoming": upcoming_rows,
        "latest_date": latest_date,
        "update_label": update_label,
        "base_labels": base_labels,
    }


payload = build_payload()

payload_json = json.dumps(payload, ensure_ascii=False)
payload_json = payload_json.replace("</", "<\\/")

html_template = r"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<style>
* {
    box-sizing:border-box;
}
html, body {
    margin:0;
    padding:0;
    background:#050b18;
    color:#e5edf8;
    font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", "Pretendard", "Apple SD Gothic Neo", sans-serif;
}
body {
    overflow-x:hidden;
}
.dashboard {
    width:100%;
    min-height:1180px;
    padding:22px 24px 28px 24px;
    background:
        radial-gradient(circle at 12% 0%, rgba(42,104,255,0.20), transparent 32%),
        radial-gradient(circle at 88% 4%, rgba(40,109,255,0.16), transparent 28%),
        linear-gradient(180deg, #071326 0%, #050b18 45%, #050b18 100%);
}
.topbar {
    display:flex;
    justify-content:space-between;
    align-items:center;
    margin-bottom:18px;
}
.title-wrap {
    display:flex;
    align-items:center;
    gap:10px;
}
.main-title {
    font-size:29px;
    line-height:1;
    font-weight:900;
    letter-spacing:-0.6px;
    color:#f8fbff;
}
.title-icon {
    font-size:25px;
}
.top-actions {
    display:flex;
    align-items:center;
    gap:12px;
    color:#8fa1bb;
    font-size:14px;
}
.update {
    display:flex;
    align-items:center;
    gap:7px;
}
.export-btn {
    background:rgba(15,28,50,0.88);
    border:1px solid rgba(103,129,168,0.35);
    color:#c9d6e8;
    padding:10px 15px;
    border-radius:9px;
    font-weight:700;
    cursor:pointer;
}
.export-btn:hover {
    border-color:#4d8cff;
    color:#fff;
}
.tabs {
    display:flex;
    gap:34px;
    height:42px;
    border-bottom:1px solid rgba(116,142,180,0.22);
    margin-bottom:14px;
}
.tab {
    position:relative;
    font-size:15px;
    color:#8d9bb0;
    font-weight:800;
    padding:12px 0 13px;
}
.tab.active {
    color:#8fb6ff;
}
.tab.active::after {
    content:"";
    position:absolute;
    left:0;
    right:0;
    bottom:-1px;
    height:3px;
    background:#4b83ff;
    border-radius:10px 10px 0 0;
}
.controls-shell {
    border:1px solid rgba(109,136,177,0.14);
    border-radius:14px;
    background:rgba(8,18,34,0.72);
    padding:18px 20px 16px;
    margin-bottom:12px;
}
.controls-row {
    display:grid;
    grid-template-columns: 1.1fr 1fr 1.55fr;
    gap:18px;
    align-items:start;
}
.left-controls {
    display:flex;
    align-items:center;
    gap:20px;
    flex-wrap:wrap;
}
.control-group {
    display:flex;
    align-items:center;
    gap:12px;
}
.control-label {
    font-size:14px;
    color:#cbd7eb;
    font-weight:800;
    white-space:nowrap;
}
.select-box {
    height:39px;
    min-width:155px;
    border:1px solid rgba(115,144,184,0.32);
    border-radius:8px;
    background:#0f1a2b;
    color:#f3f7ff;
    padding:0 38px 0 14px;
    font-size:14px;
    font-weight:700;
    outline:none;
}
.btv-check {
    grid-column:1 / span 2;
    display:flex;
    align-items:center;
    gap:8px;
    margin-top:13px;
    color:#d6e0ef;
    font-size:14px;
    font-weight:800;
    width:max-content;
}
.btv-check input {
    width:16px;
    height:16px;
    accent-color:#4b83ff;
}
.release-filter {
    grid-column:3;
    grid-row:1 / span 2;
    border:1px dashed rgba(78,139,255,0.9);
    border-radius:14px;
    padding:17px 18px;
    background:linear-gradient(135deg, rgba(18,42,78,0.82), rgba(10,22,42,0.78));
    box-shadow:0 0 26px rgba(55,119,255,0.16);
}
.release-filter-title {
    color:#9fc0ff;
    font-weight:900;
    font-size:14px;
    margin-bottom:13px;
}
.chips {
    display:flex;
    flex-wrap:wrap;
    gap:8px;
    align-items:center;
}
.chip {
    display:inline-flex;
    align-items:center;
    gap:6px;
    border:1px solid rgba(111,139,178,0.35);
    background:rgba(11,22,40,0.96);
    color:#d8e3f5;
    height:32px;
    border-radius:999px;
    padding:0 11px;
    font-size:13px;
    font-weight:800;
    cursor:pointer;
    user-select:none;
}
.chip.active {
    background:#4a80ff;
    color:#fff;
    border-color:#6ea0ff;
    box-shadow:0 0 14px rgba(74,128,255,0.38);
}
.provider-logo {
    width:19px;
    height:19px;
    border-radius:50%;
    display:inline-flex;
    align-items:center;
    justify-content:center;
    font-size:10px;
    font-weight:950;
    background:#0b1220;
}
.logo-netflix { color:#ff3045; background:#050505; }
.logo-tving { color:#ff1745; background:#0b0b0f; }
.logo-coupang { color:#ffffff; background:#1798ff; }
.logo-wavve { color:#ffffff; background:#276cff; }
.logo-disney { color:#bfe2ff; background:#053a54; }
.logo-watcha { color:#ff3f9d; background:#090913; }
.logo-apple { color:#ffffff; background:#111827; }
.logo-laftel { color:#ffffff; background:#5936b4; }
.date-chip {
    height:32px;
    border-radius:9px;
    padding:0 12px;
}
.base-row {
    display:flex;
    align-items:center;
    gap:16px;
    color:#91a4bf;
    font-size:13px;
    background:rgba(13,26,47,0.82);
    border:1px solid rgba(112,140,178,0.12);
    border-radius:9px;
    padding:11px 15px;
    margin-bottom:14px;
}
.info-icon {
    width:18px;
    height:18px;
    display:inline-flex;
    align-items:center;
    justify-content:center;
    border:1px solid rgba(160,176,205,0.45);
    border-radius:50%;
    font-size:12px;
    color:#b7c6dd;
}
.columns {
    display:grid;
    grid-template-columns: 1fr 1fr 1fr 1fr;
    gap:12px;
}
.panel {
    background:rgba(10,21,39,0.84);
    border:1px solid rgba(113,142,181,0.18);
    border-radius:13px;
    padding:13px 12px 15px;
    min-height:615px;
    box-shadow:0 10px 28px rgba(0,0,0,0.16);
}
.panel.release-panel {
    border-color:#367cff;
    box-shadow:0 0 0 1px rgba(50,115,255,0.20), 0 0 24px rgba(51,113,255,0.18);
}
.panel-head {
    display:flex;
    align-items:center;
    justify-content:space-between;
    padding:3px 4px 13px;
}
.panel-title {
    display:flex;
    align-items:center;
    gap:7px;
    font-size:20px;
    font-weight:950;
    letter-spacing:-0.4px;
    color:#f8fbff;
}
.more {
    color:#8da0ba;
    font-size:13px;
    font-weight:800;
}
.card {
    display:grid;
    grid-template-columns:42px 58px minmax(0, 1fr) 32px;
    gap:11px;
    align-items:center;
    min-height:82px;
    background:rgba(13,27,49,0.96);
    border:1px solid rgba(111,139,178,0.18);
    border-radius:9px;
    margin-bottom:7px;
    padding:8px 10px;
}
.card.small-rank {
    grid-template-columns:42px minmax(0, 1fr) 44px;
}
.rank-no {
    font-size:29px;
    color:#dce8fb;
    font-weight:900;
    text-align:center;
}
.poster-placeholder {
    width:58px;
    height:58px;
    border-radius:7px;
    background:linear-gradient(145deg, #263c64, #0b1728);
    display:flex;
    align-items:center;
    justify-content:center;
    color:#83a6df;
    font-size:18px;
    font-weight:900;
    overflow:hidden;
}
.poster-placeholder img {
    width:100%;
    height:100%;
    object-fit:cover;
    display:block;
}
.card-title {
    font-size:15px;
    color:#f5f8ff;
    font-weight:900;
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
    line-height:1.25;
}
.card-meta {
    color:#8da0bb;
    font-size:12px;
    margin-top:5px;
    line-height:1.38;
    display:-webkit-box;
    -webkit-line-clamp:2;
    -webkit-box-orient:vertical;
    overflow:hidden;
}
.status {
    text-align:right;
    font-size:12px;
    font-weight:950;
}
.status.new {
    color:#64ee78;
}
.status.up {
    color:#ff4b36;
}
.status.down {
    color:#ff5a6b;
}
.status.flat {
    color:#6e82a0;
}
.bottom-more {
    margin-top:13px;
    height:52px;
    border-radius:8px;
    border:1px solid rgba(113,142,181,0.18);
    display:flex;
    align-items:center;
    justify-content:center;
    color:#91a4bf;
    font-size:14px;
    font-weight:800;
    background:rgba(12,24,43,0.65);
}
.release-groups {
    max-height:540px;
    overflow:hidden;
}
.release-group-title {
    display:flex;
    align-items:center;
    gap:8px;
    color:#cddbf0;
    font-size:13px;
    font-weight:950;
    padding:0 6px 7px;
    margin-top:2px;
}
.group-count {
    background:#1e2f50;
    color:#a9bbd8;
    border-radius:999px;
    padding:2px 8px;
    font-size:12px;
}
.release-card {
    display:grid;
    grid-template-columns:50px minmax(0, 1fr) 24px;
    gap:10px;
    align-items:center;
    min-height:62px;
    background:rgba(13,27,49,0.96);
    border:1px solid rgba(111,139,178,0.18);
    border-radius:8px;
    margin-bottom:7px;
    padding:8px 9px;
    text-decoration:none;
    color:inherit;
}
.release-card:hover {
    border-color:#4b83ff;
    background:rgba(17,36,66,1);
}
.release-poster {
    width:48px;
    height:48px;
    border-radius:6px;
    background:linear-gradient(145deg,#243c65,#0e1728);
    overflow:hidden;
}
.release-poster img {
    width:100%;
    height:100%;
    object-fit:cover;
    display:block;
}
.release-title {
    font-size:14px;
    color:#f5f8ff;
    font-weight:900;
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
    line-height:1.25;
}
.release-meta {
    color:#8da0bb;
    font-size:12px;
    margin-top:4px;
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
}
.bookmark {
    color:#6e82a0;
    font-size:18px;
}
.empty {
    color:#90a0b8;
    padding:14px 6px;
}
@media (max-width: 1200px) {
    .columns {
        grid-template-columns:1fr 1fr;
    }
    .controls-row {
        grid-template-columns:1fr;
    }
    .release-filter {
        grid-column:1;
        grid-row:auto;
    }
    .btv-check {
        grid-column:1;
    }
}
</style>
</head>
<body>
<div class="dashboard">
    <div class="topbar">
        <div class="title-wrap">
            <div class="title-icon">🎬</div>
            <div class="main-title">키노라이츠 랭킹 / OTT 편성 검색</div>
        </div>
        <div class="top-actions">
            <div class="update">↻ 데이터 업데이트: <span id="updateLabel">-</span></div>
            <button class="export-btn" onclick="exportCSV()">⇩ 내보내기</button>
        </div>
    </div>

    <div class="tabs">
        <div class="tab active">랭킹 대시보드</div>
        <div class="tab">OTT 제공처 검색</div>
    </div>

    <div class="controls-shell">
        <div class="controls-row">
            <div class="left-controls">
                <div class="control-group">
                    <div class="control-label">기간 선택</div>
                    <select class="select-box" id="periodSelect" onchange="renderDashboard()">
                        <option value="일간">일간</option>
                        <option value="주간" selected>주간</option>
                        <option value="월간">월간</option>
                    </select>
                </div>
                <div class="control-group">
                    <div class="control-label">OTT 선택</div>
                    <select class="select-box" id="ottSelect" onchange="renderDashboard()">
                        <option value="전체">전체</option>
                        <option value="넷플릭스">넷플릭스</option>
                        <option value="티빙">티빙</option>
                        <option value="쿠팡플레이">쿠팡플레이</option>
                        <option value="웨이브">웨이브</option>
                        <option value="디즈니+">디즈니+</option>
                        <option value="왓챠">왓챠</option>
                    </select>
                </div>
            </div>

            <label class="btv-check" title="현재는 체크박스만 노출됩니다. B tv+ 편성작 필터 기능은 추후 연결 예정입니다.">
                <input type="checkbox" disabled />
                <span>B tv+ 편성작만 보기</span>
            </label>

            <div class="release-filter">
                <div class="release-filter-title">공개예정작 필터</div>
                <div class="chips" id="providerChips"></div>
                <div style="height:8px"></div>
                <div class="chips" id="rangeChips"></div>
            </div>
        </div>
    </div>

    <div class="base-row">
        <span class="info-icon">i</span>
        <span>랭킹 기준: <b id="baseLabel">-</b></span>
        <span>|</span>
        <span>공개예정작 기준: 오늘 이후</span>
    </div>

    <div class="columns">
        <section class="panel">
            <div class="panel-head">
                <div class="panel-title">🏆 <span id="topTitle">전체 주간 TOP100</span></div>
                <div class="more">더보기 〉</div>
            </div>
            <div id="topList"></div>
            <div class="bottom-more">TOP100 전체 보기 〉</div>
        </section>

        <section class="panel">
            <div class="panel-head">
                <div class="panel-title">🚀 급상승 콘텐츠</div>
                <div class="more">더보기 〉</div>
            </div>
            <div id="upList"></div>
            <div class="bottom-more">급상승 콘텐츠 더보기 〉</div>
        </section>

        <section class="panel">
            <div class="panel-head">
                <div class="panel-title">🔥 신규 진입 콘텐츠</div>
                <div class="more">더보기 〉</div>
            </div>
            <div id="newList"></div>
            <div class="bottom-more">신규 진입 콘텐츠 더보기 〉</div>
        </section>

        <section class="panel release-panel">
            <div class="panel-head">
                <div class="panel-title">🗓 공개 예정작</div>
                <div class="more">더보기 〉</div>
            </div>
            <div class="release-groups" id="releaseList"></div>
            <div class="bottom-more">공개 예정작 전체 보기 〉</div>
        </section>
    </div>
</div>

<script>
const DATA = __PAYLOAD__;

let selectedProvider = "전체";
let selectedRange = "7일";

const providerList = ["전체", "넷플릭스", "티빙", "쿠팡플레이", "웨이브", "디즈니+", "왓챠"];
const rangeList = ["오늘", "7일", "14일"];

function logo(provider) {
    if (!provider || provider === "전체") return "";
    if (provider.includes("넷플")) return '<span class="provider-logo logo-netflix">N</span>';
    if (provider.includes("티빙")) return '<span class="provider-logo logo-tving">T</span>';
    if (provider.includes("쿠팡")) return '<span class="provider-logo logo-coupang">▶</span>';
    if (provider.includes("웨이브")) return '<span class="provider-logo logo-wavve">W</span>';
    if (provider.includes("디즈니")) return '<span class="provider-logo logo-disney">D+</span>';
    if (provider.includes("왓챠")) return '<span class="provider-logo logo-watcha">W</span>';
    if (provider.includes("애플")) return '<span class="provider-logo logo-apple"></span>';
    if (provider.includes("라프텔")) return '<span class="provider-logo logo-laftel">L</span>';
    return "";
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function providerText(item) {
    if (item.provider) return item.provider;
    return "";
}

function renderChips() {
    const providerWrap = document.getElementById("providerChips");
    providerWrap.innerHTML = providerList.map(p => {
        const active = selectedProvider === p ? "active" : "";
        const label = p === "전체" ? "전체" : `${logo(p)} ${p}`;
        return `<div class="chip ${active}" onclick="selectProvider('${p}')">${label}</div>`;
    }).join("");

    const rangeWrap = document.getElementById("rangeChips");
    rangeWrap.innerHTML = rangeList.map(r => {
        const active = selectedRange === r ? "active" : "";
        return `<div class="chip date-chip ${active}" onclick="selectRange('${r}')">${r}</div>`;
    }).join("") + `<div class="chip date-chip">📅</div>`;
}

function selectProvider(p) {
    selectedProvider = p;
    renderDashboard();
}

function selectRange(r) {
    selectedRange = r;
    renderDashboard();
}

function getPeriod() {
    return document.getElementById("periodSelect").value;
}

function getOtt() {
    return document.getElementById("ottSelect").value;
}

function filterRanking() {
    const period = getPeriod();
    const ott = getOtt();

    return DATA.ranking
        .filter(x => x.period === period)
        .filter(x => {
            if (ott === "전체") return true;
            return String(x.providers || "").includes(ott);
        })
        .sort((a, b) => (a.rank || 9999) - (b.rank || 9999));
}

function statusHtml(item) {
    if (item.is_new) return `<div class="status new">NEW</div>`;
    if ((item.delta || 0) > 0) return `<div class="status up">▲ ${item.delta}</div>`;
    if ((item.delta || 0) < 0) return `<div class="status down">▼ ${Math.abs(item.delta)}</div>`;
    return `<div class="status flat">-</div>`;
}

function cardHtml(item, mode="top") {
    const title = escapeHtml(item.title);
    const meta = escapeHtml(item.meta || "");
    const rank = item.rank ?? "-";
    const first = title ? title.slice(0,1) : "?";

    if (mode === "top") {
        return `
        <div class="card">
            <div class="rank-no">${rank}</div>
            <div class="poster-placeholder">${first}</div>
            <div>
                <div class="card-title">${title}</div>
                <div class="card-meta">${meta}</div>
            </div>
            ${statusHtml(item)}
        </div>`;
    }

    return `
    <div class="card small-rank">
        <div class="rank-no">${rank}</div>
        <div>
            <div class="card-title">${title}</div>
            <div class="card-meta">${meta}</div>
        </div>
        ${statusHtml(item)}
    </div>`;
}

function renderRanking() {
    const period = getPeriod();
    const ott = getOtt();
    const base = filterRanking();

    document.getElementById("topTitle").innerText = `${ott} ${period} TOP100`;
    document.getElementById("baseLabel").innerText = DATA.base_labels[period] || "-";

    const top = base.slice(0, 5);
    const up = [...base].filter(x => (x.delta || 0) > 0).sort((a,b) => (b.delta || 0) - (a.delta || 0)).slice(0, 5);
    const newest = [...base].filter(x => x.is_new).slice(0, 5);

    document.getElementById("topList").innerHTML = top.length
        ? top.map(x => cardHtml(x, "top")).join("")
        : `<div class="empty">데이터 없음</div>`;

    document.getElementById("upList").innerHTML = up.length
        ? up.map(x => cardHtml(x, "small")).join("")
        : `<div class="empty">급상승 콘텐츠 없음</div>`;

    document.getElementById("newList").innerHTML = newest.length
        ? newest.map(x => cardHtml(x, "small")).join("")
        : `<div class="empty">신규 진입 콘텐츠 없음</div>`;
}

function parseDate(d) {
    if (!d) return null;
    const dt = new Date(d + "T00:00:00");
    if (isNaN(dt.getTime())) return null;
    return dt;
}

function filterUpcoming() {
    const today = new Date();
    today.setHours(0,0,0,0);

    let end = new Date(today);
    if (selectedRange === "오늘") {
        end.setDate(today.getDate());
    } else if (selectedRange === "14일") {
        end.setDate(today.getDate() + 14);
    } else {
        end.setDate(today.getDate() + 7);
    }

    const hasProvider = DATA.upcoming.some(x => String(x.provider || "").trim() !== "");

    return DATA.upcoming
        .filter(x => {
            const d = parseDate(x.release_date);
            if (!d) return false;
            return d >= today && d <= end;
        })
        .filter(x => {
            if (selectedProvider === "전체") return true;
            if (!hasProvider) return true;
            return String(x.provider || "").includes(selectedProvider);
        })
        .sort((a, b) => {
            const da = parseDate(a.release_date)?.getTime() || 0;
            const db = parseDate(b.release_date)?.getTime() || 0;
            return da - db || String(a.title).localeCompare(String(b.title));
        });
}

function releaseCardHtml(item) {
    const title = escapeHtml(item.title);
    const provider = providerText(item);
    const genre = item.genre ? ` · ${escapeHtml(item.genre)}` : "";
    const providerHtml = provider ? `${logo(provider)} ${escapeHtml(provider)}` : "";
    const meta = providerHtml ? `${providerHtml}${genre} · ${escapeHtml(item.release_label || "")} 공개` : `${escapeHtml(item.release_label || "")} 공개`;
    const img = item.image_url
        ? `<img src="${escapeHtml(item.image_url)}" onerror="this.style.display='none';" />`
        : "";
    const url = item.url || "#";
    const target = item.url ? "_top" : "_self";

    return `
    <a class="release-card" href="${escapeHtml(url)}" target="${target}">
        <div class="release-poster">${img}</div>
        <div>
            <div class="release-title">${title}</div>
            <div class="release-meta">${meta}</div>
        </div>
        <div class="bookmark">♡</div>
    </a>`;
}

function renderUpcoming() {
    const list = filterUpcoming();
    const wrap = document.getElementById("releaseList");

    if (!list.length) {
        wrap.innerHTML = `<div class="empty">공개예정작 데이터가 없습니다.</div>`;
        return;
    }

    const groups = {};
    list.forEach(item => {
        const g = item.release_group || item.release_label || "기타";
        if (!groups[g]) groups[g] = [];
        groups[g].push(item);
    });

    const groupKeys = Object.keys(groups);
    let html = "";

    groupKeys.slice(0, 6).forEach(group => {
        const items = groups[group].slice(0, 3);
        html += `<div class="release-group-title">${escapeHtml(group)} <span class="group-count">${groups[group].length}</span></div>`;
        html += items.map(releaseCardHtml).join("");
    });

    wrap.innerHTML = html;
}

function renderDashboard() {
    renderChips();
    renderRanking();
    renderUpcoming();
}

function exportCSV() {
    const rows = [
        ["section","rank","title","meta","release_date","provider","url"]
    ];

    filterRanking().forEach(x => {
        rows.push(["ranking", x.rank || "", x.title || "", x.meta || "", "", x.providers || "", ""]);
    });

    filterUpcoming().forEach(x => {
        rows.push(["upcoming", "", x.title || "", x.genre || "", x.release_date || "", x.provider || "", x.url || ""]);
    });

    const csv = rows.map(r => r.map(v => `"${String(v).replaceAll('"','""')}"`).join(",")).join("\\n");
    const blob = new Blob(["\\ufeff" + csv], { type:"text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "kino_dashboard_export.csv";
    a.click();
    URL.revokeObjectURL(url);
}

document.getElementById("updateLabel").innerText = DATA.update_label || "-";
renderDashboard();
</script>
</body>
</html>
"""

dashboard_html = html_template.replace("__PAYLOAD__", payload_json)

components.html(
    dashboard_html,
    height=1250,
    scrolling=True
)
