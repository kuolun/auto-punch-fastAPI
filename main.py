from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
import aiohttp
import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
import logging
from bs4 import BeautifulSoup

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化FastAPI應用
app = FastAPI(
    title="自動打卡系統",
    description="簡化版自動打卡系統",
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 靜態檔案和模板
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# API 基礎網址
BASE_URL = "https://herbworklog.netlify.app/.netlify/functions"

# 設定台灣時區
TAIWAN_TZ = timezone(timedelta(hours=8))

def get_taiwan_time():
    """取得台灣當前時間"""
    return datetime.now(TAIWAN_TZ)

def get_taiwan_date_string():
    """取得台灣當前日期字串 (YYYY-MM-DD)"""
    return get_taiwan_time().strftime("%Y-%m-%d")

# ===== 核心功能函數 =====

async def fetch_case_list_from_api(user_id: str, password: str) -> List[str]:
    """從原始API抓取案件清單"""
    try:
        data = {
            "user_id": user_id,
            "f_password": password,
            "f_password2": "",
            "from_case_edit": ""
        }
        
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{BASE_URL}/case_list", data=data) as response:
                response.raise_for_status()
                html_content = await response.text()
                soup = BeautifulSoup(html_content, "html.parser")
                
                # 找到案件清單表格
                table = soup.find("table", {"id": "caselist1"})
                if not table:
                    return []
                
                # 提取案件編號
                rows = table.find("tbody").find_all("tr") if table.find("tbody") else table.find_all("tr")
                case_numbers = []
                for row in rows:
                    tds = row.find_all("td")
                    if len(tds) >= 2:
                        case_number = tds[1].get_text(strip=True)
                        if case_number:
                            case_numbers.append(case_number)
                
                logger.info(f"Retrieved {len(case_numbers)} cases for user {user_id}")
                return case_numbers
                
    except Exception as e:
        logger.error(f"Error fetching case list for user {user_id}: {str(e)}")
        return []

async def fetch_case_edit(case_key: str, case_list: str, user_id: str):
    """取得案件編輯頁面"""
    try:
        data = {
            "form_key": case_key,
            "table_case_id_list": case_list,
            "user_id": user_id
        }
        
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{BASE_URL}/case_edit", data=data) as response:
                response.raise_for_status()
                html_content = await response.text()
                return BeautifulSoup(html_content, "html.parser")
                
    except Exception as e:
        logger.error(f"Error fetching case edit for case {case_key}: {str(e)}")
        return None

def extract_fields(doc, today: str, user_id: str, punch_message: str):
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
    try:
        payload["f_key"] = int(payload["f_key"])
    except (ValueError, TypeError):
        payload["f_key"] = 0
    
    # 更新工作日誌
    original_log = payload.get("f_log", "")
    if punch_message:
        payload["f_log"] = f"{punch_message}\n\n{original_log}".strip()
    
    # 設定更新資訊
    payload["f_update_date"] = today
    payload["f_last_editor"] = user_id
    
    return payload

def extract_fields_with_custom_log(doc, today: str, user_id: str, custom_log_content: str):
    """從案件編輯頁面提取欄位資料並使用自定義log內容"""
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
    try:
        payload["f_key"] = int(payload["f_key"])
    except (ValueError, TypeError):
        payload["f_key"] = 0
    
    # 直接使用自定義的工作日誌內容
    payload["f_log"] = custom_log_content
    
    # 設定更新資訊
    payload["f_update_date"] = today
    payload["f_last_editor"] = user_id
    
    return payload

def extract_fields_with_custom_data(doc, today: str, user_id: str, custom_log_content: str, custom_todo_content: str = None):
    """從案件編輯頁面提取欄位資料並使用自定義log和待辦事項內容"""
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
    try:
        payload["f_key"] = int(payload["f_key"])
    except (ValueError, TypeError):
        payload["f_key"] = 0
    
    # 使用自定義的工作日誌內容
    payload["f_log"] = custom_log_content
    
    # 使用自定義的待辦事項內容（如果有提供）
    if custom_todo_content is not None:
        payload["f_to_do"] = custom_todo_content
    
    # 設定更新資訊
    payload["f_update_date"] = today
    payload["f_last_editor"] = user_id
    
    return payload

async def submit_punch(payload):
    """提交打卡資料"""
    try:
        json_payload = json.dumps(payload)
        form_data = {"fields": json_payload}
        
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{BASE_URL}/sql_for_case",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data=form_data
            ) as response:
                response.raise_for_status()
                return await response.text()
                
    except Exception as e:
        logger.error(f"Error submitting punch: {str(e)}")
        return None

