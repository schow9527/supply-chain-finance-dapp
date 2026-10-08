# 合约接口说明（v0.2）

给成员 2（后端事件同步）和成员 3（前端调用）用。金额单位都是 mUSD 的最小单位（6 位小数，`10_000e6` = 10,000 mUSD）；凭证数量和面值使用同一单位，1 个凭证单位兑付 1 个 mUSD 单位。

## 角色

| 角色 | 常量 | bytes32 值 |
|---|---|---|
| 管理员 | `DEFAULT_ADMIN_ROLE` | `0x00…00` |
| 供应商 | `SUPPLIER()` | `keccak256("SUPPLIER")` |
| 核心企业 | `CORE_ENTERPRISE()` | `keccak256("CORE_ENTERPRISE")` |
| 资金方 | `FUNDER()` | `keccak256("FUNDER")` |
| 审计员 | `AUDITOR()` | `keccak256("AUDITOR")` |

前端判断角色：先调用 `RoleManager.isRegistered(addr)`，结果为 true 时再用 `roleOf(addr)` 取角色。之所以分两步，是因为管理员的角色值是 0，和“未注册”返回的值相同。

## 链上交易清单（20 种）

| # | 函数 | 调用者 | 前置条件 / 需要的 approve | 事件 |
|---|---|---|---|---|
| 1 | `RoleManager.grantRole(role, account)` | 管理员 | 该地址当前没有任何角色 | `RoleGranted` |
| 2 | `RoleManager.revokeRole(role, account)` | 管理员 | | `RoleRevoked` |
| 3 | `RoleManager.pause()` | 管理员 | | `Paused` |
| 4 | `RoleManager.unpause()` | 管理员 | | `Unpaused` |
| 5 | `InvoiceRegistry.submitInvoice(invoiceNo, buyer, amount, dueDate, fileHash)` | 供应商 | buyer 是核心企业；amount > 0；dueDate 晚于当前时间；fileHash 是 PDF 的哈希 | `InvoiceSubmitted` |
| 6 | `InvoiceRegistry.confirmInvoice(invoiceId)` | 核心企业（发票买方） | 发票处于待确认状态且未到期 | `InvoiceConfirmed`、`ReceivableMinted`、`TransferSingle` |
| 7 | `InvoiceRegistry.rejectInvoice(invoiceId, reason)` | 核心企业（发票买方） | 必须填写 reason | `InvoiceRejected` |
| 8 | `ReceivableToken.transferReceivable(to, id, amount)` | 供应商 | to 是供应商；凭证未冻结、未到期 | `ReceivableTransferred`、`TransferSingle` |
| 9 | `ReceivableToken.freeze(id, reason)` | 审计员 | | `ReceivableFrozen` |
| 10 | `ReceivableToken.unfreeze(id, reason)` | 审计员 | | `ReceivableUnfrozen` |
| 11 | `FinancingPool.requestFinancing(id, amount)` | 供应商 | **不需要 approve**；凭证会托管进池子 | `FinancingRequested`、`TransferSingle` |
| 12 | `FinancingPool.submitQuote(requestId, discountBps)` | 资金方 | **需要先 `mUSD.approve(pool, payout)`**；报价资金会锁进池子 | `QuoteSubmitted` |
| 13 | `FinancingPool.withdrawQuote(quoteId)` | 报价的资金方 | 报价尚未被接受 | `QuoteWithdrawn` |
| 14 | `FinancingPool.acceptQuote(requestId, quoteId)` | 发起申请的供应商 | 凭证转给资金方、mUSD 转给供应商，两步在同一笔交易里完成 | `FinancingFunded`、`TransferSingle` |
| 15 | `FinancingPool.cancelRequest(requestId)` | 发起申请的供应商 | 尚未接受任何报价；凭证退回供应商 | `FinancingCancelled`、`TransferSingle` |
| 16 | `FinancingPool.repay(id)` | 核心企业（凭证买方） | **需要先 `mUSD.approve(pool, faceValue)`**；正常和逾期状态都可以付款 | `Repaid`、`ReceivableStatusChanged` |
| 17 | `FinancingPool.redeem(id)` | 任一凭证持有人 | 已付款且未冻结；一次兑付持有的全部余额 | `Redeemed`、`TransferSingle` |
| 18 | `FinancingPool.markOverdue(id)` | 持有该凭证的资金方 | 已过到期日且尚未付款 | `MarkedOverdue`、`ReceivableStatusChanged` |
| 19 | `MockStablecoin.faucet()` | 任何人 | | `Transfer` |
| 20 | `MockStablecoin.approve(spender, amount)` | 资金方、核心企业 | 标准 ERC-20 | `Approval` |

`discountBps` 是贴现率，单位为万分之一：`300` 表示 3%。供应商实际到手金额 = `amount × (10000 − bps) / 10000`，前端可以直接调用 `FinancingPool.previewPayout(amount, bps)` 计算。

