import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import re

# 1. 페이지 설정
st.set_page_config(page_title="스타일링홈 실시간 지휘소", layout="wide")

# 2. 구글 시트 정보 (에러 방지를 위해 CSV 내보내기 방식 사용)
SHEET_ID = "1gKfciaxjNwDRr-59fpS_fnn2N-Ef_ksqy5OKGco12_Y"
RAW_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
GOAL_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=1052062562"
TASK_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=462337466"

# 상품 별칭 (원하시는 이름을 여기에 계속 추가하세요)
CODE_NAME_MAP = {
    "169814": "오늘의집 메이든 쉐이드",
    "382503180": "네이버 듀오",
}

@st.cache_data(ttl=60)
def load_data(url):
    try:
        df = pd.read_csv(url)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except:
        return pd.DataFrame()

# 데이터 로드
raw_df = load_data(RAW_URL)
goal_df = load_data(GOAL_URL)
task_df = load_data(TASK_URL)

# --- [사이드바 필터 영역] ---
st.sidebar.header("🔍 검색 필터")

if not raw_df.empty:
    # 1. 날짜 필터 (주문일자 기준)
    raw_df['주문일_dt'] = pd.to_datetime(raw_df['주문일자'], errors='coerce')
    min_date = raw_df['주문일_dt'].min().date() if not raw_df['주문일_dt'].isnull().all() else datetime.now().date()
    max_date = raw_df['주문일_dt'].max().date() if not raw_df['주문일_dt'].isnull().all() else datetime.now().date()
    
    date_range = st.sidebar.date_input("🗓️ 분석 기간 선택", [min_date, max_date])
    
    # 2. 쇼핑몰 필터
    all_malls = sorted(raw_df['쇼핑몰'].unique().tolist())
    selected_malls = st.sidebar.multiselect("🛒 쇼핑몰 선택", all_malls, default=all_malls)
    
    # 3. 상품코드 필터
    raw_df['상품코드_str'] = raw_df['쇼핑몰 상품코드'].astype(str)
    all_codes = sorted(raw_df['상품코드_str'].unique().tolist())
    code_display = [f"{c} | {CODE_NAME_MAP.get(c, '미등록')}" for c in all_codes]
    selected_items = st.sidebar.multiselect("📦 상품코드 선택", code_display, default=code_display[:5] if len(code_display) > 5 else code_display)

    # --- 데이터 필터링 적용 ---
    mask = (raw_df['쇼핑몰'].isin(selected_malls)) & \
           (raw_df['상품코드_str'].isin([s.split(" | ")[0] for s in selected_items]))
    
    if len(date_range) == 2:
        mask = mask & (raw_df['주문일_dt'].dt.date >= date_range[0]) & (raw_df['주문일_dt'].dt.date <= date_range[1])
    
    filtered_df = raw_df[mask].copy()
    
    # 매출 계산
    filtered_df['매출'] = pd.to_numeric(filtered_df['결제금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0) + \
                         pd.to_numeric(filtered_df['배송비'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

# ---------------------------------------------------------
# 메인 UI 레이아웃
# ---------------------------------------------------------
st.title("📊 스타일링홈 통합 매출 지휘소 v5.5")
t1, t2, t3 = st.tabs(["💰 실시간 매출 현황", "🎯 다중 목표 관리", "📝 업무 체크리스트"])

with t1:
    if not raw_df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("선택 기간 총 매출", f"{filtered_df['매출'].sum():,.0f}원")
        c2.metric("주문건수", f"{len(filtered_df):,}건")
        c3.metric("쇼핑몰 수", f"{filtered_df['쇼핑몰'].nunique()}개")
        
        st.divider()
        st.subheader("🏢 필터링된 실적 현황")
        st.dataframe(filtered_df[['주문일자', '쇼핑몰', '매입처', '매출']], use_container_width=True, hide_index=True)
    else:
        st.error("데이터 로드 실패")

with t2:
    st.header("🎯 주력 상품 목표 관리")
    st.caption("※ 기간 필터와 상관없이 상품별 누적 실적을 보여줍니다.")
    
    goal_dict = {str(row['code']): row['goal'] for _, row in goal_df.iterrows()} if not goal_df.empty else {}
    
    # 사이드바에서 선택된 상품들만 루프 돌림
    for item in selected_items:
        code = item.split(" | ")[0].strip()
        name = CODE_NAME_MAP.get(code, f"상품 {code}")
        
        target = goal_dict.get(code, 10000000)
        actual = raw_df[raw_df['상품코드_str'] == code]['매출'].sum()
        achievement = (actual / target * 100) if target > 0 else 0
        
        col_info, col_bar = st.columns([3, 7])
        with col_info:
            st.markdown(f"### {name}")
            st.write(f"목표: {target:,.0f}원 / 현재: **{actual:,.0f}원**")
        with col_bar:
            st.write(f"달성률: **{achievement:.1f}%**")
            st.progress(min(achievement/100, 1.0))
        st.write("---")

with t3:
    st.header("📝 업무 체크리스트")
    if not task_df.empty:
        st.dataframe(task_df, use_container_width=True, hide_index=True)
    else:
        st.info("Task_Log 데이터가 비어있습니다.")
