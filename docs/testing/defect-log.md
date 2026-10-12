# Defect Log

> **Owner**: YANG SHUYI (Member 6)
> **Related**: [Test Plan](test-plan.md) · [Test Cases](test-cases.md)

Fixes for BUG-05, 06, 08, 09 and 10 were merged into `feature/backend-member2` as `6a54755` (2026-10-12 19:57); fixes for BUG-11 and 12 as `8c0fc51` (20:47). Both were deployed to Render and retested.

Severity: **P0** main flow blocked / funds incorrect · **P1** feature fails acceptance criteria · **P2** wording, display or usability issue.

## Summary

| ID | Title | Severity | Owner | Found | Status | Fixed in | Retested |
|---|---|---|---|---|---|---|---|
| BUG-01 | Faucet button shows wrong amount | P2 | Member 3 | 2026-10-12 | ✅ Closed | `0c54fde` (PR #1) | 2026-10-12 ✅ |
| BUG-02 | Stale session state after switching MetaMask account | P2 | Member 3 | 2026-10-12 | ✅ Closed | `0c54fde` (PR #1) | 2026-10-12 ✅ |
| BUG-03 | No UI to grant Auditor / Admin roles | P2 | Member 3 | 2026-10-12 | ✅ Closed | `0c54fde` (PR #1) | 2026-10-12 ✅ |
| BUG-04 | Duplicate login signature requests cause misleading "another wallet" error | P2 | Member 3 | 2026-10-12 | ⚪ Won't fix (team decision 2026-10-12; workaround: confirm only one sign-in request) | — | — |
| BUG-05 | Transactions are sent from the previously connected account after switching MetaMask account | **P1** | Member 3 | 2026-10-12 | ✅ Closed | `fix/frontend-bug05-06-08` (`3a9d48a`) | 2026-10-12 ✅ (page reloads on account switch) |
| BUG-06 | Contract revert reasons shown as raw "unknown custom error" hex | P2 | Member 3 | 2026-10-12 | ✅ Closed | `fix/frontend-bug05-06-08` (`3a9d48a`) | 2026-10-12 ✅ (`RETEST-BUG-06.png`) |
| BUG-07 | Cancelling the wallet transaction leaves a backend draft that blocks the invoice number forever | **P1** | Member 2 / Member 3 | 2026-10-12 | ⚪ Deferred (team decision 2026-10-12; workaround: use a new invoice number) | — | — |
| BUG-08 | No way to view/download the invoice PDF or check the hash in the UI | **P1** | Member 3 | 2026-10-12 | ✅ Closed | `fix/frontend-bug05-06-08` (`3a9d48a`) | 2026-10-12 ✅ (`RETEST-BUG-08.png`) |
| BUG-09 | Auditor tracing page always shows "Unfrozen"; cannot unfreeze after reload | **P1** | Member 3 | 2026-10-12 | ✅ Closed | `fix/frontend-bug05-06-08` (`be4c359`) | 2026-10-12 ✅ (#5 shown as Unfrozen after reload, matching chain) |
| BUG-10 | "Apply Financing" button does nothing (calls a non-existent function) | **P0** | Member 3 | 2026-10-12 | ✅ Closed | `fix/frontend-bug05-06-08` (`ce8bcf2`) | 2026-10-12 ✅ (TC-F15-01/02) |
| BUG-11 | Withdrawn quotes still show an "Accept" button | P2 | Member 3 | 2026-10-12 | ✅ Closed | `fix/dashboard-bug11-12` (`096318b`) | 2026-10-12 ✅ (deployed code verified; no withdrawn quote left to display) |
| BUG-12 | Dashboard KPIs hard-coded / wrong, and no charts (data visualisation missing) | **P1** | Member 3 | 2026-10-12 | ✅ Closed | `fix/dashboard-bug11-12` (`096318b`) | 2026-10-12 ✅ (TC-F23-02/03/04 retest) |
| KI-01 | MetaMask flags the site as "Malicious" | — (known issue) | Member 2 (informed) | 2026-10-12 | ⚠️ Won't fix | — | — |
| KI-02 | Transactions fail when MetaMask "smart account" (EIP-7702) is enabled | — (known issue / environment) | Member 3 (error message) | 2026-10-12 | ⚠️ Workaround | — | — |

BUG-01 – BUG-03 were found during test-environment setup (before formal execution), fixed by Member 3 in a single PR merged into `feature/backend-member2` at 14:46, and deployed to Render at 15:23 on 2026-10-12.

---

## BUG-01 · Faucet button shows wrong amount

- **Where**: Home page, `frontend/templates/index.html` line 12
- **Observed**: Button read "领取 10,000 测试稳定币" (claim 10,000 test stablecoins).
- **Expected**: `MockStablecoin.FAUCET_AMOUNT` is 100,000 mUSD (verified by an on-chain call on Sepolia); the success toast already said 100,000, so button and toast contradicted each other.
- **Fix**: Button now reads "Claim 100,000 mUSD Test Tokens".
- **Retest**: Live home page shows the corrected label. ✅

## BUG-02 · Stale session state after switching MetaMask account

- **Where**: `frontend/static/js/web3-provider.js` (`accountsChanged` handler); `frontend/templates/register.html` (`checkMyRegistration`)
- **Steps to reproduce**: Log in as CE and submit a registration → switch MetaMask to S1 (not yet signed in) → stay on the registration page.
- **Observed**: The header switched to S1's address, but S1 was never prompted to sign in. The registration status request failed silently (`catch (_) {}`), so the page kept showing CE's "Pending" banner and the submit button stayed disabled. A user could not tell they needed to sign in again.
- **Expected**: After switching accounts, the page clearly prompts the new account to sign in and does not show the previous account's data.
- **Fix**: Header button turns into a prominent "🔑 Sign In (address)" when the session is not authenticated; the registration page resets its status on failure; submitting without a session first requests a signature.
- **Retest**: Switched CE → S1 on the live site; "Sign In" button appeared, and after signing the page showed S1's own state. ✅
- **Related test case**: TC-F01-04 (partial pass before the fix).

## BUG-03 · No UI to grant Auditor / Admin roles

- **Where**: `frontend/templates/admin/system.html`, `frontend/templates/register.html`, `backend/routes/enterprises.py`
- **Observed**: Admins could only approve registration applications, and applications accept only SUPPLIER / CORE_ENTERPRISE / FUNDER (frontend form and backend `VALID_ROLES`). The "Roles & System" page offered only revoke and pause. Granting AUDITOR to the test auditor account required Member 1 to use the command line.
- **Expected**: PRD §2 states roles are granted on-chain by the admin; the auditor role must be grantable through the application.
- **Fix**: New "Direct Grant On-Chain Role" form on the admin page (Auditor, Admin, Supplier, Core Enterprise, Funder), calling `RoleManager.grantRole`.
- **Retest**: Form present on the live admin page. ✅ (Functional grant is exercised in TC-F03 / TC-F04 during formal execution.)

## BUG-04 · Duplicate login signature requests cause misleading "another wallet" error

- **Where**: `frontend/templates/register.html` (calls `ensureAuthenticated()` automatically on load, lines ~79/150/180) together with the header "Sign In" button (`connectWallet` → `authenticateWallet`); backend `backend/routes/auth.py` keeps only the latest challenge in the session.
- **Steps to reproduce**: As F1 (already a Funder, not signed in), open the site → the registration page auto-requests a login signature → also click the header "🔑 Sign In" → confirm the *older* request in MetaMask.
- **Observed**: Toast "Signature was produced by another wallet." The MetaMask request showed the correct wallet (F1) and the active MetaMask account was F1. Repeated clicks queued up to 4 pending requests ("1 of 4").
- **Cause**: Each request creates a new nonce, and the backend session stores only the most recent challenge. Signing an older challenge is verified against the newer message, so the recovered address does not match and the backend returns `ADDRESS_MISMATCH`.
- **Expected**: Only one signature request at a time (ignore or disable "Sign In" while a request is pending); if a stale challenge is signed, show "Login request expired, please sign in again" instead of blaming the wallet.
- **Workaround**: Reject all pending requests, refresh, and confirm only the single latest request.
- **Also observed**: Before signing in, F1 (an approved Funder) was shown the Enterprise Onboarding Application page instead of the funder dashboard — to be re-checked after sign-in.

## BUG-05 · Transactions are sent from the previously connected account after switching MetaMask account (P1)

- **Where**: `frontend/static/js/web3-provider.js` — `window.DAppState.contractClient` is created only once (`new window.ContractClient(provider, signer, ...)`, guarded by `if (!window.DAppState.contractClient)`) with the signer of the account connected at that moment. `handleAccountsChanged` updates `DAppState.signer` but never rebuilds `contractClient`, whose `ethers.Contract` instances stay bound to the old signer.
- **Steps to reproduce**: Connect as F1 and claim from the faucet → in MetaMask switch to F2 (do not reload) → sign in → click "Claim 100,000 mUSD Test Tokens" → repeat for CE.
- **Observed**: The header showed F2 / CE, but all three faucet transactions were sent **from F1**: [`0xf7dc7a77…`](https://sepolia.etherscan.io/tx/0xf7dc7a770e819ff91731a72185c0d5d7de0ac9c4506c8f98e6c6976f2e919f1c) (block 11897571), [`0xc5c342f2…`](https://sepolia.etherscan.io/tx/0xc5c342f2c116367b68c67c50f1b96e4e4319e00bcd3a9277917672d3012fe171) (11897591), [`0xa08f6c4b…`](https://sepolia.etherscan.io/tx/0xa08f6c4bd33a5807d0d496d8970b0c707166875e6df11ae472242125e0fe79d3) (11897596). On-chain balances afterwards: F1 300,000 mUSD, F2 0, CE 0.
- **Expected**: Every transaction is signed by the account currently shown in the header / selected in MetaMask.
- **Impact**: A user believes they act as one party but the transaction executes with another account's role and funds (e.g., paying or approving from the wrong wallet). Classified **P1**.
- **Suggested fix**: Rebuild `contractClient` (or call `contract.connect(newSigner)`) inside `handleAccountsChanged`; or simply `location.reload()` on `accountsChanged`, as is already done on `chainChanged`.
- **Workaround used during testing**: Press F5 after every account switch.

## BUG-06 · Contract revert reasons shown as raw "unknown custom error" hex

- **Where**: transaction modal error handling (`frontend/static/js/contract-client.js` `executeWithLifecycle` → `UIFeedback`).
- **Steps to reproduce**: As F1, open `/financier/portfolio` and click "Mark Overdue" on receivable #2 before its due date (TC-F21-01).
- **Observed**: Modal shows `execution reverted (unknown custom error) (action="estimateGas", data="0x11ed168a000…")`. `0x11ed168a` is the selector of `NotOverdueYet(uint256,uint64)`, which **is** present in the frontend's `FinancingPool` ABI, so the reason could have been decoded. The modal also shows "Estimated Fee: 300000 Gas", which is the hard-coded fallback used when estimation fails, not a real estimate.
- **Expected**: PRD §9 (error handling) requires the contract's rejection reason to be shown clearly, e.g. "This receivable is not overdue yet (due 17:18)". Relates to TC-F26-04.
- **Reproduced again**: TC-F12-05 (transfer of matured receivable #4) showed `unknown custom error` with data `0x5e4046db…` = `ReceivableMatured(uint256,uint64)`, also present in the frontend ABI.
- **Good**: the failure was caught at the gas-estimation stage — MetaMask was never opened and no gas was spent.
- **Root cause (verified in live code, 2026-10-12)**: `UIFeedback.parseBlockchainError` already maps both `NotOverdueYet` and `ReceivableMatured` to friendly text in `CUSTOM_ERROR_MESSAGES`, but it only looks at `err.revert?.name`. When ethers reports "unknown custom error" (here, during `estimateGas` through the MetaMask provider), `err.revert` is `null` and the raw message is shown. The selectors are in the frontend ABIs (`FinancingPool.json`, `ReceivableToken.json`).
- **Suggested fix**: when `err.revert` is missing, decode `err.data` with `contract.interface.parseError(err.data)` (try each contract's interface) and then look up `CUSTOM_ERROR_MESSAGES`; hide the fee line when estimation fails.

## BUG-07 · Cancelling the wallet transaction leaves a backend draft that blocks the invoice number forever (P1)

- **Where**: invoice upload flow — `frontend/templates/supplier/upload_invoice.html` first calls `POST /api/invoices/file` (stores the PDF and an `Invoice` row with status `FILE_UPLOADED`), then sends `submitInvoice` via MetaMask. `backend/routes/invoices.py` rejects any later upload with the same `invoice_no` + supplier + buyer unless the existing row is `REJECTED`.
- **Steps to reproduce**: As S1, fill in `TEST-001`, buyer CE, 10,000, due 2026-11-13, `invoice_ok.pdf` → Submit → cancel the MetaMask transaction → click Submit again.
- **Observed**: Toast "This invoice is already uploaded." (`409 INVOICE_ALREADY_UPLOADED`). On-chain `invoiceCount()` is unchanged (4) — `TEST-001` was never registered on-chain, yet the backend draft now blocks that invoice number permanently.
- **Expected**: PRD §9 requires user-rejected signatures to be handled gracefully. A draft whose on-chain submission never happened should be reusable (e.g., treat `FILE_UPLOADED` drafts from the same supplier as replaceable, expire them, or let the user retry the on-chain step for the existing draft).
- **Code path (verified in live code)**: `static/js/invoice-upload-flow.js` `uploadAndSubmit()` calls `apiClient.uploadInvoiceFile()` first and only then `contractClient.submitInvoice()`; there is no cleanup or retry path if the second step is rejected. Evidence: `GET /api/invoices` returned `TEST-001` (id 4) and `TEST-101` (id 5) with `status: FILE_UPLOADED`, `onchain_id: null`.
- **Note**: The on-chain duplicate check (F-07) is unaffected; this is a backend/off-chain false positive.
- **Workaround used during testing**: The main-flow invoice was renamed from `TEST-001` to `TEST-101`.

## BUG-08 · No way to view/download the invoice PDF or check the hash in the UI (P1)

- **Where**: `frontend/templates/supplier/invoices.html`, `frontend/templates/core_enterprise/invoices_pending.html` (no code in `frontend/` references `file_url` or `/api/invoices/<id>/file`).
- **Observed**: "My Invoices" and "Pending Invoices" show only a truncated file hash. There is no "view / download PDF" link and no indicator of whether the stored file's hash matches the on-chain `fileHash`. The backend endpoint works: `GET /api/invoices/6/file` returned the original `invoice_ok.pdf` for S1 (TC-F10-02) and `403 ROLE_REQUIRED` for S2 (TC-F10-03).
- **Expected**: PRD F-10 — "can download the PDF, and shows whether the file hash matches the on-chain value"; PRD §8 page list — the core enterprise "views the PDF, then confirms or rejects". Without it, the core enterprise confirms invoices without seeing the document.
- **Suggested fix**: add a "View PDF" link using the `file_url` already returned by `GET /api/invoices`; compute SHA-256 of the downloaded file in the browser and compare with the on-chain `getInvoice(id).fileHash`.

## BUG-09 · Auditor tracing page always shows "Unfrozen"; cannot unfreeze after reload (P1)

- **Where**: `frontend/templates/auditor/tracing.html`.
- **Steps to reproduce**: As AU, freeze receivable #5 on `/auditor/tracing` (tx `0x3e958edb…`, block 11898633) → reload the page → trace #5 again.
- **Observed**: Badge shows "Active / Unfrozen" and only the "Freeze" button is visible, although on-chain `getReceivable(5).frozen == true` and the supplier page correctly shows "Frozen" with buttons disabled. The badge is hard-coded in the template and only updated locally right after clicking Freeze/Unfreeze, so after a reload the auditor **cannot unfreeze through the UI**. In addition, Unfreeze sends a hard-coded reason ("Verified and unfrozen") instead of asking the auditor (PRD F-13: a reason is required).
- **Expected**: The page reflects the real on-chain freeze state; the auditor enters the unfreeze reason.
- **Fix (on branch, not merged)**: read `ReceivableToken.getReceivable(id).frozen` when tracing and render badge/buttons from it; prompt for the unfreeze reason.
- **Workaround used during testing**: unfreeze #5 from the browser console as AU via `contractClient.unfreezeReceivable(5n, reason)`.

## BUG-10 · "Apply Financing" button does nothing (P0)

- **Where**: `frontend/templates/supplier/receivables.html`, `confirmRequestFinancing()`.
- **Steps to reproduce**: As S1, open My Receivables → "Apply Financing" on #5 → enter any amount → "Sign & Submit Request".
- **Observed**: Nothing happens — no MetaMask popup, no message. The function first calls `contractClient.setApprovalForAllReceivables(...)`, which does not exist in `contract-client.js`, so a `TypeError` is thrown and only logged to the console. **Supplier financing (F-15), the core step of the main flow, cannot be done through the UI at all.** A scan of all templates found no other calls to non-existent client methods.
- **Also**: no client-side check that the amount ≤ token balance (20,000 against a 6,000 balance was accepted by the form).
- **Expected**: Submitting sends `FinancingPool.requestFinancing`; the interface spec states no approval is needed (`ReceivableToken.isApprovedForAll` always returns true for FinancingPool).
- **Fix (on branch, not merged)**: remove the non-existent approval call; validate `0 < amount ≤ balance`; show errors as a toast.
- **Note**: earlier financing in this test run (request #2) was created from the console, which is why this was not hit before.

## BUG-11 · Withdrawn quotes still show an "Accept" button (P2)

- **Where**: `frontend/templates/supplier/financing.html`, `renderQuotesList()`.
- **Steps to reproduce**: F2 withdraws quote #5 on request #3 (TC-F16-06) → S1 opens My Financing.
- **Observed**: Quote #5 is still listed with "Accept Quote & Receive Funds". The backend already projects it as `WITHDRAWN` (sync lag 0), but `renderQuotesList` ignores `q.status` and shows Accept for every quote while the request is open. Clicking it is safely rejected by the contract ("This quote is expired or has been revoked.", TC-F17-03).
- **Expected**: Withdrawn quotes are shown as "Withdrawn" without an Accept button.
- **Suggested fix**: render the Accept button only when `q.status === "ACTIVE"`; otherwise show a status badge.

## BUG-12 · Dashboard KPIs hard-coded / wrong, and no charts (P1)

- **Where**: `frontend/templates/{supplier,core_enterprise,financier}/dashboard.html`, `frontend/templates/auditor/overview.html`.
- **Found**: TC-F23-01 – 04 screenshots compared with on-chain state (2026-10-12 ~20:50).
- **Observed vs. on-chain truth**:

| Dashboard | KPI shown | On-chain truth | Cause |
|---|---|---|---|
| Core enterprise | Outstanding payables **0.00** | 11,000 unpaid (#5 10,000 + #4 1,000) | loader can exit before the wallet is ready; also counted repaid invoices |
| Core enterprise | Cumulative settled **0.00** | 3,000 repaid (#2) | card never computed (static placeholder) |
| Core enterprise | Due within 7 days **0.00** | (0 is correct by coincidence) | card never computed |
| Funder | Total disbursed **0.00** | 8,730 (2,910 + 5,820) | card never computed |
| Funder | Overdue assets **0** | (0 correct by coincidence) | card never computed |
| Auditor | Total financed principal **0.00** | 9,000 (#2 3,000 + #5 6,000) | card never computed |
| Auditor | Overdue rate **0.00%** | #4 is past due and unpaid | card never computed |
| Auditor | Total invoices **6** | 4 on-chain in the projection | counted 2 BUG-07 drafts never sent on-chain |

- **Also**: none of the dashboards contained a chart, although the course brief requires "data visualisation" and PRD F-23 requires "key figures and charts".
- **Fix (on branch, not merged)**: compute every KPI from the existing APIs (on-chain invoices only), reload on `walletAccountChanged`, add one Chart.js chart per role dashboard (`static/js/dashboard-charts.js`), and label drafts on the supplier dashboard.

## KI-01 · MetaMask flags the site as "Malicious" (known issue, won't fix)

- **Observed**: Connecting MetaMask to `supply-chain-finance-dapp-nkkr.onrender.com` shows "Malicious—flagged as unsafe"; signature requests show a red "Review alert". Users can proceed via "Continue at your own risk".
- **Cause (likely)**: MetaMask's phishing detection treating a newly deployed wallet-connecting site on a shared `onrender.com` subdomain as suspicious. The site itself is the team's own deployment.
- **Decision**: Not fixed (team decision, 2026-10-12). Possible remedies — a false-positive dispute to MetaMask or a custom domain — are outside the project's scope.
- **Mitigation**: User-testing participants are briefed beforehand; the demo video explains it in one line; the technical report discusses it as a real-world adoption barrier.

## KI-02 · Transactions fail when MetaMask "smart account" (EIP-7702) is enabled

- **Observed**: F1's first faucet claim (TC-F22-01) failed with an unreadable message: `transaction execution reverted (action="sendTransaction", data=null, reason=null ...)`. Tx [`0x16712e25…bbb5f7ad`](https://sepolia.etherscan.io/tx/0x16712e25346abcfe18a68b4ac1b8272698a132f52481d50b1faab896bbb5f7ad) (block 11897499) was **not** sent to MockStablecoin but to MetaMask's delegation contract `0xdb9b1e94…47db3` as a type-4 (EIP-7702) transaction wrapping `faucet()` inside `redeemDelegations(...)`; it reverted inside that wrapper.
- **Cause**: MetaMask's **"Added protection" (Transaction Shield)** option on the confirmation screen was pre-ticked (it adds a ~$1.66 fee). With it on, MetaMask upgrades the account to a MetaMask smart account (on-chain code `0xef0100…`) and routes the call through its delegation contract; the call reverted inside that wrapper. The settings "Smart Transactions" and "Smart account requests from dapps" were also on. A second attempt after only downgrading F1 failed the same way (tx `0xa924c7f6…5fe0d86d`, block 11897538), because the account was re-upgraded on send.
- **Workaround (applied 2026-10-12)**: (1) Settings → Transactions: turn off "Smart Transactions" and "Smart account requests from dapps"; (2) Account details → Smart account → Sepolia off for affected accounts (F1, CE); (3) **untick "Added protection" on every confirmation screen**. The retry succeeded as a plain call to MockStablecoin: tx [`0xf7dc7a77…2e919f1c`](https://sepolia.etherscan.io/tx/0xf7dc7a770e819ff91731a72185c0d5d7de0ac9c4506c8f98e6c6976f2e919f1c) (block 11897571), F1 balance 100,000 mUSD, F1 code back to `0x`.
- **Impact / recommendation**: Real users with smart accounts enabled may hit the same failure with an unhelpful error. The frontend could detect a revert without reason and suggest switching to a standard account; the report should mention wallet compatibility as an adoption risk.
