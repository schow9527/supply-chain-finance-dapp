# Demo Video Script (10 min)

> **Owner**: YANG SHUYI (Member 6)
> **Format**: screen recording of the live DApp + a few slides, English narration, uploaded to YouTube
> **Live system**: <https://supply-chain-finance-dapp-nkkr.onrender.com/> (Sepolia)

## Timeline

| # | Time | Part | On screen |
|---|---|---|---|
| 1 | 0:00 – 0:45 | Problem | Slide |
| 2 | 0:45 – 1:45 | Solution & architecture | Slide (Member 5's architecture / contract diagrams) |
| 3 | 1:45 – 7:45 | Live demo (main flow) | Browser + MetaMask |
| 4 | 7:45 – 9:00 | Testing & results | Slide (from the test report) |
| 5 | 9:00 – 10:00 | Deployment, limitations, conclusion | Slide |

Waiting for block confirmations (~12 s each) is **cut out in editing**, so the demo part fits in 6 minutes.

---

## Part 1 · Problem (0:00 – 0:45) — slide

> "Small suppliers often wait months to be paid by large buyers, and banks find it hard to lend against their invoices. Two problems make it worse: the same invoice can be financed at several banks, because banks don't share data, and the large buyer's strong credit does not reach second-tier suppliers. Our project, a supply-chain finance DApp, tackles these three problems on Ethereum."

## Part 2 · Solution & architecture (0:45 – 1:45) — slide

> "A supplier registers an invoice. The PDF stays off-chain, only its hash goes on-chain, and the contract rejects any duplicate. When the core enterprise confirms the invoice, it becomes an ERC-1155 receivable token that can be split, transferred to tier-2 suppliers, and financed by banks.
> The system has five roles — admin, supplier, core enterprise, funder and auditor — and four interacting contracts plus a test stablecoin: RoleManager, InvoiceRegistry, ReceivableToken and FinancingPool. The frontend talks to the contracts through MetaMask; a Flask backend stores the PDFs and indexes contract events into PostgreSQL; everything runs on Render and Sepolia."

---

## Part 3 · Live demo (1:45 – 7:45)

Numbers used: invoice **`DEMO-001`**, **10,000 mUSD**, due **one month later**; split **3,000** to S2; finance the remaining **7,000** at **3 %** (supplier receives **6,790**).

Navigation: Home (click **SCF DApp** top-left or 🏠 Back to Home) → *Role Dashboards* card for the role → left-hand menu.

Every transaction: **untick "Added protection"** → Review alert → Confirm. Switching MetaMask account reloads the page automatically — sign in when asked.

| Step | Account | Do | Say |
|---|---|---|---|
| 3.1 Roles (15 s) | ADM2 (Main) | Home → ⚙️ Platform Admin Dashboard → ⚙️ System Control & Roles: show the grant-role form, revoke form and emergency-pause button (do not click) | "Roles are granted on-chain by the admin, who can also pause the whole system in an emergency. Every page and every contract call checks the caller's role in the RoleManager contract." |
| 3.2 Upload (40 s) | S1 | Home → 🏭 Supplier Dashboard → 📤 Upload Invoice: `DEMO-001`, buyer CE `0x3d06C8284962154159c2F7eC6F8789A75dd7A892`, 10000, date +1 month, PDF → Submit. Point at the SHA-256 hash and the **gas estimate** stage, then Confirm | "The supplier uploads the invoice. The browser hashes the PDF; only the hash and the invoice data go on-chain. Before signing, the page shows the estimated gas." |
| 3.3 Duplicate blocked (20 s) | S1 | 📤 Upload Invoice again with the exact same data → "This invoice is already uploaded." | "If the same invoice is submitted again it is rejected — and even if someone bypasses our website and calls the contract directly, the contract itself rejects the duplicate." |
| 3.4 Confirm (40 s) | CE | Home → 🏢 Core Enterprise Dashboard → 🔍 Pending Invoices: click **View PDF**, then **Confirm & Mint** | "The core enterprise opens the original PDF and confirms the invoice. This mints a 10,000 receivable token to the supplier — the buyer's credit is now a transferable asset." |
| 3.5 Split (30 s) | S1 | 💎 Receivables & Transfer → DEMO-001 token → **Split & Transfer** 3,000 to S2 `0xE128d23F32B6f576054f0F9D7ec0B6Ef2EAa282e` | "The supplier pays its own tier-2 supplier with 3,000 of the receivable, so the core enterprise's credit flows down the chain." |
| 3.6 Request financing (30 s) | S1 | 💎 Receivables & Transfer → **Apply Financing** 7,000 | "Then it asks for financing on the remaining 7,000. The token is escrowed in the FinancingPool, so it cannot be financed twice." |
| 3.7 Quote (45 s) | F1 | Home → 🏦 Financier Dashboard → 📈 Financing Market → request → rate **3** (show net 6,790 / profit 210) → Submit; two MetaMask windows: **approve**, then **quote** | "A bank offers a 3 % discount. The page shows what the supplier will receive. The funds are locked in the pool when the quote is made." |
| 3.8 Accept (40 s) | S1 | 💰 Financing & Quotes → **Accept Quote** → after success open the Etherscan link | "The supplier accepts. In one atomic transaction the token moves to the bank and 6,790 mUSD moves to the supplier — from confirmation to cash in minutes, not weeks." |
| 3.9 Audit & freeze (50 s) | AU | Home → 🛡️ Auditor Dashboard → 🔍 Token Tracing & Freeze → enter the token ID → timeline; **Freeze** with a reason; switch to S2 → 💎 Receivables & Transfer shows the token **Frozen** with buttons disabled; back to AU → **Unfreeze** with a reason | "The auditor sees the full history of every token and can freeze a suspicious one. A frozen token can't be transferred, financed or redeemed — enforced by the contract, not just the UI." |
| 3.10 Repay & redeem (45 s) | CE → F1 | CE: 💳 Payables & Settlement → **Settle Payment** (approve + repay 10,000). F1: 💼 Loan Portfolio → **Redeem** | "At maturity the core enterprise pays the full 10,000 into the pool, and every holder redeems one to one. The bank gets 7,000 back on 6,790 lent." |
| 3.11 Dashboards (35 s) | AU, then S1 | AU: 📊 Global Audit Overview (KPIs + chart), 📜 Audit Event Logs filtered by `InvoiceSubmitted`; S1: Home → **Transaction History** | "Each role has a dashboard with live figures and charts, a filterable event log, and a transaction history with Etherscan links." |

> Optional (if time allows): S2 redeems its 3,000 — shows split holders being paid independently.

---

## Part 4 · Testing & results (7:45 – 9:00) — slide

> "We tested the deployed system end to end on Sepolia with eight dedicated wallets. 128 test cases: none failing after fixes. Fifteen transaction types ran on-chain, and all 35 unauthorised or invalid calls we tried were rejected by the contracts. Duplicate financing was blocked in 7 out of 7 attempts, and the time from invoice confirmation to cash was 7 minutes 24 seconds, under our 10-minute target.
> Testing also found 12 defects — for example, a financing button that did nothing and dashboards with hard-coded figures. Ten were fixed and retested on the live system the same day."

Slide content: results table and metrics from [test-report.md](../testing/test-report.md) §1 and §4.

## Part 5 · Deployment, limitations, conclusion (9:00 – 10:00) — slide

> "The frontend and backend run on Render, the contracts on Sepolia, and the main flow uses about 15 % less gas after optimisation. Limitations: it is a testnet prototype with a test stablecoin and manual KYC, and wallets can flag new sites or block transactions through their smart-account feature, which a production rollout would need to address.
> In short: invoices that cannot be double-financed, receivables that can be split and financed in minutes, and a full audit trail. Thank you."

---

## Before recording — checklist

- [ ] **ETH top-up from Main** (Send → SepoliaETH): S1 0.02, CE 0.02, F1 0.02, S2 0.01, AU 0.01
- [ ] mUSD: F1 and CE already hold enough (≈ 300,000 / ≈ 97,000) — no faucet needed
- [ ] MetaMask: Settings → Transactions → **Smart Transactions off**, **Smart account requests from dapps off**; on every confirmation **untick "Added protection"**
- [ ] A clean PDF named e.g. `DEMO-001.pdf`
- [ ] Chrome: close other tabs, hide bookmarks bar, zoom 100–110 %, MetaMask side panel visible
- [ ] Do one dry run of Part 3 without recording if possible — it uses ~12 transactions, all affordable after the top-up
- [ ] Be ready for the red "Malicious" warning when connecting a new account: "Continue at your own risk" (cut it in editing, or mention it once)

## Recording & editing

1. **Record**: Windows 11 **Clipchamp** (built in) → Record & create → Screen recording; or OBS Studio. Record Part 3 in several short clips (one per step) so mistakes are easy to redo.
2. **Slides**: use Member 5's PPT for Parts 1, 2, 4, 5; record them as screen clips or export as images.
3. **Edit** in Clipchamp: put clips in order, cut the waiting time during block confirmation, add the narration (record voice-over in Clipchamp, or speak while recording).
4. **Export** 1080p → upload to **YouTube** as *Unlisted* (or Public) → put the link in the README / report.
