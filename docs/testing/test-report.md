# Test Report — Supply Chain Finance DApp

> **Author**: YANG SHUYI (Member 6 – Testing, Validation & Demo Video)
> **Test date**: 2026-10-12 (single test day, Sepolia testnet)
> **Build tested**: `feature/backend-member2` — final retest on `8c0fc51` (includes all fixes made during testing)
> **Live system**: <https://supply-chain-finance-dapp-nkkr.onrender.com/>
> **Demo video**: <https://youtu.be/GeVo2iIh7co>
> **Detailed records**: [test plan](test-plan.md) · [test cases & results](test-cases.md) · [defect log](defect-log.md) · [on-chain negative checks](evidence/onchain-negative-checks.md) · [screenshots](screenshots/)

---

## 1. Summary

The deployed DApp was tested end-to-end on the live Render deployment against the five contracts on Sepolia, using eight dedicated MetaMask test accounts (core enterprise, two suppliers, two funders, auditor, an unauthorised account and a tester admin).

| Item | Result |
|---|---|
| Test cases | **128** in total — **79 pass**, **8 partially verified**, **0 failing**, 41 out of scope (each with covering evidence) |
| Main business flow | Upload invoice → confirm → split → request financing → competing quotes → accept (atomic disbursement) → overdue → late repayment → redemption: **all executed successfully on-chain** |
| On-chain transaction types | **15 types** executed successfully on Sepolia (37 transactions); course minimum is 10 |
| Access control | **35 / 35** unauthorised or invalid calls rejected by the contracts (simulated from the real accounts); 3 / 3 authorised control calls succeed |
| Duplicate-financing interception | **7 / 7 (100 %)** duplicate scenarios blocked |
| Time to financing | **7 min 24 s** from invoice confirmation to cash in the supplier's wallet (target ≤ 10 min) |
| Defects found | **12 defects** (1 × P0, 5 × P1, 6 × P2) + 2 known environment issues. **10 fixed and retested on the live system** the same day; 1 won't fix, 1 deferred (both minor, with workarounds) |
| Automated tests | Backend 195 passed (2 integration tests skipped); frontend 17 passed; contract tests (52) reported by Member 1 |
| Non-functional | All 7 checks pass (page response ≤ 0.11 s, event sync ≤ 1 block, responsive layout, no private keys in backend, no information leakage) |

**Conclusion**: after the fixes made during testing, every functional requirement in scope meets its acceptance criteria on the live system. The remaining open items are two minor defects with documented workarounds and two wallet-side environment issues (§6).

## 2. Approach

| Level | What was done |
|---|---|
| Automated unit tests | Re-ran backend (`pytest`) and frontend (`npm test`) suites; contract suite (Foundry, 52 tests incl. fuzzing) cited from Member 1 |
| End-to-end functional tests | Executed the test cases manually in Chrome + MetaMask on the live site; every on-chain step verified independently by querying Sepolia (balances, states, events) |
| Contract-layer negative tests | `eth_call` simulation of unauthorised / invalid calls **from the real test accounts** against the deployed contracts; revert reasons decoded from the contract ABIs ([evidence](evidence/onchain-negative-checks.md), [script](scripts/onchain_sim.py)) |
| Maturity-dependent tests | Three seed invoices with a 1-hour due date were registered from the browser console (the UI only allows dates from tomorrow), so overdue / matured cases could be completed on the same day |
| Non-functional checks | HTTP timing, health endpoint, error format, code inspection |

**Scope adjustment.** Cases not required by the course brief, or already covered by another layer, were marked out of scope with the covering evidence (Foundry unit tests, backend unit tests, flows already executed on-chain) — see [test-plan.md §2.1](test-plan.md). Pausing the shared deployment was deliberately not executed to avoid disrupting other team members; it is covered by `test_PauseBlocksWritesButNotReads`. User testing (L5) was not conducted; the course brief accepts scenario-based evaluation, which the executed test cases provide.

## 3. Results by module

| Module | Cases | ✅ Pass | ◐ Partial | ❌ Fail | ⏭ Out of scope |
|---|---:|---:|---:|---:|---:|
| Accounts & permissions (F-01 – F-05) | 27 | 9 | 0 | 0 | 18 |
| Invoices (F-06 – F-10) | 22 | 11 | 5 | 0 | 6 |
| Receivables (F-11 – F-14) | 16 | 13 | 1 | 0 | 2 |
| Financing & repayment (F-15 – F-22) | 30 | 21 | 0 | 0 | 9 |
| Dashboard & audit (F-23 – F-26) | 14 | 10 | 0 | 0 | 4 |
| Non-functional | 7 | 7 | 0 | 0 | 0 |
| Permission matrix (contract + backend) | 12 | 8 | 2 | 0 | 2 |
| **Total** | **128** | **79** | **8** | **0** | **41** |

