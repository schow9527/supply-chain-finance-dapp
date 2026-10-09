# 去中心化供应链金融 DApp (Supply Chain Finance DApp)

> **课程项目**：NTU SC6113 (AY2026/2027) 小组作业  
> **PRD 制定**：@YANG SHUYI  
> **技术栈**：Solidity (ERC-1155 / ERC-20) + Python Flask + Ethers.js + Render 部署  

---

## 📖 项目简介

本项目是一个基于以太坊智能合约的供应链金融去中心化应用（DApp）。通过将核心企业确认过的真实应付账款上链转化为可拆分、可转让、可融资的数字凭证（ReceivableToken ERC-1155），解决中小供应商融资难、银行发票核验难、核心企业信用难穿透的行业痛点。同时，智能合约在链上实现发票唯一性哈希去重，从机制上杜绝同一张发票在多银行重复贴现融资。

---

## 📂 仓库架构与分工目录

本项目遵循**前后端与智能合约完全解耦**的协同开发架构，各成员可在独立目录内进行开发：

```
supply-chain-finance-dapp/
├── contracts/                  # 【成员 1 负责】智能合约模块（Foundry）
│   ├── contracts/              # Solidity 合约源文件
│   │   ├── RoleManager.sol     # 5 种角色权限与系统紧急暂停
│   │   ├── ReceivableToken.sol # ERC-1155 应收凭证 (拆分、转让、冻结)
│   │   ├── InvoiceRegistry.sol # 发票去重登记与核心企业确认
│   │   ├── FinancingPool.sol   # 融资申请、报价、原子化放款、还款与兑付
│   │   └── MockStablecoin.sol  # ERC-20 测试代币 (mUSD) 与水龙头
│   ├── test/                   # Foundry 单元测试 (47 个)
│   ├── script/                 # 部署脚本 (Deploy.s.sol) 与 ABI 导出
│   ├── abi/                    # 导出的 ABI（前后端直接加载）
│   ├── deployments/            # 各网络合约地址（11155111.json = Sepolia）
│   ├── docs/                   # 合约接口说明、Remix 部署指南、Gas 基线
│   ├── foundry.toml            # 编译与网络配置
│   └── README.md               # 合约开发与部署指南
│
├── backend/                    # 【成员 2 负责】后端 API 与链上同步服务
│   ├── routes/                 # Flask RESTful API 路由
│   ├── migrations/             # Flask-Migrate / Alembic 数据库迁移
│   ├── tests/                  # 后端自动化测试
│   ├── models.py               # 8 张数据库表及关键约束
│   ├── config.py               # 环境变量与配置管理
│   └── README.md               # 后端开发与本地调试指南
│
├── frontend/                   # 【成员 3 负责】前端界面与 Web3 交互
│   ├── static/                 # CSS 样式、Web3 Provider、合约 ABI
│   │   ├── css/style.css       # 统一响应式设计与主题样式
│   │   └── js/web3-provider.js # MetaMask 登录、切链监听、合约调用与 Gas 预估
│   ├── templates/              # HTML 模板视图 (19 个页面/视图)
│   └── README.md               # 前端开发规范
│
├── docs/                       # 【成员 4、5、6 及全员】项目文档与设计资料
│   ├── 供应链金融 DApp 产品需求文档（PRD）.docx  # 原始需求文档
│   ├── PRD.md                  # 需求文档 Markdown 版（含流程图与验收标准）
│   ├── team_division.md        # 6 人分工矩阵与 Git 协作工作流规范
│   └── images/                 # 核心业务流程图与合约调用架构图
│
├── .env.example                # 环境变量配置模板
├── .gitignore                  # Git 忽略规则
├── app.py                      # 根目录应用入口 (兼容本地启动与 Render 云部署)
├── requirements.txt            # 唯一 Python 依赖清单
├── Procfile                    # Render Web Service 部署指令
├── render.yaml                 # Render 云平台 Blueprint 配置
└── README.md                   # 仓库总览文档（当前文件）
```

---

## 👥 团队分工与交付物 (Team Matrix)

详细分工与协作规范请参阅 [`docs/team_division.md`](docs/team_division.md)。

| 成员 | 角色分工 | 核心交付物 | 目录归属 |
| :---: | :--- | :--- | :--- |
| **成员 1** | **智能合约开发与测试** | 5 个 Solidity 合约代码、自动化单元测试、Sepolia 测试网部署、导出 ABI | `contracts/` |
| **成员 2** | **后端开发与云端部署** | Flask REST API、Web3.py 链上同步器、Render 部署、`docs/api.md` | `backend/` |
| **成员 3** | **前端界面与 Web3 交互** | 19 个视图响应式前端页面、MetaMask 钱包集成、Ethers.js 合约调用与 Gas 估算 | `frontend/` |
| **成员 4** | **行业研究与技术报告** | 供应链金融背景调研、技术报告 (10~15 页)、个人贡献报告汇总 | `docs/` |
| **成员 5** | **系统架构设计与手册** | 5 种 UML 架构/时序图、答辩 PPT、产品使用手册 | `docs/` |
| **成员 6** | **测试验证与演示视频** | 功能/性能测试用例、测试报告、YouTube 演示视频录制或 Zoom 演示 | `docs/` |

---

## 🚀 快速启动指南

### 1. 克隆代码仓库
```bash
git clone <your-repository-url>
cd supply-chain-finance-dapp
```

### 2. 智能合约模块（成员 1）
```bash
# 需先安装 Foundry：https://book.getfoundry.sh/getting-started/installation
cd contracts
npm install
forge build
forge test
# 已部署的 Sepolia 地址见 contracts/deployments/11155111.json
```

### 3. 后端与全栈服务启动（成员 2 & 成员 3 联调）
```bash
# 返回项目根目录
cd ..
cp .env.example .env

# 安装 Python 依赖
pip install -r requirements.txt

# 启动本地服务
python app.py
```
浏览器打开 `http://127.0.0.1:5000` 即可看到 DApp 首页并连接 MetaMask。

---

## ☁️ Render 云端一键部署

项目已配置好 `Procfile` 与 `render.yaml`，推送代码至 GitHub 并在 Render 创建 Web Service 即可零配置部署：
- **Build Command**: `pip install -r requirements.txt && flask db upgrade`
- **Start Command**: `gunicorn app:app`

---

## 📋 核心业务流程速览

1. **发票登记**：供应商上传发票 PDF，链下计算 SHA-256 哈希，调用 `submitInvoice` 上链，系统自动拦截重复登记；
2. **凭证生成**：核心企业调用 `confirmInvoice` 确认发票，合约自动铸造等额 `ReceivableToken` (ERC-1155)；
3. **拆分流转**：供应商可将凭证拆分转让给二级供应商；
4. **融资申请**：供应商调用 `requestFinancing` 锁定凭证至资金池；
5. **资金方报价**：资金方调用 `submitQuote` 提供贴现率报价；
6. **原子化放款**：供应商调用 `acceptQuote`，一笔交易同时完成稳定币到账与凭证过户；
7. **到期付款与兑付**：核心企业到期还款至资金池，凭证持有人销毁凭证 1:1 提取稳定币。

---

## 📌 需求文档与待确认事项
完整 PRD 文档请直接查看：[`docs/PRD.md`](docs/PRD.md)。
首次小组例会请对照 PRD 第 10 节 CheckList 确认测试网与各自分工排期。
