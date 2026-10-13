# docs/designs · 成员 5：系统设计与演示交付物

> 本目录为成员 5（设计与展示）的全部交付物，对应分工：
> **前期 UI 线框图（供成员 3 参考）、报告要求的 5 类图、演示 PPT、用户手册。**

## 目录结构

```
docs/designs/
├── README.md                  ← 本文件
├── diagrams/                  ← 报告要求的 5 类图（mermaid 源码 + PNG 导出）
│   ├── 01-system-architecture.mmd / .png    系统架构图（四层架构）
│   ├── 02-contract-interaction.mmd / .png   合约交互图（链上时序）
│   ├── 03-data-model.mmd / .png             数据模型图（ER，7 张表）
│   ├── 04-business-flow.mmd / .png          业务流程图（含异常分支）
│   ├── 05-ui-navigation.mmd / .png          界面图（19 页面导航结构）
│   └── README.md                            图集索引（内嵌可渲染 mermaid 源码）
├── wireframes/                ← 19 张页面线框图（与 PRD §8 页面清单一一对应）
│   └── README.md                            索引 + 给前端的布局/交互规范
├── presentation/
│   └── scf-dapp-demo/         ← 演示 PPT 源工程（kimi-slides .pptd，13 页）
└── user-manual/
    └── 用户手册.md             ← 五角色的完整操作手册 + 故障排查
```

## 使用说明

1. **图**：`.mmd` 为 mermaid 源码，GitHub 上可直接渲染、可改；`.png` 为导出图，可直接插入技术报告。同目录 `README.md` 有总览。
2. **线框图**：供成员 3 前端实现作页面参考，红色批注对应 PRD 验收编号（F-xx）。
3. **PPT**：`.pptd` 工程在 Kimi Work 中打开即可编辑，并从编辑器导出 `.pptx`。
4. **用户手册**：面向五类角色的最终用户文档，随系统一起交付。

## 与其他成员交付物的衔接

| 成员 | 交付物 | 与本目录的关系 |
| :--- | :--- | :--- |
| 成员 1 | `contracts/` 合约 + ABI + Gas 数据 | 图 02/05 与 PPT 第 11 页引用其接口与基准数据 |
| 成员 2 | `backend/` + Render 部署 | 图 01/03 与 PPT 第 10/12 页引用其 API 与部署 |
| 成员 3 | `frontend/` 页面实现 | 线框图与界面图（图 05）是其页面参考 |
| 成员 4 | `docs/reports/` 技术报告 | 本目录 5 类图与 PPT 供其直接插入报告 |
| 成员 6 | `docs/testing/` 测试报告与视频 | PPT 第 12 页验证结论引用其测试结果 |
