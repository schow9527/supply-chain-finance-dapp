# Gas 优化报告

## 测量方法

- 基准测试：[`test/GasBenchmark.t.sol`](../test/GasBenchmark.t.sol)。按演示主线把每种业务交易各执行一次，用 `vm.snapshotGasLastCall` 记录 Gas。
- 运行命令：`forge test --match-contract GasBenchmark --isolate`。加 `--isolate` 后，每次调用都当作一笔独立交易计算，包含 21,000 的基础费用以及冷存储访问开销，结果和链上实际消耗一致。
- 编译设置：solc 0.8.24、EVM `cancun`、optimizer 开启、runs = 200。优化前后保持完全相同。
- 原始数据：[`gas/before.json`](gas/before.json)、[`gas/after.json`](gas/after.json)；部署成本见 [`gas/deploy-before.txt`](gas/deploy-before.txt) 和 [`gas/deploy-after.txt`](gas/deploy-after.txt)。

## 结果：每笔交易

| 交易 | 合约 | 发起角色 | 优化前 | 优化后 | 变化 | 比例 |
|---|---|---|---:|---:|---:|---:|
| `submitInvoice` | InvoiceRegistry | 供应商 | 219,256 | 173,254 | -46,002 | -21.0% |
| `confirmInvoice` | InvoiceRegistry | 核心企业 | 150,356 | 124,931 | -25,425 | -16.9% |
| `rejectInvoice` | InvoiceRegistry | 核心企业 | 43,935 | 43,332 | -603 | -1.4% |
| `transferReceivable` | ReceivableToken | 供应商 | 78,219 | 74,640 | -3,579 | -4.6% |
| `freeze` | ReceivableToken | 审计员 | 36,540 | 35,915 | -625 | -1.7% |
| `unfreeze` | ReceivableToken | 审计员 | 36,534 | 35,909 | -625 | -1.7% |
| `requestFinancing` | FinancingPool | 供应商 | 171,930 | 145,491 | -26,439 | -15.4% |
| `submitQuote` | FinancingPool | 资金方 | 178,495 | 152,198 | -26,297 | -14.7% |
| `acceptQuote` | FinancingPool | 供应商 | 160,852 | 131,343 | -29,509 | -18.3% |
| `withdrawQuote` | FinancingPool | 资金方 | 51,996 | 49,922 | -2,074 | -4.0% |
| `cancelRequest` | FinancingPool | 供应商 | 81,286 | 78,436 | -2,850 | -3.5% |
| `repay` | FinancingPool | 核心企业 | 85,548 | 83,586 | -1,962 | -2.3% |
| `redeem` | FinancingPool | 持有人 | 66,008 | 64,043 | -1,965 | -3.0% |
| `markOverdue` | FinancingPool | 资金方 | 79,523 | 76,931 | -2,592 | -3.3% |
| `grantRole` | RoleManager | 管理员 | 96,583 | 96,583 | 0 | 0.0% |
| `revokeRole` | RoleManager | 管理员 | 35,650 | 35,650 | 0 | 0.0% |
| `pause` | RoleManager | 管理员 | 47,041 | 47,041 | 0 | 0.0% |
| `faucet` | MockStablecoin | 任何人 | 50,675 | 50,675 | 0 | 0.0% |
| **合计** | | | **1,670,427** | **1,499,880** | **-170,547** | **-10.2%** |

**一笔完整融资的 Gas 合计下降 15.3%**，从 1,032,445 降到 874,846。这里统计的是演示主线上的 7 笔交易：登记发票 → 确认 → 申请融资 → 报价 → 接受报价 → 到期付款 → 兑付。

RoleManager 和 MockStablecoin 没有改动，所以数据不变。

## 结果：部署成本

| 合约 | 优化前 | 优化后 | 变化 |
|---|---:|---:|---:|
| RoleManager | 574,591 | 574,591 | 0 |
| ReceivableToken | 2,133,641 | 1,960,925 | -172,716 |
| MockStablecoin | 516,839 | 516,839 | 0 |
| InvoiceRegistry | 1,142,835 | 901,503 | -241,332 |
| FinancingPool | 1,932,501 | 2,006,354 | +73,853 |
| **合计** | **6,300,407** | **5,960,212** | **-340,195（-5.4%）** |

