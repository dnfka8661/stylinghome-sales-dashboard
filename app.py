import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import re

# 1. 페이지 설정
st.set_page_config(page_title="스타일링홈 실시간 지휘소", layout="wide")

# 2. 구글 시트 연결 (가장 안전한 로직)
@st.cache_resource
def get_gs_client():
    # Secrets에서 문자열을 읽어와서 실제 데이터로 변환
    raw_json = st.secrets["json_key"]
    # 혹시 모를 줄바꿈 깨짐 방지 처리
    key_dict = json.loads(raw_json, strict=False)
    
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    return gspread.authorize(creds)

try:
    client = get_gs_client()
    doc = client.open_by_key("1gKfciaxjNwDRr-59fpS_fnn2N-Ef_ksqy5OKGco12_Y")
    
    raw_ws = doc.get_worksheet(0)
    goal_ws = doc.worksheet("Goal_Settings")
    task_ws = doc.worksheet("Task_Log")
except Exception as e:
    st.error(f"🚨 연결 실패! Secrets 내용을 다시 확인하세요.\n에러내용: {e}")
    st.info("💡 팁: Secrets 칸에 중괄호 { } 가 빠지지 않았는지, 따옴표가 정확한지 확인해 보세요.")
    st.stop()

# --- 이하 데이터 로드 및 UI 로직 (이전과 동일) ---
CODE_NAME_MAP = {"169814": "오늘의집 메이든 쉐이드", "382503180": "네이버 듀오"}

def fetch_data():
    try:
        r = pd.DataFrame(raw_ws.get_all_records())
        if not r.empty:
            r['매출'] = pd.to_numeric(r['결제금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0) + \
                     pd.to_numeric(r['배송비'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        g = pd.DataFrame(goal_ws.get_all_records())
        g_dict = {str(row['code']): row['goal'] for _, row in g.iterrows()}
        t = pd.DataFrame(task_ws.get_all_records())
        if t.empty: t = pd.DataFrame(columns=["할일", "상태", "등록일", "비고"])
        return r, g_dict, t
    except:
        return pd.DataFrame(), {}, pd.DataFrame(columns=["할일", "상태", "등록일", "비고"])

df_raw, dict_goals, df_task = fetch_data()

st.title("🚀 스타일링홈 실시간 지휘소 v3.5")
t1, t2, t3 = st.tabs(["💰 매출 분석", "🎯 목표 설정", "📝 업무 체크리스트"])

with t2:
    st.header("🎯 주력 상품 목표 관리")
    selected = st.multiselect("상품 선택", list(CODE_NAME_MAP.keys()), format_func=lambda x: f"{x} | {CODE_NAME_MAP[x]}")
    for code in selected:
        name, saved = CODE_NAME_MAP[code], dict_goals.get(code, 0)
        c1, c2, c3 = st.columns([2, 3, 4])
        with col1: st.subheader(name)
        with col2:
            val_str = st.text_input(f"{name} 목표", value=f"{int(saved):,}", key=f"i_{code}")
            num = int(re.sub(r'[^0-9]', '', val_str)) if val_str else 0
            if st.button("저장", key=f"b_{code}"):
                cell = goal_ws.find(code)
                if cell: goal_ws.update_cell(cell.row, 2, num)
                else: goal_ws.append_row([code, num])
                st.success("저장 완료!")
                st.rerun()
        with col3:
            act = df_raw[df_raw['쇼핑몰 상품코드'].astype(str) == code]['매출'].sum() if not df_raw.empty else 0
            rate = (act / num * 100) if num > 0 else 0
            st.write(f"실적: {act:,.0f}원 ({rate:.1f}%)")
            st.progress(min(rate/100, 1.0))

with t3:
    st.header("📝 업무 리스트 편집")
    edited = st.data_editor(df_task, num_rows="dynamic", use_container_width=True, key="ed_v5")
    if st.button("💾 시트에 최종 저장"):
        task_ws.clear()
        task_ws.update([edited.columns.values.tolist()] + edited.fillna("").values.tolist())
        st.success("저장 완료!")
