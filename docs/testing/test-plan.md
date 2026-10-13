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

### 2.1 Scope adjustment (2026-10-12)

After the main flow, maturity, duplicate-prevention, financing and access-control cases were executed, the remaining manual UI cases were prioritised against the **course brief** (role-based auth, MetaMask signing, ≥ 3 interacting contracts and ≥ 10 transaction types, REST API + persistence + error handling, responsive dashboard with transaction history / event log / visualisation, gas estimation, testing, cloud deployment). Cases not required by the brief, or already covered by another layer, are marked **⏭ Out of scope** in [test-cases.md](test-cases.md) with the covering evidence:

- **Contract unit tests (Foundry, Member 1)** — pause/resume, revoke, reject & resubmit, cancel financing, repay twice, split-holder redemption, frozen redemption.
- **Backend unit tests (pytest, Member 2)** — registration validation, file-type/size checks, auth 401/403, query scoping.
- **Frontend unit tests (Member 3)** — user-cancellation and revert-reason messages.
- **On-chain `eth_call` simulation** — [evidence/onchain-negative-checks.md](evidence/onchain-negative-checks.md) for permission-matrix and invalid-input cases at the contract layer.
- **Flows already executed on-chain** — repay/redeem (receivable #2), split transfer (#5).

Pausing the shared Sepolia deployment was deliberately not executed because it would disrupt other team members' work. User testing (L5) is optional: the brief accepts user testing **or** scenario-based evaluation, and the executed test cases constitute the scenario-based evaluation.

## 3. Test Levels

| Level | Method | Owner | Status |
|---|---|---|---|
| L1 Contract unit tests | Foundry `forge test` (52 tests incl. 1 fuzz test) | Written and run by Member 1; results cited | Cited from Member 1 (not re-run) |
| L2 Backend unit tests | `pytest` (195 passed; 2 integration tests skipped – require real PostgreSQL/S3) | Written by Member 2; re-run by YANG SHUYI | ✅ Re-run and passed on 2026-10-12 |
| L3 Frontend unit tests | `npm test` (Node built-in test runner, 16 tests) | Written by Member 3; re-run by YANG SHUYI | ✅ Re-run and passed on 2026-10-12 |
| L4 End-to-end functional tests | Manual execution of [test-cases.md](test-cases.md) on the live Render deployment, with screenshots and transaction hashes | YANG SHUYI | Pending |
| L5 User testing (optional) | Lightweight study (see §9.1): 2–3 participants complete the main flow from a task card on the tester's laptop, then fill in a 5-question questionnaire | Organised by YANG SHUYI | Pending |

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

Each wallet address can hold only one role, so several MetaMask accounts are needed. Every account needs Sepolia ETH for gas. **Correction (2026-10-12):** the initial estimate assumed the network base fee (≈ 0.001 gwei), but MetaMask actually paid ≈ 1.5 gwei (priority fee), i.e. ~0.0002–0.0009 ETH per business transaction. The initial 0.004 ETH per account was not enough for the supplier (S1 ran out after ~6 transactions; topped up with 0.0035 ETH from X). Plan: obtain additional Sepolia ETH into `ADM2`/Main and distribute, and choose the "Low" fee option in MetaMask to reduce cost.

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

On-chain state is cumulative – later test cases depend on invoices and receivables created by earlier ones – so cases must be executed in order.

Some cases need a due date that has **actually passed**: marking overdue (F-21), and blocking confirmation / transfer after maturity (F-08, F-12). The frontend date picker only allows dates from tomorrow onward, but the contract only requires `dueDate > block.timestamp`. To finish in a single day, the **maturity seed invoices** `TEST-OD-001/002/003` are submitted from the browser developer console via the page's own `contractClient` (same MetaMask flow and transaction modal) with a due date **30 minutes** ahead. They are registered first; the rest of the main flow runs while they mature. These seed invoices have no PDF in the backend, which is expected and does not affect the cases they serve.

| Phase | Activities | Depends on |
|---|---|---|
| D0 Setup ✅ | 8 accounts created and funded with Sepolia ETH; CE/S1/S2/F1/F2 approved via registration flow; AUDITOR granted to AU and admin to ADM2 by ADM (2026-10-12) | Member 1 |
| Pre-test ✅ | BUG-01 – BUG-03 found during setup, fixed and retested on the live site (see [defect-log.md](defect-log.md)) | Member 3 |
| S1 Funding | F1, F2, CE claim mUSD from the faucet (TC-F22-01) | D0 |
| S2 Maturity seeds | Submit `TEST-OD-001/002/003` (due +30 min) via console; confirm OD-001 and OD-003; finance OD-001 to F1; run TC-F21-01 (mark before due) | S1 |
| S3 Main flow | TC-F01 – TC-F20, TC-F22 – TC-F26 while seeds mature | S1 |
| S4 After maturity | TC-F21-02 – 04, TC-F12-05, TC-F08-04 | S2 + 30 min |
| S5 Negative & permissions | Negative cases, permission matrix (§6 of test cases); pause cases (pausing affects the whole team – **notify the group chat first** and unpause immediately afterwards) | S3 |
| S6 Non-functional | Mobile responsive checks, page-load timing, sync latency | — |
| S7 User testing | L5, ~10 min per participant (see §9.1) | Main flow fully passing |

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

### 9.1 User Testing Protocol (lightweight)

| Item | Decision |
|---|---|
| Participants | 2–3 people: Members 4 and 5 (non-developers, reported as internal pilot testers) plus at least one person outside the team |
| Setup | Tester's own laptop with the prepared accounts (§5) already connected – participants do not install MetaMask |
| Task | One task card covering the main flow: upload invoice → confirm → request financing → quote → accept → repay → redeem, switching accounts as instructed |
| Duration | ~10 minutes per participant |
| Observation | Tester records, without helping, whether each step was completed unaided and where the participant hesitated |
| Questionnaire | 5 questions on a 1–5 scale (ease of use, clarity of status/feedback, clarity of error messages, trust in the result, overall satisfaction) |
| Limitation | Small, partly internal sample; results are indicative only and this is stated in the report |

## 10. Risks and Dependencies

| Risk | Impact | Mitigation |
|---|---|---|
| Admin wallet is held only by Member 1 | Role grants and pause tests depend on Member 1 | In D0, Member 1 grants `DEFAULT_ADMIN_ROLE` to `ADM2` (the contract allows multiple admins), so later admin test cases run without Member 1 |
| Sepolia faucet limits and block times | Slower testing; inflated time-to-financing figures | Obtain ETH early; state testnet block time in the metric report |
| Backend branch not yet merged into `main` | Version in the report differs from the repository's main branch | After merging, re-label the build under test with the merge commit |
| Render runs on paid instances | Live site goes offline if billing stops, interrupting testing and recording | Confirm billing covers the period through the final demo |
| Pause tests affect the whole team | Teammates' transactions fail mid-test | Notify the group chat; unpause immediately |
| On-chain data cannot be deleted | Test data appears in the demo environment | Prefix test invoices with `TEST-` and demo invoices with `DEMO-` |