FinancingPool 的部署成本略有上升，原因是新增了 `SafeCast` 溢出检查的代码。这些成本只在部署时支付一次，换来的是每笔融资交易都更省 Gas。

## 采用的优化手段

### 1. 存储打包（贡献最大）

EVM 每写入一个全新的存储槽，大约要花 22,100 gas。我们把可以缩小位宽的字段压缩后放进同一个槽：

| 结构体 | 优化前 | 优化后 | 做法 |
|---|---:|---:|---|
| `ReceivableToken.Receivable` | 3 槽 | 2 槽 | `faceValue` 改为 `uint96`，和 `originalSupplier` 放在同一个槽 |
| `InvoiceRegistry.Invoice` | 6 槽 | 4 槽 | `amount` 改为 `uint96`，和 `buyer` 放在同一个槽；不再存储发票号字符串（见第 2 点） |
| `FinancingPool.Request` | 4 槽 | 2 槽 | ID 改为 `uint64`，金额改为 `uint96`，和地址、状态放在一起 |
| `FinancingPool.Quote` | 3 槽 | 2 槽 | 同上 |

位宽是否够用：`uint96` 最大约为 7.9 × 10²⁸。按 mUSD 的 6 位小数折算，相当于 7.9 × 10²² 美元，远超实际需要。`uint64` 用于 ID 计数器，也不可能用完。所有向下转换都通过 OpenZeppelin 的 `SafeCast` 进行，一旦超出范围会直接 revert，不会静默截断。`test_RevertWhen_AmountExceedsUint96` 覆盖了这种情况。

### 2. 发票号只记录在事件里，不写入 storage

发票号是变长字符串，存进 storage 至少要占一个槽。它在链上唯一的用途是计算去重哈希，所以现在只保存 `dedupKey`，发票号原文只写进 `InvoiceSubmitted` 事件。事件日志的单价远低于 storage，后端本来也是通过同步事件来获取发票号的。这样做还有一个附带好处：任何合约都无法再直接读到发票号，商业信息的暴露面更小（不过事件日志仍然是公开的）。

### 3. 角色 ID 改为编译期常量

原来每次做权限检查，都要先跨合约调用 `roleManager.SUPPLIER()` 取角色 ID。现在改为共享库 [`Roles.sol`](../contracts/utils/Roles.sol) 里的 `constant`，ID 在编译时就内联进字节码。每笔交易因此少一次外部调用，大约节省 600 gas。

### 4. 合并凭证转账时的角色查询

`ReceivableToken._update` 原来最多要调用两次 `hasRole`，分别判断接收方是供应商还是资金方。现在只调用一次 `roleOf`，拿到角色后在本地比较。另外，`transferReceivable` 原来在修饰符里检查发送方角色，`_update` 里又检查一遍，现在去掉了修饰符里那一次重复检查。

## 评估过但没有采用的方案

| 编译设置 | 18 笔交易 Gas 合计 | 部署成本合计 | 结论 |
|---|---:|---:|---|
| runs = 200（采用） | 1,499,880 | 5,960,212 | 基准 |
| runs = 1,000 | 1,496,625（-0.2%） | 6,510,674（+9.2%） | 不采用 |
| runs = 10,000 | 1,493,471（-0.4%） | 7,573,774（+27.1%） | 不采用 |
| runs = 200 + via-IR | 1,493,285（-0.4%） | 5,613,547（-5.8%） | 不采用 |

- **提高 runs**：交易 Gas 只降了 0.2% 到 0.4%，部署成本却增加 9% 到 27%。对于这样一个交易量不大的平台，不划算。
- **via-IR**：两项指标都有小幅改善，但编译时间明显变长；而且在 Remix 部署和 Etherscan 验证时，都要额外配置 `viaIR`，容易出错。收益和风险相比，暂时不采用。

## 安全回归

- 52 个测试全部通过，其中新增的 2 个分别覆盖 `uint96` 溢出和“发票号只出现在事件中”。
- 合约代码行覆盖率 96.9%。
- Slither（排除 informational 和 timestamp）：0 个问题。