## 状态枚举（合约返回的是数字）

| 对象 | 枚举值 |
|---|---|
| 发票 `InvoiceStatus` | 0 None · 1 Pending · 2 Confirmed · 3 Rejected |
| 凭证 `ReceivableToken.Status` | 0 None · 1 Active · 2 Repaid · 3 Overdue；冻结是单独的 `frozen` 字段 |
| 融资申请 `RequestStatus` | 0 None · 1 Open · 2 Funded · 3 Cancelled |
| 报价 `QuoteStatus` | 0 None · 1 Active · 2 Accepted · 3 Withdrawn |

## 查询函数

> **v0.2 变更（Gas 优化）**：`getInvoice` 返回的结构里**不再包含 `invoiceNo`**，发票号请从 `InvoiceSubmitted` 事件中读取，或者通过后端查询。几个结构体的字段顺序和类型也有调整：金额字段改为 `uint96`，ID 字段改为 `uint64`。如果前端和后端都按字段名读取（例如 ethers 的 `result.amount`），就不需要改代码。

| 查询函数 | 返回结构的字段（按顺序） |
|---|---|
| `getInvoice(id)` | supplier, dueDate, status, buyer, amount, fileHash, dedupKey |
| `getReceivable(id)` | buyer, dueDate, status, frozen, originalSupplier, faceValue |
| `getRequest(id)` | supplier, status, receivableId, amount, acceptedQuoteId |
| `getQuote(id)` | funder, discountBps, status, requestId, payout |

- `InvoiceRegistry.getInvoice(id)`、`invoiceCount()`、`computeDedupKey(...)`、`invoiceIdByKey(key)`
- `ReceivableToken.getReceivable(id)`、`balanceOf(addr, id)`
- `FinancingPool.getRequest(id)`、`getQuote(id)`、`requestCount()`、`quoteCount()`、`overdueCount(core)`、`previewPayout(amount, bps)`

“某个地址持有哪些凭证”这类列表查询，合约里没有提供，需要由后端根据 `TransferSingle` 事件自己汇总。

## 错误（前端显示拒绝原因）

所有合约都用 custom error。ethers v6 在加载 ABI 之后会自动解析，从 `error.revert.name` 和 `error.revert.args` 读取。常见错误：

| 错误 | 建议提示文案 |
|---|---|
| `SystemPaused` | 系统已暂停 |
| `Unauthorized(account, role)` | 当前账户没有执行该操作的权限 |
| `InvoiceAlreadyExists(id)` | 发票已存在（编号 #id） |
| `InvalidBuyer` / `InvalidAmount` / `InvalidDueDate` / `InvalidFileHash` | 表单校验失败 |
| `NotInvoiceBuyer` | 这张发票不是开给你的 |
| `ReceivableIsFrozen(id)` | 凭证已被冻结 |
| `ReceivableMatured` / `ReceivableNotFinanceable` | 凭证已到期或状态不允许该操作 |
| `InvalidRecipient(to)` | 接收方不是已注册的供应商 |
| `ERC1155InsufficientBalance` | 凭证余额不足 |
| `ERC20InsufficientBalance` / `ERC20InsufficientAllowance` | mUSD 余额或授权额度不足 |
| `NotOverdueYet` | 还没到期，不能标记逾期 |

## 相对 PRD 的调整（需在例会上同步）

1. **申请融资时把凭证托管进池子**：自动实现“同一份金额不能同时挂两个申请”。供应商不再需要做 `setApprovalForAll`，因为 Token 默认允许 Pool 作为操作人转移凭证。
2. **报价时锁定资金**：避免供应商接受报价时，因资金方余额或授权不足而失败。为此新增了 `withdrawQuote`，让落选或改变主意的资金方取回资金。
3. **凭证的元数据和状态都存在 Token 上**（买方、面值、到期日、状态、冻结），FinancingPool 不需要再读 InvoiceRegistry。
4. **拒绝发票后释放去重键**，供应商改正后可以用同一个发票号重新提交。
5. **逾期后仍然可以付款**，状态从 Overdue 变为 Repaid。
6. **faucet 对所有人开放**，原 PRD 写的是仅限已注册用户。
7. **unfreeze 也要求填写原因**，以留下审计记录。
8. **暂停期间**：管理员的授予/撤销角色、审计员的冻结/解冻仍然可以执行，方便应急处置；其他业务写操作一律被拒绝；测试币的 `faucet` 和 `approve` 不受暂停影响。
9. 资金方持有凭证后不能再转让，只能等待兑付。

## 安全检查记录

- Slither（排除 informational）：没有高危和中危问题。
- 残留的 `timestamp` 提示属于可接受风险：到期日以天为粒度，出块者能操纵的时间只有几秒，不影响判断结果。
- 所有涉及转账的函数都加了 `nonReentrant`，并且遵循“先改状态、发事件，再做外部调用”的顺序。
