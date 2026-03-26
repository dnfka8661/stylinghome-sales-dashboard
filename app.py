import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re

# 1. 페이지 설정
st.set_page_config(page_title="스타일링홈 실시간 지휘소", layout="wide")

# 2. 구글 시트 보안 연결 (Secrets 방식)
@st.cache_resource
def get_gs_client():
    # Secrets에서 정보 로드
    creds_dict = dict(st.secrets["gcp_service_account"])
    
    # [핵심] Invalid JWT Signature 에러 방지를 위한 줄바꿈 교정 로직
    pk = creds_dict["private_key"]
    if "\\n" in pk:
        creds_dict["private_key"] = pk.replace("\\n", "\n")
    
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

try:
    client = get_gs_client()
    doc = client.open_by_key("1gKfciaxjNwDRr-59fpS_fnn2N-Ef_ksqy5OKGco12_Y")
    
    raw_ws = doc.get_worksheet(0)
    goal_ws = doc.worksheet("Goal_Settings")
    task_ws = doc.worksheet("Task_Log")
except Exception as e:
    st.error(f"🚨 연결 실패! 에러 내용: {e}")
    st.info("💡 해결방법: 스트림릿 Secrets 칸의 [gcp_service_account] 설정이 정확한지 다시 확인해 보세요.")
    st.stop()

# 상품 별칭 설정
CODE_NAME_MAP = {"169814": "오늘의집 메이든 쉐이드", "382503180": "네이버 듀오"}

# 데이터 실시간 로드 함수
def fetch_data():
    try:
        # 매출 데이터
        r = pd.DataFrame(raw_ws.get_all_records())
        if not r.empty:
            r['매출'] = pd.to_numeric(r['결제금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0) + \
                     pd.to_numeric(r['배송비'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        # 목표 데이터
        g = pd.DataFrame(goal_ws.get_all_records())
        g_dict = {str(row['code']): row['goal'] for _, row in g.iterrows()}
        
        # 업무 리스트 데이터
        t = pd.DataFrame(task_ws.get_all_records())
        if t.empty:
            t = pd.DataFrame(columns=["할일", "상태", "등록일", "비고"])
        return r, g_dict, t
    except:
        return pd.DataFrame(), {}, pd.DataFrame(columns=["할일", "상태", "등록일", "비고"])

df_raw, dict_goals, df_task = fetch_data()

# ---------------------------------------------------------
# UI 구성
# ---------------------------------------------------------
st.title("📊 스타일링홈 실시간 통합 지휘소 v3.8")
tab1, tab2, tab3 = st.tabs(["💰 매출 현황", "🎯 목표 영구 관리", "📝 업무 체크리스트"])

# --- 탭 1: 매출 현황 ---
with tab1:
    if not df_raw.empty:
        st.metric("총 매출(배송비포함)", f"{df_raw['매출'].sum():,.0f}원")
        st.dataframe(df_raw[['주문일자', '쇼핑몰', '매입처', '매출']], use_container_width=True)
    else:
        st.warning("매출 데이터를 불러올 수 없습니다.")

# --- 탭 2: 다중 목표 관리 (입력창 콤마 + 영구 저장) ---
with tab2:
    st.header("🎯 주력 상품 목표 관리")
    selected = st.multiselect("분석할 상품 선택", list(CODE_NAME_MAP.keys()), 
                                    format_func=lambda x: f"{x} | {CODE_NAME_MAP[x]}")
    for code in selected:
        name = CODE_NAME_MAP[code]
        saved_goal = dict_goals.get(code, 0)
        
        col1, col2, col3 = st.columns([2, 3, 4])
        with col1:
            st.subheader(name)
        with col2:
            # 입력창에 콤마가 찍힌 상태로 표시
            goal_str = st.text_input(f"{name} 목표 입력", value=f"{int(saved_goal):,}", key=f"goal_{code}")
            # 숫자만 추출
            try:
                clean_num = int(re.sub(r'[^0-9]', '', goal_str))
            except:
                clean_num = 0
            
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

# --- 탭 3: 업무 체크리스트 (실시간 편집 및 저장) ---
with tab3:
    st.header("📝 업무 체크리스트 편집")
    st.info("수정 후 아래 '저장' 버튼을 누르세요. (+)를 눌러 행을 추가할 수 있습니다.")
    
    edited_df = st.data_editor(df_task, num_rows="dynamic", use_container_width=True, key="task_editor")
    
    if st.button("💾 변경사항 시트에 영구 저장"):
        try:
            task_ws.clear()
            header = edited_df.columns.values.tolist()
            data = edited_df.fillna("").values.tolist()
            task_ws.update([header] + data)
            st.success("구글 시트 업데이트 완료!")
        except Exception as e:
            st.error(f"저장 중 오류 발생: {e}")