"Partial" means the contract (or API) layer was verified but the corresponding UI check was not executed (e.g. front-end form validation for a zero amount). Per-case results and evidence are in [test-cases.md](test-cases.md).

### Key scenarios verified

| Scenario | Evidence |
|---|---|
| Invoice registered with the PDF's SHA-256 on-chain; the same invoice cannot be registered again — even when the backend is bypassed and the contract is called directly (`InvoiceAlreadyExists`) | TC-F06-01, TC-F07-01/02/03 |
| Core enterprise confirmation mints an equal ERC-1155 receivable to the supplier | TC-F08-01 |
| Receivable split: 4,000 of 10,000 transferred to a tier-2 supplier; transfers to non-suppliers, above balance, or after maturity are rejected | TC-F12-01/02/03/05 |
| Auditor freeze blocks transfer and financing in both the UI and the contract; unfreeze restores it | TC-F13-01/02/05 |
| Financing request escrows the receivable; two funders quote (3 % and 2.5 %); a quote is withdrawn and refunded; acceptance moves the receivable to the funder and **5,820 mUSD to the supplier in one transaction** | TC-F15-01, TC-F16-01/02/06, TC-F17-01 |
| Mark-overdue rejected before maturity, accepted after; core enterprise repays late; funder redeems 1:1 (profit 90 mUSD on 3,000 at 3 %) | TC-F21-01/02/04 |
| Role dashboards, transaction history with Etherscan links, filterable event log, receivable timeline, phone-width layout | TC-F23 – TC-F25, TC-F14-01 |

## 4. Success metrics (PRD §9)

| Metric | Target | Measured | Status |
|---|---|---|---|
| Time to financing | ≤ 10 min | **7 min 24 s** — receivable #2: `confirmInvoice` at 16:22:48 → `acceptQuote` at 16:30:12 (SGT, block timestamps), including switching between three wallets | ✅ |
| Duplicate-financing interception rate | 100 % | **7 / 7 = 100 %** — duplicate invoice via UI (backend 409), duplicate after confirmation and via direct contract call (`InvoiceAlreadyExists` ×2), re-financing an escrowed amount (`ERC1155InsufficientBalance`), accepting a second / withdrawn quote on a funded request (`RequestNotOpen` ×2), accepting a withdrawn quote while open (`QuoteNotActive`) | ✅ |
| Cost per transaction | Optimised < before | Main flow −15.3 % in Member 1's Foundry benchmark (same compiler settings before/after). Observed Sepolia gas is reported in §5.2 | ✅ (benchmark) |
| Task completion rate | ≥ 80 % | Not measured — user testing not conducted | — |
| User satisfaction | ≥ 4 / 5 | Not measured — user testing not conducted | — |

