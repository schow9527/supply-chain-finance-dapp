# 设计图集（成员 5：系统设计与演示）

> 本目录收录技术报告要求的 5 类图。每个图提供 mermaid 源码（`.mmd`，GitHub 可原生渲染，可直接编辑）与导出的 PNG 图片（供报告 / PPT 插入）。

## 01. 系统架构图

四层架构：用户层 → 前端层 → 区块链层（Sepolia）+ 后端层（Flask/Render）→ 数据层；链下链上职责分离，后端不存私钥。

![系统架构图](01-system-architecture.png)

<details><summary>mermaid 源码</summary>

```mermaid
flowchart TB
    subgraph U["用户层（5 种角色）"]
        U1["供应商 Supplier"]
        U2["核心企业 Core Enterprise"]
        U3["资金方 Financier"]
        U4["审计员 Auditor"]
        U5["管理员 Admin"]
    end

    subgraph FE["前端层（HTML + CSS + JS，19 个视图）"]
        FE1["供应商工作台<br/>仪表盘 / 上传发票 / 发票 / 凭证 / 融资"]
        FE2["核心企业工作台<br/>仪表盘 / 待确认发票 / 应付清册"]
        FE3["资金方工作台<br/>仪表盘 / 融资市场 / 放款资产"]
        FE4["审计工作台<br/>审计看板 / 凭证穿透追踪"]
        FE5["管理工作台<br/>资质审核 / 角色与系统控制"]
        FE6["公共页面<br/>首页 / 注册申请 / 交易历史 / 事件日志"]
        FE7["Ethers.js 合约调用<br/>Gas 预估 · 交易状态提示"]
    end

    subgraph WALLET["钱包"]
        MM["MetaMask<br/>交易签名"]
    end

    subgraph CHAIN["区块链层（Sepolia 测试网）"]
        C1["RoleManager.sol<br/>角色权限 + 紧急暂停"]
        C2["InvoiceRegistry.sol<br/>发票登记 + 防重复"]
        C3["ReceivableToken.sol (ERC-1155)<br/>应收凭证 铸造/拆分/冻结"]
        C4["FinancingPool.sol<br/>融资申请/报价/原子放款/还款/兑付"]
        C5["MockStablecoin.sol (ERC-20)<br/>测试稳定币 mUSD + faucet"]
    end

    subgraph BE["后端层（Python Flask，部署于 Render）"]
        B1["REST API<br/>企业 / 发票 / 凭证 / 融资 / 仪表盘 / 审计"]
        B2["Web3.py 事件监听器<br/>同步链上事件"]
        B3["文件存储<br/>发票 PDF（链下）+ SHA-256 哈希"]
    end

    subgraph DB["数据层（SQLite / PostgreSQL，7 张表）"]
        D1["enterprises · invoices · holdings<br/>financing_requests · quotes<br/>chain_events · sync_state"]
    end

    U --> FE
    FE -->|"Ethers.js 发起交易"| MM
    MM -->|"签名后广播"| CHAIN
    FE -->|"REST 查询（链下数据 / 缓存）"| B1
    CHAIN -->|"链上事件"| B2
    B2 --> D1
    B1 --> D1
    B1 --> B3
    C1 -.->|"权限检查"| C2
    C2 -.->|"确认后铸造凭证"| C3
    C4 -.->|"转账/销毁凭证"| C3
    C4 -.->|"mUSD 划转"| C5

    classDef user fill:#e8f4fd,stroke:#4a90d9;
    classDef fe fill:#fff7e6,stroke:#d9a441;
    classDef chain fill:#e9f7ef,stroke:#3ba272;
    classDef be fill:#f3e8fd,stroke:#8e5bd9;
    classDef db fill:#fdeaea,stroke:#d94a4a;
    class U1,U2,U3,U4,U5 user
    class FE1,FE2,FE3,FE4,FE5,FE6,FE7 fe
    class C1,C2,C3,C4,C5 chain
    class B1,B2,B3 be
    class D1 db
```

</details>

