# 小组作业分工与协作规范 (SC6113)

> **项目名称**：基于智能合约的去中心化供应链金融 DApp (Supply Chain Finance DApp)  
> **PRD 来源**：PRD v1.0 (@YANG SHUYI)  

---

## 一、团队成员分工矩阵 (6 人分工)

| 角色序号 | 职责范畴 | 主要交付物 | 涉及代码/文档路径 |
| :---: | :--- | :--- | :--- |
| **成员 1** | **智能合约开发** | 5 个 Solidity 合约、Foundry 自动化单元测试、Sepolia 测试网部署、导出 ABI | `contracts/` |
| **成员 2** | **后端开发与部署** | Python Flask REST API、Web3.py 链上事件监听器、Render 部署、`docs/api.md` | `backend/` |
| **成员 3** | **前端开发与 Web3** | 响应式 Web 页面 (19 个视图)、MetaMask/Ethers.js 交互集成、Gas 预估与状态提示 | `frontend/` |
| **成员 4** | **行业研究与技术报告** | 供应链金融背景调研、技术报告 (10~15 页)、成员贡献汇总 | `docs/reports/` |
| **成员 5** | **系统架构与演示设计** | 5 种 UML 架构与时序图、演示 PPT、产品使用手册 | `docs/designs/` |
| **成员 6** | **测试验证与视频制作** | 全功能测试用例、测试报告、演示视频录制 (YouTube) 或现场演示准备 | `docs/testing/` |
| **全员** | **代码协同** | GitHub 仓库日常提交、遵循分支开发与 Pull Request 规范 | 全仓库 |

---

## 二、Git 协作与工作流规范

### 1. 分支策略
- `main`：生产稳定分支，只有经过组内 Review 且测试通过的代码才能合入。
- `develop`：日常联调主分支。
- 功能分支（按职责领用）：
  - `feature/contracts-member1`
  - `feature/backend-member2`
  - `feature/frontend-member3`
  - `feature/docs-member456`

### 2. Commit 提交信息格式
统一格式为：`[模块] 简明修改说明`
- `[Contract] 完成 FinancingPool 原子放款逻辑`
- `[Backend] 增加发票文件哈希计算与上传接口`
- `[Frontend] 实现供应商发票上传与 MetaMask 签名`
- `[Docs] 更新 API 设计文档与待办清单`

---

## 三、开发里程碑规划

1. **第一阶段（启动与环境搭建）**：
   - 确定测试网络（建议 Sepolia）；
   - 跑通 Foundry 编译测试环境与 Flask 本地服务。
2. **第二阶段（核心功能实现）**：
   - 成员 1 完成 5 个合约编写与本地测试，导出 ABI；
   - 成员 2 实现数据库模型与核心 API；
   - 成员 3 搭建页面骨架与 MetaMask 钱包连接基础。
3. **第三阶段（联调与测试网部署）**：
   - 成员 1 部署合约至 Sepolia 测试网，更新各端配置地址；
   - 成员 2 配置 Web3 事件同步并部署至 Render；
   - 成员 3 完成真实测试网全流程交互联动。
4. **第四阶段（验收、报告与视频录制）**：
   - 成员 6 执行 26 项功能测试并产出测试报告；
   - 成员 4、5 定稿最终技术报告与 PPT；
   - 全员录制演示视频上传 YouTube。
