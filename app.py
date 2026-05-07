import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="키노라이츠 랭킹",
    layout="wide"
)

st.title("🎬 키노라이츠 주간 랭킹 대시보드")

file = Path("ranking_history.csv")

if not file.exists():
    st.warning("랭킹 데이터가 없습니다.")
    st.stop()

df = pd.read_csv(file)

dates = sorted(df["date"].unique(), reverse=True)

if len(dates) < 2:
    st.warning("2주 이상 데이터가 필요합니다.")
    st.dataframe(df)
    st.stop()

this_date = dates[0]
last_date = dates[1]

this_week = df[df["date"] == this_date].copy()
last_week = df[df["date"] == last_date].copy()

merged = this_week.merge(
    last_week[["title", "rank"]],
    on="title",
    how="left",
    suffixes=("_this", "_last")
)

merged["change"] = merged["rank_last"] - merged["rank_this"]

# 신규 진입
new_df = merged[merged["rank_last"].isna()].copy()

# 상승
up_df = merged[merged["change"] > 0].sort_values(
    "change",
    ascending=False
)

# 하락
down_df = merged[merged["change"] < 0].sort_values(
    "change"
)

# TOP20
st.subheader(f"📈 이번주 TOP20 ({this_date})")

st.dataframe(
    this_week[["rank", "title"]]
    .rename(columns={
        "rank": "순위",
        "title": "작품명"
    }),
    use_container_width=True
)

col1, col2 = st.columns(2)

# 신규 진입
with col1:
    st.subheader("🔥 신규 진입")

    if len(new_df) > 0:
        st.dataframe(
            new_df[["rank_this", "title"]]
            .rename(columns={
                "rank_this": "순위",
                "title": "작품명"
            }),
            use_container_width=True
        )
    else:
        st.info("신규 진입 없음")

# 급상승
with col2:
    st.subheader("▲ 급상승")

    if len(up_df) > 0:
        up_show = up_df.copy()
        up_show["상승폭"] = "▲" + up_show["change"].astype(int).astype(str)

        st.dataframe(
            up_show[[
                "title",
                "rank_last",
                "rank_this",
                "상승폭"
            ]]
            .rename(columns={
                "title": "작품명",
                "rank_last": "지난주",
                "rank_this": "이번주"
            }),
            use_container_width=True
        )
    else:
        st.info("상승 작품 없음")

# 급하락
st.subheader("▼ 급하락")

if len(down_df) > 0:
    down_show = down_df.copy()

    down_show["하락폭"] = "▼" + (
        down_show["change"].abs().astype(int).astype(str)
    )

    st.dataframe(
        down_show[[
            "title",
            "rank_last",
            "rank_this",
            "하락폭"
        ]]
        .rename(columns={
            "title": "작품명",
            "rank_last": "지난주",
            "rank_this": "이번주"
        }),
        use_container_width=True
    )
else:
    st.info("하락 작품 없음")
