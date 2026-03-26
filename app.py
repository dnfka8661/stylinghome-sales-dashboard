import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re

# 1. 페이지 설정
st.set_page_config(page_title="스타일링홈 실시간 지휘소", layout="wide")

# 2. 구글 시트 보안 연결 (Secrets 방식 최적화)
@st.cache_resource(ttl=3600)
def get_gs_client():
    # Secrets에서 섹션 통째로 가져오기 (dict() 변환 에러 방지)
    creds_info = st.secrets["gcp_service_account"]
    
    # [핵심] JSON 호환을 위해 딕셔너리로 확실히 변환
    key_dict = {
        "type": creds_info["type"],
        "project_id": creds_info["project_id"],
        "private_key_id": creds_info["private_key_id"],
        "private_key": creds_info["private_key"].replace("\\n", "\n"),
        "client_email": creds_info["client_email"],
        "client_id": creds_info["client_id"],
        "auth_uri": creds_info["auth_uri"],
        "token_uri": creds_info["token_uri"],
        "auth_provider_x509_cert_url": creds_info["auth_provider_x509_cert_url"],
        "client_x509_cert_url": creds_info["client_x509_cert_url"]
    }
    
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
    st.error(f"🚨 연결 실패! 에러 내용: {e}")
    st.info("💡 팁: 스트림릿 Secrets 설정에서 제가 드린 내용을 한 줄씩 정확히 넣었는지 확인하세요.")
    st.stop()

# --- 데이터 처리 및 UI 로직 (MD님 요청 사항 완벽 반영) ---
CODE_NAME_MAP = {"169814": "오늘의집 메이든 쉐이드", "382503180": "네이버 듀오"}

def fetch_data():
    try:
        # 매출 데이터 로드 및 전처리
        r = pd.DataFrame(raw_ws.get_all_records())
        if not r.empty:
            for col in ['결제금액', '배송비']:
                if col in r.columns:
                    r[col] = pd.to_numeric(r[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            r['매출'] = r['결제금액'] + r['배송비']
            r['쇼핑몰 상품코드'] = r['쇼핑몰 상품코드'].astype(str)
            
        # 목표 데이터 (영구 저장용)
        g = pd.DataFrame(goal_ws.get_all_records())
        g_dict = {str(row['code']): row['goal'] for _, row in g.iterrows()} if not g.empty else {}
        
        # 업무 체크리스트 (직접 편집용)
        t = pd.DataFrame(task_ws.get_all_records())
        if t.empty: t = pd.DataFrame(columns=["할일", "상태", "비고"])
        
        return r, g_dict, t
    except:
        return pd.DataFrame(), {}, pd.DataFrame(columns=["할일", "상태", "비고"])

df_raw, dict_goals, df_task = fetch_data()

# ---------------------------------------------------------
# UI 구성
# ---------------------------------------------------------
st.title("📊 스타일링홈 실시간 통합 지휘소 v4.6")
tab1, tab2, tab3 = st.tabs(["💰 매출 분석", "🎯 목표 영구 관리", "📝 업무 체크리스트"])

with tab1:
    if not df_raw.empty:
        st.metric("오늘까지 총 매출 (배송비 포함)", f"{df_raw['매출'].sum():,.0f}원")
        st.dataframe(df_raw[['주문일자', '쇼핑몰', '매입처', '매출']], use_container_width=True)

with tab2:
    st.header("🎯 주력 상품 목표 관리 (콤마 입력+저장)")
    selected = st.multiselect("분석할 상품 선택", list(CODE_NAME_MAP.keys()), 
                              format_func=lambda x: f"{x} | {CODE_NAME_MAP[x]}")
    for code in selected:
        name = CODE_NAME_MAP[code]
        saved_goal = dict_goals.get(code, 0)
        
        col1, col2, col3 = st.columns([2, 3, 5])
        with col1: st.subheader(name)
        with col2:
            # 입력창에 천 단위 콤마가 찍힌 상태로 표시
            input_str = st.text_input(f"{name} 목표 설정(원)", value=f"{int(saved_goal):,}", key=f"goal_{code}")
            # 숫자만 추출하여 저장 준비
            try:
                clean_num = int(re.sub(r'[^0-9]', '', input_str))
            except: clean_num = 0
            
            if st.button("구글 시트에 영구 저장", key=f"btn_{code}"):
                cell = goal_ws.find(code)
                if cell: goal_ws.update_cell(cell.row, 2, clean_num)
                else: goal_ws.append_row([code, clean_num])
                st.success(f"'{name}' 목표가 저장되었습니다!")
                st.rerun()
        with col3:
            actual = df_raw[df_raw['쇼핑몰 상품코드'] == code]['매출'].sum() if not df_raw.empty else 0
            rate = (actual / clean_num * 100) if clean_num > 0 else 0
            st.write(f"현재 실적: {actual:,.0f}원 / 달성률: {rate:.1f}%")
            st.progress(min(rate/100, 1.0))

with tab3:
    st.header("📝 업무 체크리스트 (직접 편집 및 저장)")
    # [핵심] 엑셀처럼 실시간으로 수정 가능한 데이터 에디터
    edited_df = st.data_editor(df_task, num_rows="dynamic", use_container_width=True, key="task_edit")
    
    if st.button("💾 변경사항을 구글 시트에 최종 반영"):
        try:
            task_ws.clear()
            header = edited_df.columns.values.tolist()
            data = edited_df.fillna("").values.tolist()
            task_ws.update([header] + data)
            st.success("Task_Log 시트 업데이트 완료!")
        except Exception as e:
            st.error(f"저장 중 오류 발생: {e}")
