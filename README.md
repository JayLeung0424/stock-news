# 📈 Stock News Scheduler

自動抓取**富途 (Futu)** 熱門 Top 200 股票的最新新聞，每小時定時執行。

## 功能

- 🔥 **熱門股票抓取**：透過 Futu OpenD API 取得 HK / US / A股 熱門 Top 200 股票（按換手率排序）
- 📰 **新聞搜尋**：使用 Google News RSS 免費搜尋每支股票的最新新聞
- ⏰ **定時排程**：APScheduler 每小時自動執行一次（可自訂間隔）
- 💾 **持久化儲存**：SQLite 資料庫存儲所有新聞，自動去重
- 📊 **執行日誌**：記錄每次抓取的執行狀態與統計

## 專案結構

```
stock-news/
├── main.py              # 主入口 (CLI)
├── scheduler.py         # APScheduler 排程邏輯
├── stock_fetcher.py     # Futu 熱門股票抓取
├── news_searcher.py     # Google News RSS 新聞搜尋
├── storage.py           # SQLite 儲存層
├── config.py            # 設定載入 (.env)
├── requirements.txt     # Python dependencies
├── .env.example         # 環境變數範本
└── .gitignore
```

## 前置需求

1. **Python 3.9+**
2. **FutuOpenD** — 富途 OpenD 閘道器必須在本機或可連線的伺服器上運行
   - 下載：https://www.futunn.com/download/openAPI
   - 啟動 FutuOpenD 後預設監聽 `127.0.0.1:11111`

## 安裝

```bash
# 1. Clone 專案
git clone https://github.com/JayLeung0424/stock-news.git
cd stock-news

# 2. 建立虛擬環境 (建議)
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. 安裝依賴
pip install -r requirements.txt

# 4. 設定環境變數
cp .env.example .env
# 編輯 .env 設定 Futu 連線資訊等
```

## 使用方式

### 啟動排程器（每小時自動執行）

```bash
python main.py
```

### 單次執行（不啟動排程）

```bash
python main.py --once
```

### 自訂參數

```bash
# 每 30 分鐘執行一次，抓取 100 支熱門股
python main.py --interval 30 --count 100

# 指定資料庫路徑
python main.py --db /path/to/my_news.db
```

## 設定說明

所有設定可在 `.env` 檔案中配置：

| 變數 | 預設值 | 說明 |
|---|---|---|
| `FUTU_HOST` | `127.0.0.1` | FutuOpenD 主機位址 |
| `FUTU_PORT` | `11111` | FutuOpenD 連接埠 |
| `SCHEDULER_INTERVAL_MINUTES` | `60` | 排程間隔（分鐘）|
| `HOT_STOCK_COUNT` | `200` | 熱門股票數量 |
| `MAX_NEWS_PER_STOCK` | `5` | 每支股票最大新聞數 |
| `NEWS_LANG` | `zh-HK` | 新聞搜尋語言 |
| `DB_PATH` | `stock_news.db` | SQLite 資料庫路徑 |
| `LOG_LEVEL` | `INFO` | 日誌等級 |

## 資料庫結構

### `news_articles` 表

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | INTEGER | 自增主鍵 |
| `stock_code` | TEXT | 股票代碼 (e.g. HK.00700) |
| `stock_name` | TEXT | 股票名稱 |
| `title` | TEXT | 新聞標題 |
| `link` | TEXT | 新聞連結 |
| `source` | TEXT | 來源媒體 |
| `published` | TEXT | 發布時間 |
| `summary` | TEXT | 摘要 |
| `fetched_at` | TEXT | 抓取時間 |

### `fetch_log` 表

記錄每次排程執行的統計資料。

## 執行流程

```
每小時觸發
    │
    ├── 1. 連接 FutuOpenD
    │      └── 抓取 HK / US / SH / SZ 各市場熱門股票
    │      └── 合併去重，取 Top 200（按換手率排序）
    │
    ├── 2. 逐一搜尋新聞
    │      └── Google News RSS（每支最多 5 條）
    │      └── 請求間隔 1 秒避免限流
    │
    └── 3. 儲存至 SQLite
           └── INSERT OR IGNORE 自動去重
           └── 記錄執行日誌
```

## License

MIT