## 02. 合约交互图（时序图）

发票登记 → 确认铸造 → 拆分转让 → 融资申请 → 报价锁资 → 原子放款 → 到期付款 → 兑付/逾期的完整链上交互时序。

![合约交互图（时序图）](02-contract-interaction.png)

<details><summary>mermaid 源码</summary>

```mermaid
sequenceDiagram
    autonumber
    actor S as 供应商
    actor CE as 核心企业
    actor F as 资金方
    participant IR as InvoiceRegistry
    participant RT as ReceivableToken<br/>(ERC-1155)
    participant FP as FinancingPool
    participant USD as MockStablecoin<br/>(ERC-20)

    Note over S,IR: ① 发票登记（防重复融资的第一道闸）
    S->>IR: submitInvoice(invoiceNo, buyer, amount, dueDate, fileHash)
    alt 去重键 invoiceNo+buyer+supplier+amount 已存在
        IR-->>S: revert InvoiceAlreadyExists
    else 首次登记
        IR-->>S: emit InvoiceSubmitted
    end

    Note over CE,RT: ② 核心企业确认，自动铸造等额应收凭证
    CE->>IR: confirmInvoice(invoiceId)
    IR->>RT: mint(supplier, receivableId, amount)
    RT-->>CE: emit InvoiceConfirmed + ReceivableMinted

    Note over S,RT: ③ 凭证拆分转让（可选，信用向下游传递）
    S->>RT: transferReceivable(to, id, amount)
    RT-->>S: emit ReceivableTransferred

    Note over S,FP: ④ 申请融资（凭证自动托管进池，杜绝二次质押）
    S->>FP: requestFinancing(id, amount)
    FP->>RT: 托管划转凭证（TransferSingle 至池子）

    Note over F,FP: ⑤ 资金方报价（贴现率 bps，报价资金锁定）
    F->>USD: approve(pool, payout)
    F->>FP: submitQuote(requestId, discountBps)
    FP->>USD: 锁定报价资金

    Note over S,USD: ⑥ 接受报价：原子化放款（任一步失败整笔回滚）
    S->>FP: acceptQuote(requestId, quoteId)
    FP->>RT: 凭证所有权 → 资金方
    FP->>USD: 贴现后金额 → 供应商
    FP-->>S: emit FinancingFunded

    Note over CE,FP: ⑦ 到期付款入池
    CE->>USD: approve(pool, faceValue)
    CE->>FP: repay(id)
    FP-->>CE: emit Repaid

    Note over F,FP: ⑧ 持有人兑付（1:1 销毁凭证领取 mUSD）
    F->>FP: redeem(id)
    FP->>RT: burn 凭证
    FP->>USD: 面值金额 → 持有人
    FP-->>F: emit Redeemed

    Note over F,FP: ⑨ 逾期未付：资金方标记逾期
    F->>FP: markOverdue(id)
    FP-->>F: emit MarkedOverdue（逾期记录仪表盘可见）
```

</details>

## 03. 数据模型图（ER 图）

后端 7 张表的关系：企业、发票、持有记录、融资申请、报价、链上事件、同步游标。

![数据模型图（ER 图）](03-data-model.png)

<details><summary>mermaid 源码</summary>

