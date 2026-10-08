# 智能合约模块 (Smart Contracts)

> **责任人**：成员 1  
> **技术栈**：Solidity (^0.8.20), Hardhat, Ethers.js, OpenZeppelin  

---

## 目录结构

```
contracts/
├── contracts/             # Solidity 合约源文件
│   ├── RoleManager.sol    # 角色管理与系统紧急暂停
│   ├── ReceivableToken.sol# ERC-1155 应收账款凭证
│   ├── InvoiceRegistry.sol# 发票登记、去重与核心企业确认
│   ├── FinancingPool.sol  # 融资申请、报价、放款、还款与兑付
│   └── MockStablecoin.sol # ERC-20 测试稳定币及水龙头
├── scripts/
│   └── deploy.js          # 合约部署与跨合约权限配置脚本
├── test/                  # 合约单元测试目录
├── hardhat.config.js      # Hardhat 配置文件 (含 Sepolia 网络配置)
├── package.json           # 依赖与编译命令配置
└── README.md
```

## 快速上手

### 1. 安装依赖
```bash
cd contracts
npm install
```

### 2. 编译合约
```bash
npx hardhat compile
```

### 3. 运行测试
```bash
npx hardhat test
```

### 4. 部署至 Sepolia 测试网
配置上级目录或本地 `.env` 中的 `WEB3_PROVIDER_URI` 与 `DEPLOYER_PRIVATE_KEY`，执行：
```bash
npm run deploy:sepolia
```

部署完成后，将生成的合约地址同步至：
1. `docs/contracts_spec.md`
2. `frontend/static/js/deployed_addresses.json`
3. `backend/.env`
