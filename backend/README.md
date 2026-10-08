# 后端模块 (Backend API & Event Sync)

> **责任人**：成员 2  
> **技术栈**：Python 3.9+, Flask, SQLAlchemy, Web3.py, Gunicorn  
> **部署平台**：Render  

---

## 目录结构

```
backend/
├── routes/                # Flask Blueprint 路由模块
│   ├── api_accounts.py    # 企业入驻与角色状态查询
│   ├── api_invoices.py    # 发票上传 (PDF) 与列表查询
│   ├── api_receivables.py # 应收凭证与流转记录
│   ├── api_financing.py   # 融资申请与资金方报价
│   ├── api_dashboard.py   # 仪表盘聚合数据统计
│   └── api_events.py      # 链上事件审计查询
├── services/
│   ├── event_sync.py      # Web3.py 区块链事件轮询同步器
│   └── storage.py         # PDF 本地/云存储与 SHA-256 计算
├── models.py              # SQLite / PostgreSQL 数据模型 (7张表)
├── config.py              # 环境与配置管理
├── requirements.txt       # Python 依赖清单
└── README.md
```

## 核心职责
1. **数据中继与存储**：保存链下发票文件原件，计算 SHA-256 哈希供合约登记。
2. **链上事件同步**：利用 Web3.py 轮询或 WebSocket 监听各合约事件，持久化至 `chain_events` 表并更新状态。
3. **高速查询接口**：向前端提供各角色仪表盘与列表的 RESTful API，避免前端频繁通过 RPC 直查链上数据。
4. **安全底线**：后端绝对不托管任何私钥，所有链上写操作由前端 MetaMask 签名。

## 快速上手

### 1. 创建虚拟环境并安装依赖
```bash
cd backend
python -m venv venv

# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. 配置环境变量
参考根目录 `.env.example` 在根目录或 `backend/` 下配置 `.env` 文件。

### 3. 本地启动
```bash
python app.py
```
默认运行在 `http://127.0.0.1:5000`。
