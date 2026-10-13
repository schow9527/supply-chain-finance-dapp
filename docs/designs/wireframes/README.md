# UI 线框图集（供前端开发参考）

> 成员 5 绘制，供成员 3 前端实现作页面参考。共 19 张，与 PRD §8「前端页面清单（19 个页面/视图）」一一对应。
> 红色编号批注是设计要点与验收标准（F-xx）的对应说明，实现时请逐条核对。

## 阅读方式

| 编号 | 文件 | 页面 | 对应功能 |
| :--- | :--- | :--- | :--- |
| 00 | [00-landing-homepage.png](00-landing-homepage.png) | 首页 Landing | F-01 |
| 01 | [01-register-application.png](01-register-application.png) | 注册申请页 | F-02 |
| 02 | [02-supplier-dashboard.png](02-supplier-dashboard.png) | 供应商仪表盘 | F-23 |
| 03 | [03-supplier-upload-invoice.png](03-supplier-upload-invoice.png) | 上传发票页 | F-06, F-07 |
| 04 | [04-supplier-invoices.png](04-supplier-invoices.png) | 我的发票列表 | F-10 |
| 05 | [05-supplier-receivables.png](05-supplier-receivables.png) | 我的应收凭证 | F-11, F-12, F-15 |
| 06 | [06-supplier-financing.png](06-supplier-financing.png) | 我的融资管理 | F-17, F-18 |
| 07 | [07-core-dashboard.png](07-core-dashboard.png) | 核心企业仪表盘 | F-23 |
| 08 | [08-core-pending-invoices.png](08-core-pending-invoices.png) | 待确认发票 | F-08, F-09 |
| 09 | [09-core-payables.png](09-core-payables.png) | 应付账款清册 | F-19 |
| 10 | [10-financier-dashboard.png](10-financier-dashboard.png) | 资金方仪表盘 | F-23 |
| 11 | [11-financier-market.png](11-financier-market.png) | 融资市场 | F-16 |
| 12 | [12-financier-assets.png](12-financier-assets.png) | 我的放款资产 | F-20, F-21 |
| 13 | [13-auditor-dashboard.png](13-auditor-dashboard.png) | 全局审计看板 | F-23 |
| 14 | [14-auditor-tracking.png](14-auditor-tracking.png) | 凭证穿透追踪 | F-13, F-14 |
| 15 | [15-admin-review.png](15-admin-review.png) | 资质审核管理 | F-03 |
| 16 | [16-admin-roles-control.png](16-admin-roles-control.png) | 角色与系统控制 | F-04, F-05 |
| 17 | [17-transactions.png](17-transactions.png) | 交易历史中心 | F-24 |
| 18 | [18-event-logs.png](18-event-logs.png) | 合约事件日志 | F-25 |

## 通用布局规范

1. **顶部导航栏**：Logo + 全局菜单（首页 / 仪表盘 / 交易历史 / 事件日志）+ 右侧钱包状态胶囊（地址缩写 + 已连接状态）。切换钱包账户后页面按新角色自动切换（F-01）。
2. **左侧边栏**：仅角色工作台页面出现，列出该角色的功能菜单；当前项高亮。
3. **交易反馈规范**：所有上链按钮点击后必须经过「MetaMask 签名 → 交易广播 → 等待确认 → 成功/失败提示」四阶段；失败时展示合约 custom error 的解析结果（见 `contracts/docs/interface.md` 错误表）。
4. **Gas 预估**：每次发起交易前在按钮附近显示预估 Gas 费用（F-26）。
5. **状态徽章配色**：待确认/开放中 = 橙，成功/正常/已确认 = 绿，失败/拒绝/冻结 = 红，未到期/进行中 = 蓝，中立 = 灰。全站统一。

## 线框图

### 00 首页 Landing
![首页](00-landing-homepage.png)

### 01 注册申请页
![注册申请页](01-register-application.png)

### 02 供应商仪表盘
![供应商仪表盘](02-supplier-dashboard.png)

### 03 上传发票页
![上传发票页](03-supplier-upload-invoice.png)

### 04 我的发票列表
![我的发票列表](04-supplier-invoices.png)

### 05 我的应收凭证
![我的应收凭证](05-supplier-receivables.png)

### 06 我的融资管理
![我的融资管理](06-supplier-financing.png)

### 07 核心企业仪表盘
![核心企业仪表盘](07-core-dashboard.png)

### 08 待确认发票
![待确认发票](08-core-pending-invoices.png)

### 09 应付账款清册
![应付账款清册](09-core-payables.png)

### 10 资金方仪表盘
![资金方仪表盘](10-financier-dashboard.png)

### 11 融资市场
![融资市场](11-financier-market.png)

### 12 我的放款资产
![我的放款资产](12-financier-assets.png)

### 13 全局审计看板
![全局审计看板](13-auditor-dashboard.png)

### 14 凭证穿透追踪
![凭证穿透追踪](14-auditor-tracking.png)

### 15 资质审核管理
![资质审核管理](15-admin-review.png)

### 16 角色与系统控制
![角色与系统控制](16-admin-roles-control.png)

### 17 交易历史中心
![交易历史中心](17-transactions.png)

### 18 合约事件日志
![合约事件日志](18-event-logs.png)
