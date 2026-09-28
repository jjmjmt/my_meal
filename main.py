    # main.py — 학교를 검색해 고르면 그 학교의 급식을 보여 주는 첫 화면
import datetime
import re

import requests
import streamlit as st

st.set_page_config(page_title="학교 급식 찾아보기", layout="wide")
st.title("🍚 학교 급식 찾아보기")
st.write("학교 이름을 검색해 고르면 그 학교의 그날 중식을 보여 줍니다. 왼쪽 메뉴에는 우리 학교만 보는 페이지가 있습니다.")

name = st.text_input("학교 이름", value="송탄고등학교")
picked = st.date_input("날짜를 고르세요", value=(datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date())  # 한국 시간 기준 오늘

# 1) 학교 이름으로 교육청 코드와 학교 코드를 찾는다 (인증키 없이, 한 번에 5건까지)
def search_schools(query):
    info = requests.get(
        "https://open.neis.go.kr/hub/schoolInfo",
        params={"Type": "json", "SCHUL_NM": query},
        timeout=10,
    ).json()
    if "schoolInfo" in info:
        return info["schoolInfo"][1]["row"]
    result = info.get("RESULT", {})
    if result.get("CODE") == "INFO-200":
        return []
    st.error("학교 조회에 실패했습니다. " + result.get("MESSAGE", "응답을 확인해 주세요."))
    st.stop()


schools = search_schools(name)
if not schools:
    # '수도여고'처럼 줄여 적은 이름은 정식 이름의 일부가 아니라 못 찾는다 — 풀어서 다시 찾는다
    for short, full in [("여고", "여자고등학교"), ("고", "고등학교"), ("중", "중학교"), ("초", "초등학교")]:
        if name.endswith(short):
            schools = search_schools(name[: -len(short)] + full)
            break
if not schools:
    st.warning("그 이름의 학교를 찾지 못했습니다. 정식 이름으로 적어 보세요. (예: 수도여자고등학교)")
    st.stop()

labels = [f"{s['SCHUL_NM']} ({s['LCTN_SC_NM']})" for s in schools]
chosen = schools[labels.index(st.selectbox("학교 고르기", labels))]

# 2) 고른 학교의 그날 중식을 불러온다
ymd = picked.strftime("%Y%m%d")
meal = requests.get(
    "https://open.neis.go.kr/hub/mealServiceDietInfo",
    params={
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": chosen["ATPT_OFCDC_SC_CODE"],
        "SD_SCHUL_CODE": chosen["SD_SCHUL_CODE"],
        "MMEAL_SC_CODE": "2",
        "MLSV_FROM_YMD": ymd,
        "MLSV_TO_YMD": ymd,
    },
    timeout=10,
).json()

st.subheader(chosen["SCHUL_NM"] + " · " + picked.strftime("%Y년 %m월 %d일") + " 중식")
if "mealServiceDietInfo" not in meal:
    result = meal.get("RESULT", {})
    if result.get("CODE") == "INFO-200":
        st.info("조회한 날짜의 급식 정보가 없습니다.")
    else:
        st.error("급식 조회에 실패했습니다. " + result.get("MESSAGE", "요청 조건을 확인해 주세요."))
else:
    row = meal["mealServiceDietInfo"][1]["row"][0]
    for dish in row["DDISH_NM"].split("<br/>"):
        # 조회 화면에서는 메뉴와 알레르기 정보를 함께 보여 준다
        st.write(dish.strip())
    st.metric("칼로리", row["CAL_INFO"])