```mermaid
erDiagram
    ENTERPRISES ||--o{ INVOICES : "作为供应商开具"
    ENTERPRISES ||--o{ INVOICES : "作为核心企业确认"
    INVOICES ||--|| HOLDINGS : "确认后生成凭证持有记录"
    HOLDINGS ||--o{ FINANCING_REQUESTS : "凭证发起融资申请"
    FINANCING_REQUESTS ||--o{ QUOTES : "收到资金方报价"
    ENTERPRISES ||--o{ QUOTES : "资金方提交报价"

    ENTERPRISES {
        int id PK
        string wallet_address "钱包地址（唯一）"
        string company_name "企业名称"
        string contact "联系人"
        string role "申请角色 Supplier/Core/Financier"
        string status "审核状态 pending/approved/rejected"
        string reject_reason "驳回原因"
        string grant_tx_hash "链上授权交易哈希"
    }

    INVOICES {
        int id PK
        int onchain_invoice_id "链上发票 ID"
        string invoice_no "发票号（事件读取）"
        string supplier "供应商地址"
        string buyer "核心企业地址"
        int amount "金额（mUSD 最小单位）"
        date due_date "到期日"
        string file_hash "PDF 的 SHA-256"
        string file_path "链下文件路径"
        string status "状态 Pending/Confirmed/Rejected"
    }

    HOLDINGS {
        int id PK
        int receivable_id "链上凭证 ID（ERC-1155 tokenId）"
        string holder "持有人地址"
        int balance "持有份额余额"
    }

    FINANCING_REQUESTS {
        int id PK
        int onchain_request_id "链上申请 ID"
        int receivable_id "凭证 ID"
        string supplier "申请人地址"
        int amount "申请融资金额"
        string status "状态 Open/Funded/Cancelled"
        int accepted_quote_id "最终成交报价 ID"
    }

    QUOTES {
        int id PK
        int onchain_quote_id "链上报价 ID"
        int request_id "所属融资申请"
        string funder "资金方地址"
        int discount_bps "贴现率（万分之一）"
        int payout "实际放款金额"
        string status "状态 Active/Accepted/Withdrawn"
    }

    CHAIN_EVENTS {
        int id PK
        int block_number "区块号"
        string tx_hash "交易哈希"
        string contract_name "合约名"
        string event_name "事件名"
        json args "解析后参数 JSON"
        datetime created_at "时间戳"
    }

    SYNC_STATE {
        string contract_name PK "合约名"
        int last_block "已同步到的区块高度"
    }
```

</details>

## 04. 业务流程图

核心业务流程：上传发票 → 链上查重 → 核心企业确认 → 凭证铸造 → 拆分/融资/持有三选一 → 报价成交 → 到期付款 → 兑付闭环，含拒绝、取消、逾期、冻结分支。

![业务流程图](04-business-flow.png)

<details><summary>mermaid 源码</summary>

```mermaid
flowchart TD
    START([供应商开具发票]) --> UPLOAD["上传发票元数据 + PDF<br/>文件哈希 SHA-256 上链"]
    UPLOAD --> DEDUP{"链上查重<br/>发票号+买卖双方+金额组合"}
    DEDUP -->|已存在| REJECT_DUP["合约拒绝<br/>InvoiceAlreadyExists"] --> END1([流程终止])
    DEDUP -->|通过| PENDING["发票状态：待确认<br/>PDF 存链下，哈希存链上"]

    PENDING --> CE{"核心企业查验发票"}
    CE -->|拒绝（需填原因）| REJECTED["状态：已拒绝<br/>释放去重键，可修改后重提"] --> END2([流程终止])
    CE -->|确认| MINT["自动铸造等额应收凭证 ERC-1155<br/>信用确权完成"]

    MINT --> CHOICE{"供应商选择"}
    CHOICE -->|拆分转让| SPLIT["按份额转给二级供应商<br/>（仅限已注册供应商、未冻结未到期）"] --> CHOICE
    CHOICE -->|持有到期| HOLD["等待核心企业到期付款"]
    CHOICE -->|发起融资| RF["申请融资<br/>凭证自动托管进池（不可二次质押）"]

    RF --> QUOTE["资金方报价（贴现率 bps）<br/>报价资金锁定进池"]
    QUOTE --> ACCEPT{"供应商选择报价"}
    ACCEPT -->|接受| FUND["原子化放款：一笔交易内<br/>凭证→资金方，贴现后资金→供应商"]
    ACCEPT -->|取消申请| CANCEL["凭证退回供应商"] --> CHOICE

    FUND --> DUE{"到期日核对"}
    DUE -->|核心企业按时付款| REPAY["面值全额付入融资池"]
    DUE -->|逾期未付| OVERDUE["资金方标记逾期<br/>逾期记录链上留痕"] --> REPAY2["逾期后仍可付款"]
    REPAY2 --> REPAY

    REPAY --> REDEEM["当前凭证持有人销毁凭证<br/>按 1:1 兑付稳定币"]
    REDEEM --> END3([融资闭环完成])

    FREEZE_NOTE["审计员任意时点可冻结/解冻凭证<br/>冻结后不可转让、融资、兑付"] -.-> MINT

    classDef supplier fill:#e8f4fd,stroke:#4a90d9;
    classDef core fill:#e9f7ef,stroke:#3ba272;
    classDef funder fill:#fff7e6,stroke:#d9a441;
    classDef auditor fill:#fdeaea,stroke:#d94a4a;
    class UPLOAD,PENDING,SPLIT,RF,HOLD supplier
    class CE,REJECTED,MINT,REPAY,REPAY2 core
    class QUOTE,FUND,OVERDUE funder
    class FREEZE_NOTE auditor
```

