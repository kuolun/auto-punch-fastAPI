# 自動打卡系統 v2.1 - 簡化版

🤖 企業自動打卡系統，專注核心功能，使用 FastAPI 構建的輕量級版本。

## ✨ 核心功能

- **🔐 簡單登入**: 員工編號 + 密碼驗證
- **📋 案件抓取**: 自動從系統獲取案件清單
- **⚡ 批量打卡**: 高效能異步批量打卡處理
- **💾 智能記憶**: Cookie 儲存帳號密碼，自動登入
- **🎨 簡潔介面**: 三步驟完成打卡流程

## 🏗️ 系統架構

```
auto-punch-fastAPI/
├── main.py                 # FastAPI 主應用 (所有功能)
├── requirements.txt       # 精簡依賴套件
├── templates/            # HTML 模板
│   ├── base.html         # 基礎模板
│   └── index.html        # 主頁面 (唯一頁面)
├── static/              # 靜態檔案目錄
└── README.md            # 說明文檔
```

## 🚀 快速開始

### 1. 環境需求

- Python 3.8+
- 支援現代瀏覽器 (Chrome, Firefox, Edge)

### 2. 安裝與執行

```bash
# 1. 創建虛擬環境
python -m venv venv

# 2. 啟動虛擬環境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 3. 安裝依賴
pip install -r requirements.txt

# 4. 啟動應用
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 5. 開啟瀏覽器
# http://localhost:8000
```

## 📱 使用說明

### 三步驟簡單操作

1. **🔐 輸入登入資訊**
   - 員工編號：例如 `1889`
   - 密碼：您的系統密碼
   - ✅ 勾選「記住帳號密碼」可自動儲存

2. **📋 抓取案件清單**
   - 點擊「抓取案件清單」按鈕
   - 系統自動驗證並獲取您的案件

3. **⚡ 執行批量打卡**
   - 輸入打卡訊息 (可選)
   - 點擊「開始批量打卡」
   - 查看執行結果統計

### 智能功能

- **自動登入**: 下次開啟會自動載入儲存的帳密並抓取案件
- **即時回饋**: 顯示詳細的執行結果和統計資訊
- **錯誤處理**: 友善的錯誤提示和處理機制

## 🔧 API 端點

### 核心 API

```bash
# 抓取案件清單
POST /api/fetch-cases
Content-Type: multipart/form-data
- user_id: 員工編號
- password: 密碼

# 批量打卡
POST /api/batch-punch  
Content-Type: multipart/form-data
- user_id: 員工編號
- case_list: 案件清單 (逗號分隔)
- punch_message: 打卡訊息 (選填)

# 健康檢查
GET /api/health
```

### 使用範例

```bash
# 抓取案件清單
curl -X POST "http://localhost:8000/api/fetch-cases" \
  -F "user_id=1889" \
  -F "password=your_password"

# 批量打卡
curl -X POST "http://localhost:8000/api/batch-punch" \
  -F "user_id=1889" \
  -F "case_list=CASE1,CASE2,CASE3" \
  -F "punch_message=今日打卡"
```

## 🔒 安全性

- **無密碼儲存**: 系統不儲存使用者密碼，僅作驗證
- **本機 Cookie**: 帳號密碼儲存在用戶本機瀏覽器
- **HTTPS 支援**: 生產環境建議使用 HTTPS
- **並發控制**: 限制同時請求數量，防止系統過載

## 🛠️ 自訂設定

### 修改並發數量

在 `main.py` 中找到：
```python
semaphore = asyncio.Semaphore(3)  # 最多同時處理3個案件
```

### 修改 Cookie 有效期

在 `templates/index.html` 中找到：
```javascript
function setCookie(name, value, days = 30) // 預設30天
```

### 修改 API 基礎網址

在 `main.py` 中找到：
```python
BASE_URL = "https://herbworklog.netlify.app/.netlify/functions"
```

## 🚀 部署

### 本機測試
```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### 生產環境
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker 部署
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 🆚 版本對比

| 功能 | v1.x (Streamlit) | v2.0 (複雜版) | v2.1 (簡化版) |
|------|-----------------|-------------|-------------|
| 使用者介面 | 單頁 Streamlit | 多頁面 + 儀表板 | 單頁面專注 |
| 認證機制 | 無持久認證 | JWT Token | Cookie 儲存 |
| 並發處理 | 同步 | 異步 | 異步 |
| 檔案數量 | 1個 | 15個+ | 4個 |
| 部署複雜度 | 簡單 | 複雜 | 簡單 |
| 功能完整度 | 基本 | 完整 | 核心 |

## 💡 常見問題

### Q: Cookie 安全嗎？
A: Cookie 儲存在本機瀏覽器，相對安全。可隨時清除或關閉記住功能。

### Q: 為什麼簡化版本？
A: 專注核心打卡功能，移除複雜的認證和監控，更易維護和使用。

### Q: 如何清除儲存的帳密？
A: 取消勾選「記住帳號密碼」或清除瀏覽器 Cookie。

### Q: 支援多少案件？
A: 理論無限制，實際受系統 API 限制。建議單次不超過50個案件。

## 📝 更新日誌

### v2.1.0 (2024-12)
- **🎯 功能簡化**: 專注三大核心功能
- **💾 智能記憶**: Cookie 自動儲存登入資訊
- **⚡ 效能優化**: 移除不必要的複雜功能
- **🎨 介面改進**: 更簡潔的三步驟操作流程
- **📦 架構精簡**: 從15+檔案簡化到4個核心檔案

### v2.0.0 (2024-12)
- 完整的 FastAPI 重構版本

### v1.x
- Streamlit 版本

## 🤝 支援

如果遇到問題：
1. 檢查瀏覽器控制台錯誤訊息
2. 確認網路連線正常
3. 驗證帳號密碼正確性
4. 查看 API 文檔: `/docs`

---

**簡單、快速、可靠** - 專注於您真正需要的打卡功能。 