# ===== 網頁路由 =====

@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """主頁面"""
    return templates.TemplateResponse("index.html", {"request": request})

# ===== API路由 =====

@app.post("/api/fetch-cases")
async def fetch_cases(user_id: str = Form(...), password: str = Form(...)):
    """抓取案件清單"""
    try:
        cases = await fetch_case_list_from_api(user_id, password)
        
        if not cases:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "無法取得案件清單，請檢查帳號密碼是否正確"}
            )
        
        return {
            "success": True,
            "cases": cases,
            "total_count": len(cases),
            "message": f"成功抓取 {len(cases)} 個案件"
        }
        
    except Exception as e:
        logger.error(f"Error in fetch_cases: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"系統錯誤: {str(e)}"}
        )

@app.post("/api/fetch-case-details")
async def fetch_case_details(
    user_id: str = Form(...), 
    case_list: str = Form(...)
):
    """抓取所有案件的詳細資料"""
    try:
        case_keys = [k.strip() for k in case_list.split(",") if k.strip()]
        
        if not case_keys:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "沒有有效的案件清單"}
            )
        
        logger.info(f"Fetching details for {len(case_keys)} cases by user {user_id}")
        
        case_details = []
        
        # 使用信號量限制並發數量
        semaphore = asyncio.Semaphore(3)
        
        async def get_case_detail(case_key: str):
            async with semaphore:
                try:
                    doc = await fetch_case_edit(case_key, case_list, user_id)
                    if not doc:
                        return {
                            "case_key": case_key,
                            "case_name": "無法取得",
                            "current_log": "",
                            "person_id": "",
                            "f_dir": "",
                            "f_to_do": "",
                            "error": "無法取得案件資料"
                        }
                    
                    # 提取案件詳細資訊
                    case_name_el = doc.find(id="f_case_name")
                    case_name = case_name_el.get("value", "").strip() if case_name_el else "未知案件"
                    
                    log_el = doc.find(id="f_log")
                    current_log = log_el.text.strip() if log_el else ""
                    
                    person_el = doc.find(id="f_person_id")
                    person_id = person_el.get("value", "").strip() if person_el else ""
                    
                    f_key_el = doc.find(id="f_key")
                    f_key = f_key_el.get("value", "").strip() if f_key_el else ""
                    
                    # 提取 f_dir (資料夾路徑)
                    f_dir_el = doc.find(id="f_dir")
                    f_dir = ""
                    if f_dir_el:
                        if f_dir_el.name == "input":
                            f_dir = f_dir_el.get("value", "").strip()
                        elif f_dir_el.name == "textarea":
                            f_dir = f_dir_el.text.strip()
                    
                    # 提取 f_to_do (待辦事項)
                    f_to_do_el = doc.find(id="f_to_do")
                    f_to_do = ""
                    if f_to_do_el:
                        if f_to_do_el.name == "input":
                            f_to_do = f_to_do_el.get("value", "").strip()
                        elif f_to_do_el.name == "textarea":
                            f_to_do = f_to_do_el.text.strip()
                    
                    return {
                        "case_key": case_key,
                        "case_name": case_name,
                        "current_log": current_log,
                        "person_id": person_id,
                        "f_key": f_key,
                        "f_dir": f_dir,
                        "f_to_do": f_to_do,
                        "error": None
                    }
                    
                except Exception as e:
                    logger.error(f"Error getting details for case {case_key}: {str(e)}")
                    return {
                        "case_key": case_key,
                        "case_name": "錯誤",
                        "current_log": "",
                        "person_id": "",
                        "f_dir": "",
                        "f_to_do": "",
                        "error": str(e)
                    }
        
        # 並發處理所有案件
        tasks = [get_case_detail(case_key) for case_key in case_keys]
        case_details = await asyncio.gather(*tasks)
        
        success_count = sum(1 for detail in case_details if detail["error"] is None)
        
        logger.info(f"Fetched details: {success_count}/{len(case_keys)} successful")
        
        return {
            "success": True,
            "case_details": case_details,
            "total_count": len(case_keys),
            "success_count": success_count,
            "message": f"成功取得 {success_count}/{len(case_keys)} 個案件詳細資料"
        }
        
    except Exception as e:
        logger.error(f"Error in fetch_case_details: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"系統錯誤: {str(e)}"}
        )

