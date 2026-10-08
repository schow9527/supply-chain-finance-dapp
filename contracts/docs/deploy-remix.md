# 用 Remix 部署到 Sepolia

部署文件：`remix/SupplyChainFinance.sol`。这是 5 个合约展平后合成的一个文件。合约源码改过之后，要先运行 `./script/export-abi.sh` 重新生成它。

## 准备

- MetaMask 切到 **Sepolia**，部署账户里至少有 0.05 SepoliaETH。可以去 Alchemy 或 Google Cloud 的 Sepolia faucet 领取。
- 用来部署的这个账户会成为**平台管理员**。

## 1. 编译

1. 打开 https://remix.ethereum.org ，新建文件 `SupplyChainFinance.sol`，把 `remix/SupplyChainFinance.sol` 的内容整个粘贴进去。
2. 打开 **Solidity Compiler** 面板，按下表设置（要和本地 Foundry 保持一致，否则 Gas 数据和 Etherscan 验证都会对不上）：

   | 设置 | 值 |
   |---|---|
   | Compiler | `0.8.24` |
   | EVM Version | `cancun` |
   | Optimization | 勾选，runs = `200` |

3. 点 Compile，应该没有报错。

## 2. 按顺序部署

打开 **Deploy & Run Transactions** 面板，Environment 选 **Injected Provider - MetaMask**，并确认下面显示的是 `Sepolia (11155111)`。

每部署完一个合约，就在下方 Deployed Contracts 里复制它的地址，填进后面步骤的参数。

| 步骤 | CONTRACT 下拉框选 | 构造参数 / 调用 | 记下地址 |
|---|---|---|---|
| 1 | `RoleManager` | `admin` = 你的部署账户地址 | ROLE_MANAGER |
| 2 | `ReceivableToken` | `roleManager_` = ROLE_MANAGER | TOKEN |
| 3 | `MockStablecoin` | 无参数 | USD |
| 4 | `InvoiceRegistry` | `roleManager_` = ROLE_MANAGER，`receivableToken_` = TOKEN | REGISTRY |
| 5 | `FinancingPool` | `roleManager_` = ROLE_MANAGER，`receivableToken_` = TOKEN，`stablecoin_` = USD | POOL |
| 6 | 在已部署的 **ReceivableToken** 上调用 `setSystemContracts` | `invoiceRegistry_` = REGISTRY，`financingPool_` = POOL | — |

> ⚠️ 第 6 步**只能调用一次**，地址一旦填错就只能整套重新部署。点 transact 之前请再核对一遍。

## 3. 授予演示角色

在已部署的 **RoleManager** 上：

1. 先调用只读函数 `SUPPLIER`、`CORE_ENTERPRISE`、`FUNDER`、`AUDITOR`，拿到 4 个 bytes32 值。
2. 对每个演示账户调用 `grantRole(role, account)`。注意每个地址只能拥有一种角色。

建议演示时至少准备这些账户：供应商 ×2（用来演示拆分转让）、核心企业 ×1、资金方 ×2（用来演示竞价）、审计员 ×1。

## 4. 冒烟测试（可选）

建议把主流程在 Remix 里手动走一遍：faucet → approve → submitInvoice → confirmInvoice → requestFinancing → submitQuote → acceptQuote → repay → redeem。

- `fileHash` 可以随便填一个非零值，例如 `0x1111111111111111111111111111111111111111111111111111111111111111`。
- 金额按 6 位小数填写，`10000000000` 表示 10,000 mUSD。
- `dueDate` 填 Unix 时间戳，必须晚于当前时间。

## 5. 记录部署信息

新建 `deployments/11155111.json`，格式和本地链的那份一致：

```json
{
  "chainId": 11155111,
  "startBlock": <RoleManager 部署交易所在的区块号>,
  "admin": "0x...",
  "RoleManager": "0x...",
  "ReceivableToken": "0x...",
  "MockStablecoin": "0x...",
  "InvoiceRegistry": "0x...",
  "FinancingPool": "0x..."
}
```

`startBlock` 去 Sepolia Etherscan 上查 RoleManager 的部署交易就能看到。后端从这个区块开始同步事件，不用从 0 开始扫。

## 6. 在 Etherscan 上验证源码（推荐）

验证之后，Etherscan 上能直接读合约、看到解码后的事件，报告里也可以放链接。

做法：在 Remix 的 Plugin Manager 里启用 **Contract Verification**，填入 Etherscan API key，逐个验证。也可以在本地用 `forge verify-contract`，参数按上面的编译设置填写。
