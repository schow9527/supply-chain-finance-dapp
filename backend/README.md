# 后端基础模块

当前阶段提供可测试、可迁移和可部署的 Flask 后端。已实现应用工厂、19 个页面路由、统一错误响应、健康检查、8 张数据表、钱包签名 Session 认证、企业申请/审核，以及发票 PDF 安全上传和授权下载。

## 目录结构

```text
backend/
├── app.py                 # create_app 与 WSGI 应用
├── config.py              # development/testing/production 配置
├── errors.py              # 统一 JSON 错误处理
├── extensions.py          # SQLAlchemy、Migrate、CORS
├── models.py              # 8 张数据表及约束
├── migrations/            # 唯一初始迁移
├── routes/
│   ├── health.py          # /api/health/live 与 /api/health/ready
│   ├── auth.py            # nonce、签名验证、Session、/api/me
│   ├── enterprises.py     # 企业申请、列表和审核
│   ├── invoices.py        # PDF 上传与授权下载
│   └── pages.py           # 19 个服务端页面路由
├── services/
│   ├── blockchain.py      # RoleManager 读取与 RoleGranted 回执验证
│   └── validation.py      # 地址和文本校验
└── tests/                 # pytest 自动化测试
```

Python 依赖的唯一事实来源是仓库根目录 `requirements.txt`，不存在独立的 `backend/requirements.txt`。

## 安装与启动

在仓库根目录执行：

```bash
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Gunicorn/Render 使用：

```bash
gunicorn app:app
```

SQLite 仅用于本地开发和自动化测试。Production 配置必须提供 PostgreSQL `DATABASE_URL`、非默认 `SECRET_KEY`、Sepolia RPC，并使用 Chain ID `11155111` 和非零合约地址。

## 测试

```bash
python -m compileall backend app.py
python -m pytest backend/tests -q
python -m pytest backend/tests --cov=backend --cov-report=term-missing
python -m pip check
```

`TestingConfig` 无条件使用独立内存 SQLite。需要文件数据库的迁移测试必须通过 `create_app({...})` 显式传入临时测试 URI。测试 fixture 在执行 `drop_all()` 前还会校验数据库 URI；不得将生产数据库 URI 作为测试 override。

## 当前 API

- `POST /api/auth/nonce`、`POST /api/auth/verify`、`POST /api/auth/logout`
- `GET /api/me`
- `POST /api/enterprises`
- `GET /api/enterprises`、`PATCH /api/enterprises/<id>`（链上 ADMIN）
- `POST /api/invoices/file`
- `GET /api/invoices/<id>/file`
- `GET /api/health/live`、`GET /api/health/ready`

链上写交易始终由浏览器 MetaMask 发起。后端只读取 RoleManager 状态，并在批准企业申请前验证交易目标、确认数和 `RoleGranted` 事件；后端不保存私钥或助记词。

## 数据库迁移

设置开发数据库环境后，在仓库根目录执行：

```bash
python -m flask --app app:app db upgrade
python -m flask --app app:app db check
python -m flask --app app:app db downgrade base
python -m flask --app app:app db upgrade
python -m flask --app app:app db check
```

迁移测试应使用临时 SQLite 文件，避免在项目目录生成或修改开发数据库。Production 迁移应由部署环境提供 PostgreSQL 连接信息。

## 下一阶段

- Web3 事件同步 Worker
- 凭证、融资、审计和仪表盘查询 API
