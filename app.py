import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import re

# 1. 페이지 설정
st.set_page_config(page_title="스타일링홈 매출 지휘소 3.3", layout="wide")

# 2. 구글 시트 보안 연결 (Secrets 방식)
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

try:
    # Secrets에 저장된 json_key를 읽어와 딕셔너리로 변환
    key_dict = json.loads(st.secrets["json_key"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    client = gspread.authorize(creds)
    
    # 시트 연결
    doc = client.open_by_key("1gKfciaxjNwDRr-59fpS_fnn2N-Ef_ksqy5OKGco12_Y")
    raw_ws = doc.get_worksheet(0)
    goal_ws = doc.worksheet("Goal_Settings")
    task_ws = doc.worksheet("Task_Log")
    
except Exception as e:
    st.error(f"⚠️ 연결 실패! Secrets 설정을 확인하세요: {e}")
    st.stop()

# 상품 별칭 설정
CODE_NAME_MAP = {"169814": "오늘의집 메이든 쉐이드", "382503180": "네이버 듀오"}

# 데이터 불러오기 함수
def load_all_data():
    # 매출 데이터
    r_df = pd.DataFrame(raw_ws.get_all_records())
    if not r_df.empty:
        r_df['매출'] = pd.to_numeric(r_df['결제금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0) + \
                      pd.to_numeric(r_df['배송비'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    # 목표 데이터 (영구 저장용)
    g_df = pd.DataFrame(goal_ws.get_all_records())
    g_dict = {str(r['code']): r['goal'] for _, r in g_df.iterrows()} if not g_df.empty else {}
    
    # 업무 데이터
    t_df = pd.DataFrame(task_ws.get_all_records())
    if t_df.empty:
        t_df = pd.DataFrame(columns=["할일", "상태", "비고"])
        
    return r_df, g_dict, t_df

df_raw, dict_goals, df_task = load_all_data()

# ---------------------------------------------------------
# UI 구현
# ---------------------------------------------------------
st.title("🚀 스타일링홈 통합 매출 지휘소")
t1, t2, t3 = st.tabs(["💰 매출 분석", "🎯 목표 영구 설정", "📝 업무 체크리스트"])

with t1:
    if not df_raw.empty:
        st.metric("오늘까지 총 매출", f"{df_raw['매출'].sum():,.0f}원")
        st.dataframe(df_raw[['주문일자', '쇼핑몰', '매입처', '매출']], use_container_width=True)

with t2:
    st.header("🎯 주력 상품 목표 관리 (콤마 입력+영구 저장)")
    selected = st.multiselect("분석할 상품 선택", list(CODE_NAME_MAP.keys()), 
                              format_func=lambda x: f"{x} | {CODE_NAME_MAP[x]}")
    
    for code in selected:
        name = CODE_NAME_MAP[code]
        saved_goal = dict_goals.get(code, 0)
        
        col1, col2, col3 = st.columns([2, 3, 4])
        with col1: st.subheader(name)
        with col2:
            # 입력창에 콤마가 찍힌 상태로 표시
            input_str = st.text_input(f"{name} 목표액", value=f"{int(saved_goal):,}", key=f"goal_{code}")
            clean_num = int(re.sub(r'[^0-9]', '', input_str)) if input_str else 0
            
            if st.button("시트에 영구 저장", key=f"btn_{code}"):
                cell = goal_ws.find(code)
                if cell: goal_ws.update_cell(cell.row, 2, clean_num)
                else: goal_ws.append_row([code, clean_num])
                st.success(f"{name} 저장 성공!")
                st.rerun()
        with col3:
            actual = df_raw[df_raw['쇼핑몰 상품코드'].astype(str) == code]['매출'].sum() if not df_raw.empty else 0
            rate = (actual / clean_num * 100) if clean_num > 0 else 0
            st.write(f"현재: {actual:,.0f}원 ({rate:.1f}%)")
            st.progress(min(rate/100, 1.0))

with t3:
    st.header("📝 업무 체크리스트 (수정 후 저장 필수)")
    # [핵심] 엑셀처럼 직접 편집하는 에디터
    edited_df = st.data_editor(df_task, num_rows="dynamic", use_container_width=True, key="task_edit")
    
    if st.button("💾 변경사항 시트에 저장"):
        task_ws.clear()
        task_ws.update([edited_df.columns.values.tolist()] + edited_df.fillna("").values.tolist())
        st.success("Task_Log 업데이트 완료!")
