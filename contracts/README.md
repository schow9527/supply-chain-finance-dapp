# Contracts — Supply-Chain Finance DApp

成员 1 负责。Solidity 0.8.24 + OpenZeppelin 5.6 + Foundry。

> 工具链用 Foundry 而不是 Hardhat：测试直接用 Solidity 写、速度快，`forge snapshot` / `--gas-report` 便于做 Gas 优化前后对比，`forge coverage` 直接出覆盖率。

目录：`contracts/` 合约源码 · `test/` 测试 · `script/` 部署与 ABI 导出 · `abi/` ABI · `deployments/` 部署地址 · `remix/` Remix 部署用的单文件 · `docs/` 接口与部署文档

## 合约一览

| 合约 | 职责 |
|---|---|
| `RoleManager` | 5 种角色的授予/撤销（每个地址只能有一种角色）、全局紧急暂停 |
| `InvoiceRegistry` | 登记发票、哈希去重、核心企业确认/拒绝；确认时调用 Token 铸造凭证 |
| `ReceivableToken` | ERC-1155 应收凭证（id = 发票 id，数量 = 面值），拆分转让、冻结；存凭证状态 |
| `FinancingPool` | 融资申请（凭证托管）、报价（资金锁定）、放款、到期付款、兑付、逾期 |
| `MockStablecoin` | 测试稳定币 mUSD（**6 位小数**），任何人可 `faucet()` 领 100,000 |

调用关系：Registry → Token（mint）；Pool → Token（转移、burn、改状态）；Pool → mUSD；三个业务合约都 → RoleManager（查角色、查暂停）。

接口细节（函数、事件、错误、前端需要的 approve）见 [docs/interface.md](docs/interface.md)。

## Sepolia 部署信息（2026-10-08，Gas 优化版）

| 合约 | 地址 |
|---|---|
| RoleManager | [`0x82f86a2B31C424b4833b5BAb82464eB7f69B6a2E`](https://sepolia.etherscan.io/address/0x82f86a2B31C424b4833b5BAb82464eB7f69B6a2E) |
| ReceivableToken | [`0x3c9EcDdf7e788F7B8e04D4177d04B3c291E0368f`](https://sepolia.etherscan.io/address/0x3c9EcDdf7e788F7B8e04D4177d04B3c291E0368f) |
| MockStablecoin | [`0xE3C713Db876c97600141Ba34C7Cb68898CF1E04F`](https://sepolia.etherscan.io/address/0xE3C713Db876c97600141Ba34C7Cb68898CF1E04F) |
| InvoiceRegistry | [`0x39605C1D4FCE3D85DC14f7f283899b984dd1eD7a`](https://sepolia.etherscan.io/address/0x39605C1D4FCE3D85DC14f7f283899b984dd1eD7a) |
| FinancingPool | [`0x2bb0A6e688C331248fe8575121F799B5286985c6`](https://sepolia.etherscan.io/address/0x2bb0A6e688C331248fe8575121F799B5286985c6) |

- 管理员：`0x0ced068d2f30d72ca4c8d41d9619a2183d06834f`
- 起始区块（后端事件同步从这里开始）：`11869257`
- 机器可读版本：[deployments/11155111.json](deployments/11155111.json)
- 部署方式：Remix + MetaMask，solc 0.8.24 / cancun / optimizer 200
- 首次部署（优化前版本，已弃用）的 RoleManager 为 `0x441c4300B1c6F900050A298D6960A5C0A7e43942`，起始区块 11868898

## 常用命令

```bash
# 先安装 Foundry: https://book.getfoundry.sh/getting-started/installation
npm install                 # 安装 OpenZeppelin 与 forge-std
forge build
forge test                  # 运行全部测试
npm run coverage            # 覆盖率（排除脚本与测试文件）
npm run gas                 # Gas 基准，结果写入 snapshots/GasBenchmark.json
./script/export-abi.sh      # 导出 ABI 到 abi/
```

### 本地链部署（开发联调用）

```bash
anvil
forge script script/Deploy.s.sol --rpc-url http://127.0.0.1:8545 \
  --unlocked --sender 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 --broadcast
```

地址写入 `deployments/31337.json`。可用 `DEMO_SUPPLIERS=addr1,addr2` 等环境变量在部署时直接授予角色（见 `.env.example`）。

### Sepolia 部署

**方式 A：Remix + MetaMask（推荐）**，按 [docs/deploy-remix.md](docs/deploy-remix.md) 一步步操作，使用的文件是 `remix/SupplyChainFinance.sol`。

**方式 B：Foundry 脚本**

```bash
cp .env.example .env        # 填 RPC 和 Etherscan key
source .env
forge script script/Deploy.s.sol --rpc-url sepolia --account <keystore名> --broadcast --verify
```

用 `cast wallet import <名字> --interactive` 导入部署钱包，**不要把私钥写进文件或命令行**。地址写入 `deployments/11155111.json`，`startBlock` 是后端事件同步的起始区块。

## 给其他成员的输出

- `abi/*.json` — 纯 ABI，web3.py / ethers.js 直接加载
- `deployments/<chainId>.json` — 合约地址、管理员地址、起始区块
- `docs/interface.md` — 函数、事件、错误码说明
- `docs/gas-optimization.md` — Gas 优化前后对比与分析（原始数据在 `docs/gas/`）
