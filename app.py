import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

st.set_page_config(
    page_title="키노라이츠 랭킹 대시보드",
    page_icon="🎬",
    layout="wide"
)

st.markdown("""
<style>
.main {
    background-color: #0f172a;
}
.block-container {
    padding-top: 2rem;
}
h1, h2, h3, p, div {
    color: #f8fafc;
}
.metric-card {
    background: linear-gradient(135deg, #1e293b, #334155);
    padding: 24px;
    border-radius: 20px;
    border: 1px solid #475569;
    box-shadow: 0 8px 24px rgba(0,0,0,0.25);
}
.big-number {
    font-size: 36px;
    font-weight: 800;
    color: #38bdf8;
}
.card-title {
    font-size: 16px;
    color: #cbd5e1;
}
.section-card {
    background-color: #111827;
    padding: 20px;
    border-radius: 18px;
    border: 1px solid #374151;
    margin-bottom: 16px;
}
.new-badge {
    color: #f97316;
    font-weight: 800;
}
.up-badge {
    color: #22c55e;
    font-weight: 800;
}
.down-badge {
    color: #ef4444;
    font-weight: 800;
}
</style>
""", unsafe_allow_html=True)

st.title("🎬 키노라이츠 주간 랭킹 대시보드")
st.caption("매주 월요일 기준 키노라이츠 랭킹 변화 모니터링")

file = Path("ranking_history.csv")

if not file.exists():
    st.error("ranking_history.csv 파일이 없습니다.")
    st.stop()

df = pd.read_csv(file)

if df.empty or len(df) == 0:
    st.error("수집된 데이터가 없습니다.")
    st.stop()

df["date"] = df["date"].astype(str)
df["rank"] = pd.to_numeric(df["rank"], errors="coerce")
df = df.dropna(subset=["rank", "title"])
df["rank"] = df["rank"].astype(int)

dates = sorted(df["date"].unique(), reverse=True)

# 테스트용: 데이터가 1주치뿐이면 가짜 지난주 데이터 자동 생성
demo_mode = False

if len(dates) < 2:
    demo_mode = True

    this_date = dates[0]
    this_week = df[df["date"] == this_date].copy()

    demo_date = (
        datetime.strptime(this_date, "%Y-%m-%d") - timedelta(days=7)
    ).strftime("%Y-%m-%d")

    demo_titles = this_week["title"].tolist()

    # 테스트용 순위 섞기
    demo_titles = demo_titles[3:10] + demo_titles[0:3] + demo_titles[10:15]

    # 일부 작품 제거해서 NEW 발생시키기
    demo_titles = demo_titles[:15]

    last_week = pd.DataFrame({
        "date": [demo_date] * len(demo_titles),
        "rank": range(1, len(demo_titles) + 1),
        "title": demo_titles
    })

    last_date = demo_date

else:
    this_date = dates[0]
    last_date = dates[1]

    this_week = df[df["date"] == this_date].copy()
    last_week = df[df["date"] == last_date].copy()

this_week = this_week.sort_values("rank")
last_week = last_week.sort_values("rank")

merged = this_week.merge(
    last_week[["title", "rank"]],
    on="title",
    how="left",
    suffixes=("_this", "_last")
)

merged["change"] = merged["rank_last"] - merged["rank_this"]

new_df = merged[merged["rank_last"].isna()].copy()

up_df = merged[merged["change"] > 0].copy()
up_df = up_df.sort_values("change", ascending=False)

down_df = merged[merged["change"] < 0].copy()
down_df = down_df.sort_values("change")

maintain_df = merged[merged["change"] == 0].copy()

top10_this = set(this_week[this_week["rank"] <= 10]["title"])
top10_last = set(last_week[last_week["rank"] <= 10]["title"])
top10_keep_rate = round(len(top10_this & top10_last) / 10 * 100, 1)

new_rate = round(len(new_df) / len(this_week) * 100, 1)

if demo_mode:
    st.warning("현재는 1주치 데이터만 있어서 테스트용 지난주 데이터를 자동 생성했습니다. 다음주부터 실제 비교로 바뀝니다.")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="card-title">이번주 수집 작품</div>
        <div class="big-number">{len(this_week)}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="card-title">신규 진입</div>
        <div class="big-number">{len(new_df)}</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="card-title">TOP10 유지율</div>
        <div class="big-number">{top10_keep_rate}%</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="card-title">신규 진입률</div>
        <div class="big-number">{new_rate}%</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

left, right = st.columns([1.1, 1])

with left:
    st.subheader(f"🏆 이번주 TOP20 | {this_date}")

    show_top = this_week[["rank", "title"]].rename(
        columns={"rank": "순위", "title": "작품명"}
    )

    st.dataframe(
        show_top,
        use_container_width=True,
        hide_index=True
    )

with right:
    st.subheader("🔥 신규 진입 작품")

    if len(new_df) > 0:
        for _, row in new_df.head(10).iterrows():
            st.markdown(f"""
            <div class="section-card">
                <span class="new-badge">NEW</span>
                &nbsp; #{int(row['rank_this'])} &nbsp;
                <b>{row['title']}</b>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("신규 진입 작품 없음")

st.markdown("---")

col_up, col_down = st.columns(2)

with col_up:
    st.subheader("▲ 급상승 TOP10")

    if len(up_df) > 0:
        up_show = up_df.head(10).copy()
        up_show["상승폭"] = up_show["change"].astype(int)

        for _, row in up_show.iterrows():
            st.markdown(f"""
            <div class="section-card">
                <span class="up-badge">▲{int(row['상승폭'])}</span>
                &nbsp; <b>{row['title']}</b><br>
                <span style="color:#cbd5e1;">
                    지난주 #{int(row['rank_last'])} → 이번주 #{int(row['rank_this'])}
                </span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("급상승 작품 없음")

with col_down:
    st.subheader("▼ 급하락 TOP10")

    if len(down_df) > 0:
        down_show = down_df.head(10).copy()
        down_show["하락폭"] = down_show["change"].abs().astype(int)

        for _, row in down_show.iterrows():
            st.markdown(f"""
            <div class="section-card">
                <span class="down-badge">▼{int(row['하락폭'])}</span>
                &nbsp; <b>{row['title']}</b><br>
                <span style="color:#cbd5e1;">
                    지난주 #{int(row['rank_last'])} → 이번주 #{int(row['rank_this'])}
                </span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("급하락 작품 없음")

st.markdown("---")

st.subheader("📊 전체 변동표")

change_table = merged.copy()

def make_status(row):
    if pd.isna(row["rank_last"]):
        return "NEW"
    if row["change"] > 0:
        return f"▲{int(row['change'])}"
    if row["change"] < 0:
        return f"▼{abs(int(row['change']))}"
    return "-"

change_table["변동"] = change_table.apply(make_status, axis=1)

change_table = change_table[[
    "rank_this",
    "title",
    "rank_last",
    "변동"
]].rename(columns={
    "rank_this": "이번주 순위",
    "title": "작품명",
    "rank_last": "지난주 순위"
})

st.dataframe(
    change_table,
    use_container_width=True,
    hide_index=True
)
