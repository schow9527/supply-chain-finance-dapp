# Demo Presentation (Member 5 — English Version)

- `scf-dapp-demo-en/`: source project of the 13-page English deck (kimi-slides `.pptd`). Page content and figures are based on real data from this repository (contract interfaces, Gas benchmarks, Sepolia deployment addresses). The final slide (page 13) includes the full team division-of-work table (Member / Role / Deliverables, Members 1–6). It can be opened in Kimi Work for further editing and re-exported to `.pptx`.
- The exported Chinese deck `scf-dapp-demo.pptx` lives in `../../designs/presentation/scf-dapp-demo/`; the English deck can be exported the same way from Kimi Work.

## Slide Structure (13 pages)

| Page | Content |
| :--- | :--- |
| 01 | Cover |
| 02 | Background & Problem → Product Goals |
| 03 | Solution Overview: demo storyline + five roles + key figures |
| 04 | System Architecture (four layers) |
| 05 | Smart Contract Design: 5 contracts, responsibilities & security baseline |
| 06 | Three Gates Against Duplicate Financing (core mechanism) |
| 07 | Contract Interaction Sequence Diagram |
| 08 | Business Flow: main path + four revertible branches |
| 09 | UI Design: 3 wireframes + interaction rules |
| 10 | Data Model & Back-End Responsibilities |
| 11 | Gas Optimization Results (real Foundry benchmark data) |
| 12 | Sepolia Deployment Addresses & Verification Conclusions |
| 13 | Summary & Division of Work |

> Figure sources: `../diagrams/` and `../wireframes/`; Gas data from `contracts/docs/gas/`; contract addresses from `contracts/deployments/11155111.json`.
