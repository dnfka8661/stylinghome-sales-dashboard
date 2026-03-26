import streamlit as st
import pandas as pd
import re

# 1. 페이지 설정
st.set_page_config(page_title="스타일링홈 매출 분석 시스템", layout="wide")

# 2. 구글 시트 정보 (공유 설정된 링크 사용)
SHEET_ID = "1gKfciaxjNwDRr-59fpS_fnn2N-Ef_ksqy5OKGco12_Y"
# 매출 데이터 탭 (GID=0)
RAW_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
# Goal_Settings 탭 (GID=1052062562)
GOAL_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=1052062562"
# Task_Log 탭 (GID=462337466)
TASK_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=462337466"

# 상품 별칭 설정
CODE_NAME_MAP = {"169814": "오늘의집 메이든 쉐이드", "382503180": "네이버 듀오"}

@st.cache_data(ttl=60) # 1분마다 새로고침
def load_csv(url):
    try:
        df = pd.read_csv(url)
        return df
    except:
        return pd.DataFrame()

# 데이터 로드
df_raw = load_csv(RAW_URL)
df_goal = load_csv(GOAL_URL)
df_task = load_csv(TASK_URL)

# ---------------------------------------------------------
# UI 구성
# ---------------------------------------------------------
st.title("📊 스타일링홈 매출 분석 지휘소 (안정 버전)")
tab1, tab2, tab3 = st.tabs(["💰 매출 현황", "🎯 목표 관리", "📝 업무 체크리스트"])

with tab1:
    if not df_raw.empty:
        # 금액 데이터 숫자 변환
        df_raw['매출'] = pd.to_numeric(df_raw['결제금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0) + \
                         pd.to_numeric(df_raw['배송비'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        st.metric("총 매출(배송비포함)", f"{df_raw['매출'].sum():,.0f}원")
        st.divider()
        st.subheader("실시간 매출 데이터")
        st.dataframe(df_raw[['주문일자', '쇼핑몰', '매입처', '매출']], use_container_width=True)

with tab2:
    st.header("🎯 주력 상품 목표 관리")
    st.caption("※ 이 버전은 조회가 주 목적입니다. 목표액은 시트에서 직접 수정해 주세요.")
    
    # 시트에서 목표값 읽어오기
    goal_dict = {str(row['code']): row['goal'] for _, row in df_goal.iterrows()} if not df_goal.empty else {}
    
    selected = st.multiselect("분석할 상품 선택", list(CODE_NAME_MAP.keys()), format_func=lambda x: f"{x} | {CODE_NAME_MAP[x]}")
    
    for code in selected:
        name = CODE_NAME_MAP[code]
        goal_val = goal_dict.get(code, 10000000)
        
        actual = df_raw[df_raw['쇼핑몰 상품코드'].astype(str) == code]['매출'].sum() if not df_raw.empty else 0
        rate = (actual / goal_val * 100) if goal_val > 0 else 0
        
        st.subheader(f"{name}")
        col_res, col_bar = st.columns([1, 2])
        col_res.write(f"목표: **{goal_val:,.0f}원** / 실적: **{actual:,.0f}원**")
        col_bar.progress(min(rate/100, 1.0))
        st.write(f"달성률: {rate:.1f}%")

with tab3:
    st.header("📝 업무 체크리스트 (조회 전용)")
    st.info("구글 시트의 'Task_Log' 탭에서 내용을 수정하면 여기에 반영됩니다.")
    if not df_task.empty:
        st.dataframe(df_task, use_container_width=True, hide_index=True)