A second financing run (receivable #5) took longer in wall-clock time because testing was paused between confirmation and financing to fix BUG-10; it is not representative and is excluded. The comparison with the traditional factoring process (days to weeks) is provided in the technical report by Member 4.

## 5. Blockchain integration

### 5.1 Transaction coverage

15 of the 20 transaction types were executed successfully on Sepolia during testing; the remaining five (`revokeRole`, `pause`, `unpause`, `rejectInvoice`, `cancelRequest`) are covered by Foundry unit tests. Full list with Etherscan links: [test-cases.md §7](test-cases.md).

### 5.2 Observed gas vs. Foundry benchmark

| Transaction | Runs | On-chain gas used | Foundry benchmark (after optimisation) | Ratio |
|---|---:|---:|---:|---:|
| `submitInvoice` | 4 | 597,554 – 597,602 | 173,254 | 3.45× |
| `confirmInvoice` | 3 | 391,491 | 124,931 | 3.13× |
| `requestFinancing` | 2 | 395,023 – 395,035 | 145,491 | 2.72× |
| `grantRole` | 2 | 246,225 – 354,585 | 96,583 | 2.55× |
| `transferReceivable` | 1 | 164,760 | 74,640 | 2.21× |
| `markOverdue` | 1 | 167,051 | 76,931 | 2.17× |
| `repay` | 1 | 180,176 | 83,586 | 2.16× |
| `submitQuote` | 3 | 309,647 – 407,579 | 152,198 | 2.03× |
| `acceptQuote` | 2 | 222,831 – 320,751 | 131,343 | 1.70× |
| `withdrawQuote` | 1 | 71,122 | 49,922 | 1.42× |
| `redeem` | 1 | 76,595 | 64,043 | 1.20× |
| `freeze` | 1 | 37,707 | 35,915 | 1.05× |
| `unfreeze` | 1 | 37,677 | 35,909 | 1.05× |
| `faucet` | 5 | 41,975 – 139,895 | 50,675 | 0.83 – 2.76× |
| `approve` (mUSD) | 4 | 128,251 – 128,275 | — | — |

Transactions that only modify existing storage (`freeze`, `unfreeze`) match the benchmark within ~5 %, while transactions that create new storage slots cost 2–3.5× more on Sepolia. The faucet isolates the effect: the first claim by an account (new balance slot) used 139,895 gas, a repeat claim 41,975. This indicates that the Sepolia gas schedule prices new state far higher than the local EVM version used for the benchmark. It does not affect correctness or the before/after comparison (measured under identical settings), but **the benchmark should be re-run with the EVM version matching Sepolia** before quoting absolute costs. At the effective gas price paid during testing (1.0–1.5 gwei), the most expensive transaction (`submitInvoice`) cost about 0.0009 SepoliaETH.

## 6. Defects

| Severity | Found | Closed (fixed & retested) | Won't fix / deferred |
|---|---:|---:|---:|
| P0 | 1 | 1 | 0 |
| P1 | 5 | 4 | 1 (BUG-07) |
| P2 | 6 | 5 | 1 (BUG-04) |
| **Total** | **12** | **10** | **2** |

Most significant defects (all fixed and retested on the live system):

- **BUG-10 (P0)** — the "Apply Financing" button called a non-existent function, so suppliers could not request financing from the UI at all. A scan of all templates found no other such call.
- **BUG-05 (P1)** — after switching MetaMask accounts, transactions were still signed by the previously connected account (three faucet claims intended for F2 and CE all came from F1). Fixed by reloading the page on account change.
- **BUG-12 (P1)** — several dashboard KPIs were static placeholders (e.g. funder "total disbursed" showed 0 instead of 8,730) and no dashboard had a chart. KPIs are now computed from real data and every role dashboard has a chart (course requirement: data visualisation).
- **BUG-08 (P1)** — no way to view the invoice PDF in the UI; core enterprises confirmed invoices without seeing the document.
- **BUG-09 (P1)** — the auditor page always showed "Unfrozen" after a reload, so a frozen receivable could not be unfrozen from the UI.

Open items:

| ID | Issue | Workaround |
|---|---|---|
| BUG-04 (P2, won't fix) | Several pending sign-in requests; signing a stale one reports "another wallet" | Confirm only one sign-in request |
| BUG-07 (P1, deferred) | Cancelling the wallet transaction during invoice upload leaves a backend draft that blocks that invoice number | Use a new invoice number |
| KI-01 (environment) | MetaMask labels the `onrender.com` site "Malicious" | "Continue at your own risk"; a custom domain would be needed in production |
| KI-02 (environment) | MetaMask's pre-ticked "Added protection" upgrades the account to a smart account and the transaction reverts with an unreadable error | Untick "Added protection"; turn off "Smart Transactions" and "Smart account requests from dapps" |

Minor observations (not logged as defects): transaction-history labels are derived from events (e.g. `acceptQuote` shown as TRANSFER); the receivable timeline shows the mint twice; payables are sorted latest-due first; the core-enterprise chart uses green for "Overdue"; the auditor overdue-rate subtitle is static; there is no UI to withdraw a quote (not a PRD requirement); on-chain gas is higher than the benchmark (§5.2).

## 7. Non-functional results

| Requirement | Result |
|---|---|
| Query pages load ≤ 3 s | Server response 0.07 – 0.11 s for all 11 main pages |
| Events synced ≤ 30 s after confirmation | Sync lag 0 – 1 block (≈ 12 s) throughout testing |
| Responsive on phone and desktop | Layout stacks correctly at phone width, no horizontal scrolling |
| Backend stores no private keys | Confirmed by code inspection; all writes are signed in MetaMask |
| Unified error format, no leakage | `{"error":{code,message,details}}`; health endpoint exposes no URLs or credentials |
| Availability on Render | Reachable and `ready` at every check during the test day |

## 8. Limitations

- Testing ran on a single day on a public testnet with one core enterprise; multi-enterprise and high-volume scenarios were not exercised.
- Overdue scenarios used console-seeded invoices with a 1-hour due date; these have no PDF in the backend.
- User testing (task completion, satisfaction) was not conducted.
- Some negative cases were verified with `eth_call` simulation rather than sent transactions; simulation reflects exactly what the contracts would do at that block but produces no on-chain record.

## 9. Recommendations

1. Fix BUG-07 in the backend: allow a `FILE_UPLOADED` draft from the same supplier to be replaced.
2. Re-run the Foundry gas benchmark with the EVM version used by Sepolia so reported costs match on-chain values.
3. Before the demo and any user testing: untick MetaMask "Added protection" on every account, and brief viewers on the MetaMask site warning (KI-01).
4. Optional polish: event-independent action names in transaction history, de-duplicated mint entry in the timeline, payables sorted soonest-due first, a "withdraw quote" button for funders.
