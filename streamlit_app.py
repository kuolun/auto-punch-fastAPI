# 導入所需的函式庫
import streamlit as st  # Web 應用框架
import requests  # HTTP 請求
from bs4 import BeautifulSoup  # HTML 解析
from datetime import datetime, timezone, timedelta  # 日期時間處理（加入時區支援）
import time  # 時間控制
import json  # JSON 處理

# 頁面設定
st.set_page_config(
    page_title="自動打卡系統",  # 瀏覽器標題
    page_icon="🤖",  # 瀏覽器圖示
    layout="wide",  # 寬版佈局
    initial_sidebar_state="collapsed"  # 隱藏側邊欄
)

# 自訂 CSS 樣式
st.markdown("""
<style>
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .error-box {
        padding: 1rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .info-box {
        padding: 1rem;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        border-radius: 5px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# API 基礎網址
BASE_URL = "https://herbworklog.netlify.app/.netlify/functions"

# 設定台灣時區
TAIWAN_TZ = timezone(timedelta(hours=8))  # UTC+8

def get_taiwan_time():
    """取得台灣當前時間"""
    return datetime.now(TAIWAN_TZ)

def get_taiwan_date_string():
    """取得台灣當前日期字串 (YYYY-MM-DD)"""
    return get_taiwan_time().strftime("%Y-%m-%d")

def get_taiwan_datetime_string():
    """取得台灣當前日期時間字串 (YYYY-MM-DD HH:MM:SS)"""
    return get_taiwan_time().strftime("%Y-%m-%d %H:%M:%S")

# 工具函數
@st.cache_data(ttl=300)  # 快取 5 分鐘，避免重複請求
def fetch_case_list(user_id, password):
    """根據使用者帳密自動取得案件清單"""
    try:
        data = {
            "user_id": user_id,
            "f_password": password,
            "f_password2": "",
            "from_case_edit": ""
        }
        resp = requests.post(f"{BASE_URL}/case_list", data=data, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 找到案件清單表格
        table = soup.find("table", {"id": "caselist1"})
        if not table:
            return None

        # 找到表格中的所有行
        rows = table.find("tbody").find_all("tr") if table.find("tbody") else table.find_all("tr")

        # 提取每行第2個td的內容（案件編號）
        case_numbers = []
        for row in rows:
            tds = row.find_all("td")
            if len(tds) >= 2:  # 確保至少有2個td
                case_number = tds[1].get_text(strip=True)  # 第2個td（索引1）
                if case_number:
                    case_numbers.append(case_number)

        # 用逗號串接所有案件編號
        return ",".join(case_numbers) if case_numbers else None

    except Exception as e:
        return None

@st.cache_data(ttl=60)  # 快取 60 秒，避免重複請求
def fetch_case_edit(case_key, case_list, user_id):
    """取得案件編輯頁面"""
    try:
        data = {
            "form_key": case_key,
            "table_case_id_list": case_list,
            "user_id": user_id
        }
        resp = requests.post(f"{BASE_URL}/case_edit", data=data, timeout=30)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        return None

def extract_fields(doc, today, user_id, punch_message):
    """從案件編輯頁面提取欄位資料"""
    field_ids = [
        "f_key", "f_case_name", "f_person_id", "f_person2_id",
        "f_event_date", "f_alert_date", "f_log", "f_note",
        "f_to_do", "f_dir", "f_risk", "f_doc"
    ]

    payload = {}
    for fid in field_ids:
        el = doc.find(id=fid)
        if not el:
            payload[fid] = ""
        elif el.name == "input":
            payload[fid] = el.get("value", "").strip()
        elif el.name == "textarea":
            payload[fid] = el.text.strip()
        else:
            payload[fid] = ""

    # 轉換 f_key 為整數
    payload["f_key"] = int(payload["f_key"])

    # 更新工作日誌
    original_log = payload.get("f_log", "")
    payload["f_log"] = f"{punch_message}\n\n{original_log}".strip()

    # 設定更新資訊
    payload["f_update_date"] = today
    payload["f_last_editor"] = user_id

    return payload

def submit_punch(payload):
    """提交打卡資料"""
    try:
        # 將 payload 轉換為 JSON 字串，放在 fields 欄位中
        json_payload = json.dumps(payload)
        form_data = {"fields": json_payload}

        resp = requests.post(
            f"{BASE_URL}/sql_for_case",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=form_data,
            timeout=30
        )
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        return None

# 初始化 session state
if 'punch_log' not in st.session_state:
    st.session_state.punch_log = []

# 主要介面
col1, col2 = st.columns([2, 1])

with col1:
    # 🔥 重點：使用者資訊輸入區 🔥
    st.subheader("👤 使用者資訊")
    st.markdown("**請填寫您的個人登入資訊：**")

    # 使用 columns 讓輸入框橫向排列
    input_col1, input_col2 = st.columns(2)

    with input_col1:
        # 🔥 員工編號輸入框
        user_id = st.text_input(
            "🆔 員工編號",
            placeholder="例如：1889",
            help="請輸入您的員工編號",
            key="user_id_input"
        )

    with input_col2:
        # 🔥 密碼輸入框（隱藏顯示）
        password = st.text_input(
            "🔐 登入密碼",
            type="password",
            placeholder="請輸入密碼",
            help="您的系統登入密碼",
            key="password_input"
        )

    st.markdown("---")
    st.markdown("🎯 **抓取案件清單**：請先抓取您的案件清單")
    
    if st.button(
        "🔄 抓取案件清單",
        help="從系統取得您的案件清單",
        type="secondary"
    ):
        # 檢查是否已填入帳密
        if not user_id:
            st.error("❌ 請先填寫員工編號")
        elif not password:
            st.error("❌ 請先填寫登入密碼")
        else:
            with st.spinner("🔍 正在從系統取得您的案件清單..."):
                auto_case_list = fetch_case_list(user_id, password)

                if auto_case_list:
                    # 自動填入案件清單
                    st.session_state.auto_case_list = auto_case_list
                    # 解析案件數量
                    auto_cases = [k.strip() for k in auto_case_list.split(",") if k.strip()]

                    st.success(f"✅ 成功抓取！從表格中找到 {len(auto_cases)} 個案件")
                else:
                    st.error("❌ 無法取得案件清單")

                    # 除錯資訊
                    with st.expander("🔧 除錯資訊"):
                        st.markdown("**可能的原因：**")
                        st.write("1. 員工編號或密碼錯誤")
                        st.write("2. 網路連線問題")
                        st.write("3. 系統中沒有 id='caselist1' 的表格")
                        st.write("4. 表格結構與預期不符")

                        st.markdown("**建議解決方案：**")
                        st.write("- 檢查員工編號和密碼是否正確")
                        st.write("- 先嘗試手動登入系統確認帳密")
                        st.write("- 如果問題持續，請聯繫系統管理員")

    st.divider()

    # 顯示已抓取的案件清單（只讀）
    if st.session_state.get('auto_case_list'):
        st.markdown("### 📋 目前的案件清單")
        case_list = st.session_state.auto_case_list
        case_keys = [k.strip() for k in case_list.split(",") if k.strip()]

        # 使用只讀的文字區域顯示
        st.text_area(
            "已抓取的案件清單",
            value=case_list,
            height=60,
            disabled=True,  # 只讀，不能編輯
            help="這是從系統自動抓取的案件清單，不可手動修改"
        )

        st.success(f"🎯 確認：已載入 {len(case_keys)} 個案件")

        # 清除按鈕
        col_info, col_clear = st.columns([3, 1])
        with col_clear:
            if st.button("🗑️ 清除", help="清除已抓取的案件清單，重新抓取"):
                st.session_state.auto_case_list = ""
                st.rerun()

    else:
        case_list = ""  # 設定為空，讓後續驗證失敗


    # 選項設定
    st.subheader("⚙️ 執行設定")

    auto_save_log = st.checkbox(
        "📝 自動儲存日誌",
        value=True,
        help="執行結果會儲存在瀏覽器中"
    )

with col2:
    # 側邊操作區
    st.subheader("🎮 操作區")

    # 驗證輸入
    case_list = st.session_state.get('auto_case_list', '')
    input_valid = bool(user_id and password and case_list)

    if not user_id or not password:
        st.warning("⚠️ 請填寫員工編號和密碼")
    elif not case_list:
        st.warning("⚠️ 請使用「🔄 抓取案件清單」取得案件清單")
    else:
        st.success("✅ 所有資訊已準備就緒，可以開始操作")

    # 🔥 自訂打卡訊息（移到開始打卡按鈕上方）
    punch_message = st.text_input(
        "💬 打卡訊息",
        value="",
        help="這個訊息會加入到您的工作日誌中",
        key="punch_message_input_right"
    )

    # 開始打卡按鈕
    if st.button(
        "🚀 開始打卡",
        disabled=not input_valid,
        use_container_width=True,
        type="primary"
    ):
        # 確認執行
        st.info(f"🎯 執行模式：正常模式（處理所有案件）")

        # 解析案件清單
        case_keys = [k.strip() for k in case_list.split(",") if k.strip()]
        today = get_taiwan_date_string()  # 使用台灣時間

        st.info(f"📋 將處理 {len(case_keys)} 筆案件")

        # 建立結果顯示區域
        progress_bar = st.progress(0)
        status_placeholder = st.empty()
        results_placeholder = st.empty()

        # 執行結果列表
        results = []

        # 開始處理每個案件
        for i, key in enumerate(case_keys):
            # 更新進度
            progress = (i + 1) / len(case_keys)
            progress_bar.progress(progress)
            status_placeholder.info(f"⚙️ 處理案件 {key} ({i+1}/{len(case_keys)})...")

            try:
                # 取得案件資料
                with st.spinner(f"📡 正在取得案件 {key} 的資料..."):
                    doc = fetch_case_edit(key, case_list, user_id)

                if not doc:
                    results.append({
                        "case": key,
                        "status": "❌ 失敗",
                        "message": "無法取得案件資料",
                        "details": "請檢查案件編號是否正確"
                    })
                    continue

                # 提取欄位資料
                payload = extract_fields(doc, today, user_id, punch_message)
                case_name = payload.get('f_case_name', '未知')
                f_key = payload.get('f_key', '未知')

                # 顯示案件資訊
                status_placeholder.success(f"📋 找到案件：{case_name} (ID: {f_key})")

                # 提交打卡資料
                with st.spinner("💾 正在提交打卡資料..."):
                    result = submit_punch(payload)

                if result:
                    results.append({
                        "case": key,
                        "status": "✅ 成功",
                        "message": f"案件：{case_name}",
                        "details": f"f_key: {f_key}，已更新工作日誌",
                        "f_key": f_key
                    })
                    status_placeholder.success(f"✅ 案件 {key} 打卡成功！")
                else:
                    results.append({
                        "case": key,
                        "status": "❌ 失敗",
                        "message": f"案件：{case_name}",
                        "details": "提交打卡資料失敗"
                    })
                    status_placeholder.error(f"❌ 案件 {key} 打卡失敗！")

                # 即時顯示目前結果
                with results_placeholder.container():
                    st.subheader("📊 執行結果")
                    for r in results:
                        if r["status"].startswith("✅"):
                            st.success(f"**{r['case']}** - {r['status']} - {r['message']}")
                        else:
                            st.error(f"**{r['case']}** - {r['status']} - {r['message']}")

                # 暫停避免請求過快
                time.sleep(1)

            except Exception as e:
                error_msg = str(e)
                results.append({
                    "case": key,
                    "status": "❌ 錯誤",
                    "message": "系統錯誤",
                    "details": error_msg
                })
                status_placeholder.error(f"❌ 處理案件 {key} 時發生錯誤：{error_msg}")

        # 最終結果統計
        progress_bar.progress(1.0)
        success_count = sum(1 for r in results if r["status"].startswith("✅"))

        # 顯示最終結果
        status_placeholder.empty()  # 清除狀態訊息

        if success_count == len(case_keys):
            st.success(f"🎉 **全部成功！** 已完成 {success_count}/{len(case_keys)} 筆打卡")
        elif success_count > 0:
            st.warning(f"⚠️ **部分成功！** 已完成 {success_count}/{len(case_keys)} 筆打卡")
        else:
            st.error(f"❌ **全部失敗！** 無法完成任何打卡")

        # 詳細結果表格
        st.subheader("📋 詳細執行結果")
        for i, result in enumerate(results, 1):
            with st.expander(f"{i}. 案件 {result['case']} - {result['status']}"):
                st.write(f"**案件編號：** {result['case']}")
                st.write(f"**執行狀態：** {result['status']}")
                st.write(f"**案件資訊：** {result['message']}")
                st.write(f"**詳細說明：** {result.get('details', '無')}")

        # 儲存到執行歷史
        if auto_save_log:
            timestamp = get_taiwan_datetime_string()  # 使用台灣時間
            st.session_state.punch_log.append({
                "timestamp": timestamp,
                "results": results,
                "success_count": success_count,
                "total_count": len(case_keys),
                "mode": "正常模式"
            })
            st.info("💾 執行結果已儲存到歷史記錄")

        # 重新執行建議
        if success_count < len(case_keys):
            st.warning("💡 **建議：** 如果有失敗的案件，可以檢查錯誤原因後重新執行")

        st.success("🏁 **執行完成！** 您可以關閉此頁面或繼續使用其他功能")



# 頁腳資訊
st.divider()
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.9em;">
    🤖 自動打卡系統 v3.0 - 簡潔版
</div>
""", unsafe_allow_html=True)

