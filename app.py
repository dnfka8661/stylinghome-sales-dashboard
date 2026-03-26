import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import re

# 1. 페이지 설정
st.set_page_config(page_title="스타일링홈 실시간 지휘소", layout="wide")

# 2. 구글 시트 연결 (Secrets 방식 - 파일 필요 없음)
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    # 스트림릿 Secrets에서 열쇠 정보 로드
    key_info = json.loads(st.secrets["json_key"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_info, scope)
    client = gspread.authorize(creds)
    doc = client.open_by_key("1gKfciaxjNwDRr-59fpS_fnn2N-Ef_ksqy5OKGco12_Y")
    
    raw_ws = doc.get_worksheet(0)
    goal_ws = doc.worksheet("Goal_Settings")
    task_ws = doc.worksheet("Task_Log")
except Exception as e:
    st.error(f"⚠️ 연결 실패: 스트림릿 Settings > Secrets에 'json_key'를 정확히 넣으셨나요? ({e})")
    st.stop()

# 상품 별칭
CODE_NAME_MAP = {"169814": "오늘의집 메이든 쉐이드", "382503180": "네이버 듀오"}

# 데이터 실시간 로드
def fetch_data():
    raw = pd.DataFrame(raw_ws.get_all_records())
    if not raw.empty:
        raw.columns = [str(c).strip() for c in raw.columns]
        raw['매출'] = pd.to_numeric(raw['결제금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0) + \
                     pd.to_numeric(raw['배송비'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    goals = pd.DataFrame(goal_ws.get_all_records())
    goal_dict = {str(r['code']): r['goal'] for _, r in goals.iterrows()} if not goals.empty else {}
    
    tasks = pd.DataFrame(task_ws.get_all_records())
    if tasks.empty:
        tasks = pd.DataFrame(columns=["할일", "상태", "비고"])
    return raw, goal_dict, tasks

df_raw, dict_goals, df_task = fetch_data()

# ---------------------------------------------------------
# UI 구성
# ---------------------------------------------------------
st.title("🚀 스타일링홈 실시간 통합 지휘소")
t1, t2, t3 = st.tabs(["💰 매출 현황", "🎯 목표 관리", "📝 업무 체크리스트"])

with t1:
    if not df_raw.empty:
        st.metric("총 매출(배송비포함)", f"{df_raw['매출'].sum():,.0f}원")
        st.dataframe(df_raw[['주문일자', '쇼핑몰', '매입처', '매출']], use_container_width=True)

with t2:
    st.header("🎯 주력 상품 목표 관리")
    selected_codes = st.multiselect("분석할 상품 선택", list(CODE_NAME_MAP.keys()), 
                                    format_func=lambda x: f"{x} | {CODE_NAME_MAP[x]}")
    
    for code in selected_codes:
        alias = CODE_NAME_MAP[code]
        saved_goal = dict_goals.get(code, 10000000)
        
        with st.container():
            col_info, col_input, col_bar = st.columns([2, 3, 5])
            with col_info:
                st.subheader(alias)
            with col_input:
                # [해결] 입력창에 콤마가 찍힌 상태로 로드 및 유지
                goal_str = st.text_input(f"{alias} 목표 입력", value=f"{int(saved_goal):,}", key=f"in_{code}")
                try:
                    goal_num = int(re.sub(r'[^0-9]', '', goal_str))
                except:
                    goal_num = 0
                
                if st.button(f"시트에 저장", key=f"save_{code}"):
                    cell = goal_ws.find(code)
                    if cell: goal_ws.update_cell(cell.row, 2, goal_num)
                    else: goal_ws.append_row([code, goal_num])
                    st.success("시트에 저장되었습니다!")
                    st.rerun()
            with col_bar:
                actual = df_raw[df_raw['쇼핑몰 상품코드'].astype(str) == code]['매출'].sum() if not df_raw.empty else 0
                rate = (actual / goal_num * 100) if goal_num > 0 else 0
                st.write(f"현재: {actual:,.0f}원 / 달성률: {rate:.1f}%")
                st.progress(min(rate/100, 1.0))

with t3:
    st.header("📝 업무 체크리스트 편집")
    st.info("수정 후 아래 '저장' 버튼을 누르세요. (+)를 눌러 행을 추가할 수 있습니다.")
    # [해결] 시트가 비어있어도 편집 가능한 데이터 에디터
    edited_task = st.data_editor(df_task, num_rows="dynamic", use_container_width=True, key="task_edit")
    
    if st.button("💾 시트에 최종 저장"):
        try:
            task_ws.clear()
            task_ws.update([edited_task.columns.values.tolist()] + edited_task.fillna("").values.tolist())
            st.success("구글 시트 업데이트 완료!")
        except Exception as e:
            st.error(f"저장 실패: {e}")
