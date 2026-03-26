import streamlit as st
import pandas as pd
import re

# 1. 페이지 설정
st.set_page_config(page_title="스타일링홈 매출 분석 시스템", layout="wide")

# 2. 구글 시트 정보 (에러 방지를 위해 CSV 내보내기 방식 사용)
SHEET_ID = "1gKfciaxjNwDRr-59fpS_fnn2N-Ef_ksqy5OKGco12_Y"
RAW_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
GOAL_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=1052062562"
TASK_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=462337466"

# 상품 별칭 (여기에 추가하시면 대시보드에 이름으로 뜹니다)
CODE_NAME_MAP = {
    "169814": "오늘의집 메이든 쉐이드",
    "382503180": "네이버 듀오",
    # 추가 상품이 있다면 여기에 "코드": "이름" 형태로 넣어주세요
}

@st.cache_data(ttl=60) # 1분마다 자동 갱신
def load_data(url):
    try:
        df = pd.read_csv(url)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except:
        return pd.DataFrame()

# 데이터 로드
df_raw = load_data(RAW_URL)
df_goal = load_csv_data = load_data(GOAL_URL) # 목표값 시트
df_task = load_data(TASK_URL) # 업무 리스트 시트

# 매출 데이터 숫자 전처리
if not df_raw.empty:
    df_raw['매출'] = pd.to_numeric(df_raw['결제금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0) + \
                     pd.to_numeric(df_raw['배송비'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    df_raw['상품코드_str'] = df_raw['쇼핑몰 상품코드'].astype(str)

# ---------------------------------------------------------
# 메인 UI
# ---------------------------------------------------------
st.title("📊 스타일링홈 실시간 통합 지휘소 v5.0")
t1, t2, t3 = st.tabs(["💰 실시간 매출 현황", "🎯 다중 목표 관리", "📝 업무 체크리스트"])

# --- 탭 1: 전체 현황 ---
with t1:
    if not df_raw.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("총 매출(배송비포함)", f"{df_raw['매출'].sum():,.0f}원")
        c2.metric("총 주문건수", f"{len(df_raw):,}건")
        c3.metric("평균 객단가", f"{(df_raw['매출'].sum()/len(df_raw)):,.0f}원")
        
        st.divider()
        st.subheader("🏢 매입처/쇼핑몰별 실적 (상위 10개)")
        col_a, col_b = st.columns(2)
        with col_a:
            st.dataframe(df_raw.groupby('매입처')['매출'].sum().sort_values(ascending=False).head(10), use_container_width=True)
        with col_b:
            st.dataframe(df_raw.groupby('쇼핑몰')['매출'].sum().sort_values(ascending=False).head(10), use_container_width=True)

# --- 탭 2: 다중 목표 관리 (복구 완료!) ---
with t2:
    st.header("🎯 주력 상품군 집중 목표 관리")
    
    if not df_raw.empty:
        # 1. 데이터에 존재하는 모든 상품코드 추출
        all_product_codes = sorted(df_raw['상품코드_str'].unique().tolist())
        
        # 2. 선택창 옵션 생성 (별칭이 있으면 별칭으로 표시)
        display_options = [f"{c} | {CODE_NAME_MAP.get(c, '미등록 상품')}" for c in all_product_codes]
        
        # 3. 사라졌던 왼쪽 다중 선택창 복구!
        selected_items = st.multiselect("분석할 상품을 선택하세요 (여러 개 선택 가능)", display_options, default=display_options[:2])
        
        st.divider()
        
        # 4. 시트에서 저장된 목표값 가져오기
        goal_dict = {str(row['code']): row['goal'] for _, row in df_goal.iterrows()} if not df_goal.empty else {}

        for item in selected_items:
            code = item.split(" | ")[0].strip()
            name = CODE_NAME_MAP.get(code, f"상품코드: {code}")
            
            # 목표값 (시트에 없으면 기본 1,000만 원)
            target = goal_dict.get(code, 10000000)
            actual = df_raw[df_raw['상품코드_str'] == code]['매출'].sum()
            achievement = (actual / target * 100) if target > 0 else 0
            
            with st.container():
                col_info, col_bar = st.columns([3, 7])
                with col_info:
                    st.subheader(name)
                    st.write(f"목표: {target:,.0f}원")
                    st.write(f"현재: **{actual:,.0f}원**")
                with col_bar:
                    st.write(f"달성률: **{achievement:.1f}%**")
                    st.progress(min(achievement/100, 1.0))
            st.write("")
    else:
        st.warning("매출 데이터가 없습니다.")

# --- 탭 3: 업무 체크리스트 (복구 완료!) ---
with t3:
    st.header("📝 업무 체크리스트 현황")
    st.info("구글 시트(Task_Log)의 내용을 실시간으로 보여줍니다.")
    if not df_task.empty:
        # 필터링 기능 추가 (완료 제외 등)
        show_all = st.checkbox("완료된 항목 포함", value=True)
        display_task = df_task if show_all else df_task[df_task['상태'] != '완료']
        
        st.dataframe(display_task, use_container_width=True, hide_index=True)
    else:
        st.error("업무 리스트 데이터를 불러올 수 없습니다. 시트의 GID 값을 확인해 주세요.")
