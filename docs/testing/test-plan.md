# Test Plan

> **Owner**: YANG SHUYI (Member 6 – Testing, Validation & Demo Video)
> **Version**: v0.1 (2026-10-12)
> **Build under test**: `feature/backend-member2` @ `23a68da` (all of `main` + backend)
> **Related documents**: [Test Cases](test-cases.md) · [PRD](../PRD.md) · [Contract Interface](../../contracts/docs/interface.md) · [Backend API](../api.md)

---

## 1. Objectives

1. Verify that all **26 functional requirements (F-01 – F-26)** in PRD §4 meet their acceptance criteria.
2. Verify that each of the **20 on-chain transaction types** can be executed successfully on Sepolia by the authorised role, and is rejected for every other role.
3. Verify the **permission matrix** in PRD §2: access control is enforced in both the smart contracts and the backend, not merely by hiding buttons in the frontend.
4. Verify **error handling**: the UI shows a clear message when the user rejects a signature, has insufficient balance, is on the wrong network, the contract reverts, or the system is paused.
5. Measure the **five success metrics** in PRD §9 and hand the data to Member 4 for the impact-evaluation chapter of the report.

## 2. Scope

| In scope | Out of scope |
|---|---|
| All 19 pages of the live Render deployment | Ethereum mainnet |
| The 5 contracts deployed on Sepolia | Real fiat on/off-ramp, real KYC, tax-authority invoice verification |
| Backend REST API, event synchronisation, PDF storage | Render platform SLA |
| Desktop Chrome + MetaMask; mobile browsers (responsive layout only) | Signing inside mobile wallet apps (MetaMask Mobile) |

## 3. Test Levels

| Level | Method | Owner | Status |
|---|---|---|---|
| L1 Contract unit tests | Foundry `forge test` (52 tests incl. 1 fuzz test) | Written by Member 1; re-run and recorded by YANG SHUYI | Pending (Foundry not yet installed) |
| L2 Backend unit tests | `pytest` (195 passed; 2 integration tests skipped – require real PostgreSQL/S3) | Written by Member 2; re-run by YANG SHUYI | ✅ Re-run and passed on 2026-10-12 |
| L3 Frontend unit tests | `npm test` (Node built-in test runner, 16 tests) | Written by Member 3; re-run by YANG SHUYI | ✅ Re-run and passed on 2026-10-12 |
| L4 End-to-end functional tests | Manual execution of [test-cases.md](test-cases.md) on the live Render deployment, with screenshots and transaction hashes | YANG SHUYI | Pending |
| L5 User testing | ≥ 5 participants outside the team complete the full flow from task cards and fill in a questionnaire | Organised by YANG SHUYI | Pending |

> Note on re-running L2: on Windows, if the repository sits in a deep directory, the storage tests fail with HTTP 503 because the path exceeds 260 characters. Use a short temp directory, e.g. `pytest --basetemp=C:/pt`. This is an environment issue, not a code defect.

## 4. Test Environment

| Item | Value |
|---|---|
| Live URL | <https://supply-chain-finance-dapp-nkkr.onrender.com/> |
| Health check | <https://supply-chain-finance-dapp-nkkr.onrender.com/api/health/ready> |
| Network | Sepolia (Chain ID 11155111) |
| Browser | Latest Chrome + MetaMask extension |
| Block explorer | <https://sepolia.etherscan.io/> |
| Stablecoin | mUSD, 6 decimals; `faucet()` mints 100,000 mUSD per call |

### Contract addresses ([contracts/deployments/11155111.json](../../contracts/deployments/11155111.json))

| Contract | Address |
|---|---|
| RoleManager | `0x82f86a2B31C424b4833b5BAb82464eB7f69B6a2E` |
| InvoiceRegistry | `0x39605C1D4FCE3D85DC14f7f283899b984dd1eD7a` |
| ReceivableToken | `0x3c9EcDdf7e788F7B8e04D4177d04B3c291E0368f` |
| FinancingPool | `0x2bb0A6e688C331248fe8575121F799B5286985c6` |
| MockStablecoin | `0xE3C713Db876c97600141Ba34C7Cb68898CF1E04F` |

## 5. Test Accounts

Each wallet address can hold only one role, so several MetaMask accounts are needed. Every account needs Sepolia ETH for gas. At the gas price observed on 2026-10-12 (≈ 0.001 gwei) a `submitInvoice` costs < 0.000001 ETH, so 0.004 ETH per account is ample; CE funded each of the other accounts with 0.004 ETH on 2026-10-12.