@app.post("/api/batch-punch")
async def batch_punch(
    user_id: str = Form(...),
    case_list: str = Form(...),
    punch_data: str = Form(...)  # JSON 格式的案件打卡資料
):
    """批量打卡 - 支援個別案件自訂訊息"""
    try:
        # 解析打卡資料
        import json
        punch_info = json.loads(punch_data)
        
        if not punch_info or not isinstance(punch_info, list):
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "無效的打卡資料格式"}
            )
        
        logger.info(f"Starting batch punch for {len(punch_info)} cases by user {user_id}")
        
        # 執行批量打卡
        results = []
        today = get_taiwan_date_string()
        
        # 使用信號量限制並發數量
        semaphore = asyncio.Semaphore(3)
        
        async def process_case(case_info: dict):
            async with semaphore:
                case_key = case_info.get("case_key")
                edited_log_content = case_info.get("edited_log_content", "")
                edited_todo_content = case_info.get("edited_todo_content", None)
                
                try:
                    # 取得案件資料
                    doc = await fetch_case_edit(case_key, case_list, user_id)
                    if not doc:
                        return {
                            "success": False,
                            "case_key": case_key,
                            "message": "無法取得案件資料"
                        }
                    
                    # 提取欄位資料並使用編輯後的log和待辦事項內容
                    payload = extract_fields_with_custom_data(doc, today, user_id, edited_log_content, edited_todo_content)
                    case_name = payload.get('f_case_name', '未知')
                    
                    # 提交打卡資料
                    result = await submit_punch(payload)
                    
                    if result:
                        message_parts = [f"案件 {case_name}"]
                        if edited_log_content:
                            message_parts.append("工作日誌")
                        if edited_todo_content is not None:
                            message_parts.append("待辦事項")
                        message_parts.append("更新成功")
                        
                        return {
                            "success": True,
                            "case_key": case_key,
                            "case_name": case_name,
                            "message": " ".join(message_parts),
                            "log_content": edited_log_content[:50] + "..." if len(edited_log_content) > 50 else edited_log_content,
                            "todo_content": edited_todo_content[:30] + "..." if edited_todo_content and len(edited_todo_content) > 30 else edited_todo_content
                        }
                    else:
                        return {
                            "success": False,
                            "case_key": case_key,
                            "case_name": case_name,
                            "message": f"案件 {case_name} 更新失敗"
                        }
                        
                except Exception as e:
                    return {
                        "success": False,
                        "case_key": case_key,
                        "message": f"處理錯誤: {str(e)}"
                    }
        
        # 並發處理所有案件
        tasks = [process_case(case_info) for case_info in punch_info]
        results = await asyncio.gather(*tasks)
        
        # 統計結果
        success_count = sum(1 for r in results if r.get("success", False))
        
        logger.info(f"Batch punch completed: {success_count}/{len(punch_info)} successful")
        
        return {
            "success": True,
            "results": results,
            "total_count": len(punch_info),
            "success_count": success_count,
            "message": f"批量打卡完成：{success_count}/{len(punch_info)} 成功"
        }
        
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "打卡資料JSON格式錯誤"}
        )
    except Exception as e:
        logger.error(f"Batch punch error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"批量打卡失敗: {str(e)}"}
        )

@app.get("/api/health")
async def health_check():
    """健康檢查端點"""
    return {
        "status": "healthy",
        "timestamp": get_taiwan_time().isoformat(),
        "version": "2.1.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 