</details>

## 05. 界面图（页面导航结构）

19 个页面/视图的导航关系：首页连接钱包 → 角色检查 → 各角色工作台 → 公共交易历史与事件日志。

![界面图（页面导航结构）](05-ui-navigation.png)

<details><summary>mermaid 源码</summary>

```mermaid
flowchart TD
    LANDING["首页 Landing<br/>产品介绍 · 连接 MetaMask"] --> CHECK{"链上角色检查<br/>isRegistered + roleOf"}
    CHECK -->|未注册| REG["注册申请页<br/>填写企业资料 · 选择角色<br/>等待管理员审核"]
    REG -.->|审核通过链上授权| CHECK
    CHECK -->|供应商| S1["供应商仪表盘<br/>凭证总额 / 融资总额 / 待办"]
    CHECK -->|核心企业| C1["核心企业仪表盘<br/>待确认数 / 应付总额 / 临期预警"]
    CHECK -->|资金方| F1["资金方仪表盘<br/>放款总额 / 应收本息 / 逾期监控"]
    CHECK -->|审计员| A1["全局审计看板<br/>发票总数 / 流转总额 / 逾期率"]
    CHECK -->|管理员| AD1["资质审核管理<br/>链上核准授权 / 驳回"]

    S1 --> S2["上传发票页"]
    S1 --> S3["我的发票列表<br/>状态筛选 · PDF 核对"]
    S1 --> S4["我的应收凭证<br/>拆分转让 · 发起融资"]
    S1 --> S5["我的融资管理<br/>查看报价 · 接受放款 / 取消"]
    S4 --> S2

    C1 --> C2["待确认发票<br/>预览 PDF · 确认 / 拒绝"]
    C1 --> C3["应付账款清册<br/>按到期日排序 · 一键付款"]

    F1 --> F2["融资市场<br/>待报价项目 · 输入贴现率"]
    F1 --> F3["我的放款资产<br/>到期兑付 · 标记逾期"]

    A1 --> A2["凭证穿透追踪<br/>流转树 · 冻结 / 解冻"]

    AD1 --> AD2["角色与系统控制<br/>角色吊销 · 紧急暂停 / 恢复"]

    S1 --> PUB["交易历史中心（全角色）"]
    C1 --> PUB
    F1 --> PUB
    A1 --> PUB
    AD1 --> PUB
    PUB --> EV["合约事件日志（管理员 / 审计员）<br/>按类型 / 时间 / 地址筛选"]

    classDef pub fill:#f2f2f2,stroke:#888;
    classDef role1 fill:#e8f4fd,stroke:#4a90d9;
    classDef role2 fill:#e9f7ef,stroke:#3ba272;
    classDef role3 fill:#fff7e6,stroke:#d9a441;
    classDef role4 fill:#fdeaea,stroke:#d94a4a;
    classDef role5 fill:#f3e8fd,stroke:#8e5bd9;
    class LANDING,CHECK pub
    class REG,S1,S2,S3,S4,S5 role1
    class C1,C2,C3 role2
    class F1,F2,F3 role3
    class A1,A2,EV role4
    class AD1,AD2 role5
```

</details>

