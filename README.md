# lccnet-python-sample-project

## Session1. Python 核心語法與後端架構基本功


## Session2. 網路爬蟲工程 —— 打造 Agent 的即時感測器

### Functional Requirements

- Perform web scraping across a series of webpages by iterating through structured URL.
    - Cloud service price from Azure, GCP and AWS
- Perform ETL workflow to clean and preprocess data.
- Define SQL Schema to store preprocessed data.

### Non-functional Requirements

- Use asynchronous mechanism such as open many driver to accelerate the process.
- Due to anti-scraping mechanisms, minimize interactions that trigger a full page re-render.
- Minimize the frequency of connection between service and database

### High-Level Design

```mermaid
flowchart TD
    %% 階段一：排程與爬蟲層
    subgraph S1 ["階段一：資料擷取層 (Data Extraction)"]
        direction TB
        Trigger["排程任務觸發器<br/>(Cron / Airflow / Prefect)"]
        
        subgraph Spiders ["跨平台爬蟲叢集"]
            AWS_Spider["AWS 價格爬蟲<br/>(EC2, S3, RDS 等)"]
            GCP_Spider["GCP 價格爬蟲<br/>(GCE, GCS, Cloud SQL 等)"]
            AZ_Spider["Azure 價格爬蟲<br/>(VM, Blob, SQL DB 等)"]
        end
        
        Proxy["連線管理機制<br/>(限速、代理 IP 輪替、重試機制)"]
        
        Trigger --> Spiders
        Spiders -.-> Proxy
    end

    %% 階段二：原始資料暫存層
    subgraph S2 ["階段二：原始資料暫存層 (Raw Storage / Landing Zone)"]
        direction TB
        MetaCheck{"檢查內容雜湊值<br/>(Hash Check)"}
        
        subgraph MongoDB ["MongoDB 原始資料庫"]
            RawDocs[("raw_html_snapshots<br/>-------------------<br/>• 來源雲端平台<br/>• 目標服務分類<br/>• 抓取時間戳記<br/>• 原始 HTML 內容<br/>• 頁面狀態與雜湊")]
        end
        
        Spiders -->|取得 HTML| MetaCheck
        MetaCheck -->|內容已異動 / 新版本| RawDocs
        MetaCheck -->|內容未變更| Skip["略過更新<br/>(降低寫入與處理成本)"]
    end

    %% 階段三：ETL 資料轉換管線
    subgraph S3 ["階段三：ETL 資料清洗與轉換 (Data Transformation)"]
        direction TB
        ETL_Trigger["觸發 ETL 工作流程<br/>(Change Streams / Message Queue)"]
        
        subgraph Processing ["資料處理程序"]
            Parser["HTML 剖析與特徵擷取<br/>(BeautifulSoup / lxml)"]
            Align["跨平台主題服務對齊<br/>(如: Compute / Storage / DB)"]
            Normalize["價格標準化處理<br/>(規格對齊、計費週期統一、幣別換算)"]
            Validate{"資料品質驗證<br/>(欄位完整性 / 異常波動檢測)"}
        end
        
        DeadLetter[("異常資料隔離區<br/>(Dead Letter Queue)")]
        
        RawDocs -->|發出變更通知| ETL_Trigger
        ETL_Trigger --> Parser
        Parser --> Align
        Align --> Normalize
        Normalize --> Validate
        Validate -->|驗證失敗| DeadLetter
    end

    %% 階段四：結構化儲存層
    subgraph S4 ["階段四：結構化資料儲存層 (Structured Storage Layer)"]
        direction TB
        BatchLoad["批次整批寫入<br/>(Batch Upsert)"]
        
        subgraph RDBMS ["結構化關聯式資料庫 (PostgreSQL / MySQL)"]
            Dim_Provider[("dim_cloud_providers<br/>(雲端平台維度)")]
            Dim_Service[("dim_services<br/>(跨平台服務對照維度)")]
            Dim_Spec[("dim_specifications<br/>(硬體/服務規格維度)")]
            Fact_Pricing[("fact_service_pricings<br/>(各平台定價事實表)")]
        end
        
        Validate -->|驗證通過| BatchLoad
        BatchLoad --> Dim_Provider
        BatchLoad --> Dim_Service
        BatchLoad --> Dim_Spec
        BatchLoad --> Fact_Pricing
    end

    %% 樣式設定
    classDef default fill:#F8F9FA,stroke:#343A40,stroke-width:1px;
    classDef storage fill:#E8F0FE,stroke:#1A73E8,stroke-width:2px;
    classDef alert fill:#FCE8E6,stroke:#D93025,stroke-width:1px;
    
    class MongoDB,RDBMS storage;
    class DeadLetter alert;
```

### Steps for each cloud

#### Azure

1. Enter the following link: https://azure.microsoft.com/en-us/products 
2. Locate the block including groups of title, separator and services
3. Use the visible text 'Price' to locate the elements and get links from services
4. Enter each price table of cloud service
5. Select one region and get the price table.

#### GCP

1. Enter the following link: https://cloud.google.com/pricing/list
2. Locate the main block including groups of title and the list of services
3. Get the title and extract the link from the services
4. Enter the price page of service through link
5. If the table about categories of the service is displayed, get each link of categories and enter each of the link.
6. Select on region and get all of price tables

#### AWS

### Project Structure

```
module2/
├── shared/
│   ├── utility.py          # BrowserPool、@open_playwright_page 裝飾器、close_playwright()
│   ├── mongo.py            # MongoDB 連線與 raw_html_snapshots 寫入（待實作）
│   └── db.py               # PostgreSQL 連線與 Batch Upsert（待實作）
├── automation/
│   ├── compute-azure.py    # Azure VM 定價爬蟲
│   ├── compute-gcp.py      # GCP Compute 定價爬蟲
│   └── compute-aws.py      # AWS EC2 定價爬蟲（待實作）
└── db/
    └── 01_create_table.sql # 結構化資料庫 Schema 定義
```

### Environment Setup

**Dependencies**

| Package | Version |
|---|---|
| `playwright` | 1.62.0 |
| `beautifulsoup4` | 4.14.2 |
| `lxml` | 6.0.2 |
| `nest_asyncio` | 1.6.0 |

```bash
pip install playwright==1.62.0 beautifulsoup4==4.14.2 lxml==6.0.2 nest_asyncio==1.6.0

# 安裝 Chromium（Playwright 需要）
playwright install chromium
```

**Run Scrapers**

```bash
# 從專案根目錄執行
python -m module2.automation.compute-azure
python -m module2.automation.compute-gcp
```