| Alias | Role | Purpose | Address | Notes |
|---|---|---|---|---|
| `ADM` | Admin | Grant/revoke roles, pause/unpause | `0x0ced068d2f30d72ca4c8d41d9619a2183d06834f` | **Deployer wallet, held by Member 1** – requires Member 1's assistance |
| `ADM2` | Admin (tester) | Approve registrations, revoke roles, pause/unpause during testing | `0x877c15eB8449DF65323a2e49902d889052a9Df42` | Tester's own admin account (MetaMask name `Main`), to be granted `DEFAULT_ADMIN_ROLE` by `ADM`; revoke tests are run only against `X` |
| `CE` | Core Enterprise | Confirm/reject invoices, repay at maturity | `0x3d06C8284962154159c2F7eC6F8789A75dd7A892` | Needs mUSD for repayment |
| `S1` | Supplier | Upload invoices, split/transfer, request financing | `0xC5192Be82Ef411Ca3ec3B8Ea03EA260C770795F2` | |
| `S2` | Supplier (tier 2) | Receive split receivables | `0xE128d23F32B6f576054f0F9D7ec0B6Ef2EAa282e` | |
| `F1` | Funder | Quote, fund, mark overdue, redeem | `0xE21E58104Aa80450bA60C6A535129E7d9F8b9916` | Needs mUSD for funding |
| `F2` | Funder | Second competing quote on the same request (F-16) | `0x9c781511c1b3843837da8be745e0CCCeCd04661E` | Needs mUSD |
| `AU` | Auditor | Freeze/unfreeze, global view | `0x2aAEe8c8A554c988872179d6391A29f6f18d37ce` | |
| `X` | Unauthorised | Access-control tests, role revocation, registration flow | `0x0B1A4a58beAAF4C990C058158716D9867f053D55` | No role, or role revoked after use |

## 6. Schedule

On-chain state is cumulative – later test cases depend on invoices and receivables created by earlier ones – so cases must be executed in order. Two groups of cases **cannot run until the next day**:

- The contract requires the due date to be in the future, and the frontend date picker's earliest option is tomorrow.
- Marking overdue (F-21) and blocking transfers/confirmation after maturity (F-12, F-08) require the due date to have actually passed.

Therefore, **on Day 1 an invoice due "tomorrow" must be registered, confirmed and financed to F1**, so it can be used for the overdue tests on Day 2.

| Phase | Activities | Depends on |
|---|---|---|
| D0 Setup | Create 8 accounts, obtain Sepolia ETH, fill in the account table; ask ADM to grant roles to CE/S1/S2/F1/F2/AU (or use the registration/approval flow, which also covers F-02/F-03) | Member 1 |
| D1 morning | Register overdue seed invoice `TEST-OD-001` (due tomorrow) → confirm → request financing → fund to F1 | D0 |
| D1 | Main flow: TC-F01 – TC-F20, TC-F22 – TC-F26 | D0 |
| D1 | Negative and access-control cases; pause cases (pausing affects the whole team – **notify the group chat first** and unpause immediately afterwards) | D0 |
| D2 | Maturity-dependent cases: TC-F21, TC-F12-05, TC-F08-04 | D1 seed invoice |
| D2 | Mobile responsive checks; success-metric summary | — |
| D3+ | User testing (L5) | Main flow fully passing |

## 7. Defect Management

- Report defects as GitHub Issues titled `[Bug][F-xx] one-line description`. The body must include: steps to reproduce, expected result, actual result, screenshot, transaction hash, and the role of the current account.
- Severity: **P0** main flow blocked / funds incorrect; **P1** a feature fails its acceptance criteria; **P2** wording, display or styling issues.
- Assign to the module owner: contracts → Member 1, backend/deployment → Member 2, frontend → Member 3.
- Regression: after a fix, re-run the case and update its result in test-cases.md.

## 8. Exit Criteria

- Zero open P0 defects; all P1 defects fixed or justified in the report.
- All positive cases for the 26 features pass; ≥ 95 % of negative cases pass.
- Each of the 20 on-chain transaction types has at least one successful Sepolia transaction hash as evidence.
- L1 – L3 automated tests all pass.

## 9. Success Metric Measurement (PRD §9)

| Metric | Measurement method | Target | Data source |
|---|---|---|---|
| Time to financing | Block time of `acceptQuote` − block time of `confirmInvoice`; average of 5 runs. Baseline for the traditional process to be supplied by Member 4 from the literature | ≤ 10 min | Etherscan timestamps |
| Duplicate-financing interception rate | Construct duplicate scenarios – resubmitting the same invoice (on-chain and via backend), resubmitting after confirmation, re-financing an amount already in escrow, accepting a second quote on a funded request – and compute intercepted / constructed | 100 % | TC-F07, TC-F15, TC-F17 |
| Cost per transaction | Gas used per transaction type before vs. after optimisation (already measured by Member 1, see [gas-optimization.md](../../contracts/docs/gas-optimization.md)); spot-check against real Sepolia "Gas Used" values | After < before (main flow −15.3 %) | Foundry report + Etherscan |
| Task completion rate | Participants who complete the full flow without assistance / total participants | ≥ 80 % | L5 observation sheet |
| User satisfaction | Mean score of a 1–5 post-test questionnaire | ≥ 4.0 | L5 questionnaire |

## 10. Risks and Dependencies

| Risk | Impact | Mitigation |
|---|---|---|
| Admin wallet is held only by Member 1 | Role grants and pause tests depend on Member 1 | In D0, Member 1 grants `DEFAULT_ADMIN_ROLE` to `ADM2` (the contract allows multiple admins), so later admin test cases run without Member 1 |
| Sepolia faucet limits and block times | Slower testing; inflated time-to-financing figures | Obtain ETH early; state testnet block time in the metric report |
| Backend branch not yet merged into `main` | Version in the report differs from the repository's main branch | After merging, re-label the build under test with the merge commit |
| Render runs on paid instances | Live site goes offline if billing stops, interrupting testing and recording | Confirm billing covers the period through the final demo |
| Pause tests affect the whole team | Teammates' transactions fail mid-test | Notify the group chat; unpause immediately |
| On-chain data cannot be deleted | Test data appears in the demo environment | Prefix test invoices with `TEST-` and demo invoices with `DEMO-` |
