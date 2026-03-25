import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date

# 1. 페이지 설정
st.set_page_config(page_title="스타일링홈 매출 분석 시스템", layout="wide")

# 2. 구글 시트 연결 정보
SHEET_ID = "1gKfciaxjNwDRr-59fpS_fnn2N-Ef_ksqy5OKGco12_Y"
BASE_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
RAW_URL = f"{BASE_URL}&gid=0"
TASK_URL = f"{BASE_URL}&gid=462337466"

# [핵심] 상품코드별 명칭 매핑 사전
CODE_NAME_MAP = {
    "169814": "오늘의집 메이든 쉐이드",
    "382503180": "네이버 듀오"
}

@st.cache_data
def load_all_data():
    try:
        raw = pd.read_csv(RAW_URL)
        task = pd.read_csv(TASK_URL)
        for d in [raw, task]:
            d.columns = [str(c).strip() for c in d.columns]
            
        def auto_map(df, keywords, default_name):
            for k in keywords:
                for c in df.columns:
                    if k in c: return df.rename(columns={c: default_name})
            if default_name not in df.columns:
                df[default_name] = 0 if any(x in default_name for x in ["금액", "수량", "배송비"]) else ""
            return df

        raw = auto_map(raw, ['주문일자', '주문일'], '표준_주문일')
        raw = auto_map(raw, ['결제금액', '매출'], '표준_결제금액')
        raw = auto_map(raw, ['EAx수량', '판매수량', '수량'], '표준_판매수량')
        raw = auto_map(raw, ['배송비'], '표준_배송비')
        raw = auto_map(raw, ['쇼핑몰 상품코드', '상품코드'], '표준_상품코드')
        raw = auto_map(raw, ['쇼핑몰', '판매처'], '표준_쇼핑몰')
        raw = auto_map(raw, ['매입처'], '표준_매입처')
        raw = auto_map(raw, ['상품약어', '품명'], '표준_상품약어')

        raw['표준_주문일'] = pd.to_datetime(raw['표준_주문일'], errors='coerce').dt.date
        raw = raw.dropna(subset=['표준_주문일'])
        for c in ['표준_결제금액', '표준_판매수량', '표준_배송비']:
            raw[c] = pd.to_numeric(raw[c].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        raw['표준_총매출액'] = raw['표준_결제금액'] + raw['표준_배송비']
        return raw, task
    except Exception as e:
        st.error(f"데이터 로드 중 오류: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_raw, df_task = load_all_data()

# --- 사이드바 및 기본 필터 ---
if not df_raw.empty:
    st.sidebar.header("🔍 데이터 통합 필터")
    min_d, max_d = df_raw['표준_주문일'].min(), df_raw['표준_주문일'].max()
    date_range = st.sidebar.date_input("조회 기간 설정", [min_d, max_d])
    shops = ["전체"] + sorted(df_raw['표준_쇼핑몰'].unique().tolist())
    sel_shops = st.sidebar.multiselect("판매처 선택", shops, default="전체")

    df_f = df_raw.copy()
    if len(date_range) == 2:
        df_f = df_f[(df_f['표준_주문일'] >= date_range[0]) & (df_f['표준_주문일'] <= date_range[1])]
    if "전체" not in sel_shops and sel_shops:
        df_f = df_f[df_f['표준_쇼핑몰'].isin(sel_shops)]

    st.title("📊 스타일링홈 매출 분석 지휘소 2.0")
    t1, t2, t3 = st.tabs(["💰 실시간 매출 현황", "🎯 다중 목표 관리", "📝 업무 체크리스트"])

    with t1:
        # 기존 매출 현황 레이아웃 (매입처, 쇼핑몰, 상품약어 순위)
        c_m1, c_m2, c_m3 = st.columns(3)
        c_m1.metric("총 매출액(배송비포함)", f"{df_f['표준_총매출액'].sum():,.0f}원")
        c_m2.metric("총 판매수량", f"{int(df_f['표준_판매수량'].sum()):,}개")
        c_m3.metric("주문 건수", f"{len(df_f):,}건")
        st.divider()
        col_vendor, col_shop = st.columns(2)
        with col_vendor:
            st.subheader("🏢 매입처별 실적")
            v_df = df_f.groupby('표준_매입처')['표준_총매출액'].sum().sort_values(ascending=False).reset_index()
            st.dataframe(v_df, use_container_width=True, hide_index=True)
        with col_shop:
            st.subheader("🛒 쇼핑몰별 실적")
            s_df = df_f.groupby('표준_쇼핑몰')['표준_총매출액'].sum().sort_values(ascending=False).reset_index()
            st.dataframe(s_df, use_container_width=True, hide_index=True)
        st.divider()
        st.subheader("📦 상품약어별 판매 수량")
        p_df = df_f.groupby('표준_상품약어')['표준_판매수량'].sum().sort_values(ascending=False).reset_index()
        st.dataframe(p_df, use_container_width=True, hide_index=True)

    with t2:
        st.header("🎯 주력 상품군 집중 목표 관리")
        
        # 상품코드 리스트 준비 (별칭 포함)
        all_raw_codes = sorted(df_raw['표준_상품코드'].unique().astype(str).tolist())
        display_options = []
        for code in all_raw_codes:
            alias = CODE_NAME_MAP.get(code, "")
            display_text = f"{code} | {alias}" if alias else code
            display_options.append(display_text)

        selected_display = st.multiselect("관리할 상품을 선택하세요", display_options, default=display_options[:1])
        st.divider()

        if selected_display:
            for display_item in selected_display:
                # 선택된 텍스트에서 코드만 다시 추출
                current_code = display_item.split(" | ")[0].strip()
                custom_name = CODE_NAME_MAP.get(current_code, "")
                
                with st.container():
                    col_info, col_input, col_bar = st.columns([2.5, 2, 4.5])
                    
                    with col_info:
                        if custom_name:
                            st.subheader(custom_name)
                            st.caption(f"상품코드: {current_code}")
                        else:
                            # 별칭이 없는 경우 기존처럼 상품약어를 가져옴
                            p_name = df_raw[df_raw['표준_상품코드'].astype(str) == current_code]['표준_상품약어'].iloc[0]
                            st.write(f"**[{current_code}]**")
                            st.caption(p_name)
                    
                    with col_input:
                        p_goal = st.number_input(f"목표(원)", value=10000000, step=1000000, key=f"goal_{current_code}")
                    
                    with col_bar:
                        if len(date_range) == 2:
                            p_actual = df_f[df_f['표준_상품코드'].astype(str) == current_code]['표준_총매출액'].sum()
                            p_rate = (p_actual / p_goal * 100) if p_goal > 0 else 0
                            st.write(f"기간 매출: **{p_actual:,.0f}원** (달성률: {p_rate:.1f}%)")
                            st.progress(min(p_rate/100, 1.0))
                st.write("") 
        else:
            st.info("조회할 상품을 선택해 주세요.")

    with t3:
        st.subheader("📋 실시간 업무 현황")
        st.dataframe(df_task, use_container_width=True, hide_index=True)

else:
    st.warning("데이터를 불러올 수 없습니다.")