import datetime
import re
import pytz
import requests
import streamlit as st

# 페이지 기본 설정
st.set_page_config(page_title="학교 급식 찾아보기", page_icon="🍱", layout="centered")

# API URL 설정
SCHOOL_INFO_URL = "https://open.neis.go.kr/hub/schoolInfo"
MEAL_INFO_URL = "https://open.neis.go.kr/hub/mealServiceDietInfo"


def search_school_api(keyword: str):
    """나이스 API를 호출하여 학교 목록을 검색합니다."""
    params = {"Type": "json", "SCHUL_NM": keyword}
    try:
        response = requests.get(SCHOOL_INFO_URL, params=params, timeout=5)
        data = response.json()

        if "schoolInfo" in data:
            # 정상 수신시 row 목록 반환
            return data["schoolInfo"][1]["row"]
        return []
    except Exception:
        return []


def search_school_with_fallback(keyword: str):
    """
    학교 이름으로 검색하되, 검색 결과가 없는 경우
    줄임말(여고->여자고등학교, 고->고등학교 등)을 변환하여 재검색합니다.
    """
    keyword = keyword.strip()
    if not keyword:
        return []

    # 1차 검색
    results = search_school_api(keyword)
    if results:
        return results

    # 2차 검색: 줄임말 변환 적용
    substituted = False
    if "여고" in keyword:
        keyword = keyword.replace("여고", "여자고등학교")
        substituted = True
    elif "고" in keyword and not keyword.endswith("고등학교"):
        # 단어 끝이 '고'로 끝나거나 단어 중 '고'가 포함되어 '고등학교'가 안 적힌 경우
        keyword = re.sub(r"고$", "고등학교", keyword)
        keyword = keyword.replace("고 ", "고등학교 ")
        substituted = True

    if substituted:
        results = search_school_api(keyword)
        if results:
            return results

    return []


def get_meal_info(atpt_code: str, schul_code: str, date_str: str):
    """해당 학교와 날짜(YYYYMMDD)의 중식(MMEAL_SC_CODE=2) 정보 및 응답 코드를 가져옵니다."""
    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": atpt_code,
        "SD_SCHUL_CODE": schul_code,
        "MMEAL_SC_CODE": "2",  # 중식
        "MLSV_FROM_YMD": date_str,
        "MLSV_TO_YMD": date_str,
    }

    try:
        response = requests.get(MEAL_INFO_URL, params=params, timeout=5)
        data = response.json()

        if "mealServiceDietInfo" in data:
            row = data["mealServiceDietInfo"][1]["row"][0]
            return {"code": "SUCCESS", "data": row}

        # RESULT 에러/안내 처리
        if "RESULT" in data:
            return {"code": data["RESULT"].get("CODE", "UNKNOWN"), "data": None}

        return {"code": "EMPTY", "data": None}
    except Exception:
        return {"code": "ERROR", "data": None}


# UI 구성
st.title("🍱 학교 급식 찾아보기")
st.markdown("학교 이름을 검색하고 날짜를 선택하여 중식 메뉴를 확인하세요.")

# 1. 학교 검색
school_keyword = st.text_input("학교 이름을 입력하세요", placeholder="예: 수도여고, 서울고, 중앙중")

selected_school = None

if school_keyword:
    schools = search_school_with_fallback(school_keyword)

    if not schools:
        st.warning(f"'{school_keyword}'(으)로 검색된 학교가 없습니다. 학교명을 정확히 입력해 주세요.")
    else:
        # 셀렉트박스 옵션 생성 (학교명 (지역))
        school_options = {
            f"{s['SCHUL_NM']} ({s.get('LCTN_SC_NM', '지역미상')})": s for s in schools
        }

        selected_label = st.selectbox(
            "검색된 학교 목록에서 선택하세요:", list(school_options.keys())
        )
        selected_school = school_options[selected_label]

st.divider()

# 2. 날짜 선택 (기본값: KST 기준 오늘)
kst = pytz.timezone("Asia/Seoul")
today_kst = datetime.datetime.now(kst).date()

selected_date = st.date_input("날짜를 선택하세요", value=today_kst)

# 3. 급식 정보 조회 및 표시
if selected_school and selected_date:
    ymd_str = selected_date.strftime("%Y%m%d")

    meal_result = get_meal_info(
        selected_school["ATPT_OFCDC_SC_CODE"],
        selected_school["SD_SCHUL_CODE"],
        ymd_str,
    )

    st.subheader(
        f"📅 {selected_school['SCHUL_NM']} ({selected_date.strftime('%Y-%m-%d')}) 중식"
    )

    if meal_result["code"] == "SUCCESS" and meal_result["data"]:
        meal_data = meal_result["data"]

        # <br/> 태그를 줄바꿈으로 변환하여 식단 구성
        raw_ddish = meal_data.get("DDISH_NM", "")
        clean_ddish = raw_ddish.replace("<br/>", "\n").replace("<br>", "\n")
        calories = meal_data.get("CAL_INFO", "정보 없음")

        # 결과 출력
        st.success("식단 정보를 성공적으로 불러왔습니다.")

        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("### 🥗 식단 및 알레르기 정보")
            st.text(clean_ddish)
        with col2:
            st.markdown("### 🔥 칼로리")
            st.info(f"**{calories}**")

        st.caption("※ 메뉴 이름 뒤의 괄호 안 숫자는 알레르기 유발 물질 번호입니다.")

    elif meal_result["code"] == "INFO-200":
        st.info("💡 해당 날짜에는 등록된 급식 식단 정보가 없습니다 (주말, 공휴일 또는 방학 등).")
    else:
        st.error("급식 정보를 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")
elif not selected_school and school_keyword:
    st.info("상단에서 학교를 선택해 주세요.")
else:
    st.info("학교 이름을 입력하면 급식 정보를 확인할 수 있습니다.")
