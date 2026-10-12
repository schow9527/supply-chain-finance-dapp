# Functional Test Cases

> **Owner**: YANG SHUYI (Member 6)
> **Version**: v0.1 (2026-10-12)
> **Test plan**: [test-plan.md](test-plan.md)
> **Environment**: <https://supply-chain-finance-dapp-nkkr.onrender.com/> · Sepolia

## How to Use This Document

- **Account aliases** are defined in [Test Plan §5](test-plan.md#5-test-accounts): `ADM` Admin · `CE` Core Enterprise · `S1`/`S2` Suppliers · `F1`/`F2` Funders · `AU` Auditor · `X` Unauthorised.
- **Result**: after execution, replace `☐` with `✅ Pass` / `❌ Fail (Issue #)` / `⏭ Blocked`.
- **Evidence**: store screenshots in `docs/testing/screenshots/` named `<case-id>.png`; for on-chain cases also note the first 10 characters of the transaction hash – full links are collected in §7.
- All test invoice numbers use the `TEST-` prefix; amounts are in mUSD.
- For every on-chain case, also confirm the transaction modal goes through all four stages: **gas estimate → awaiting wallet confirmation → confirming → success/failure** (F-26).

### Test Data

| Data | Value | Purpose |
|---|---|---|
| Main-flow invoice | `TEST-101`, S1 → CE, 10,000 mUSD, due +30 days | Main flow (renamed from `TEST-001`, which is blocked by BUG-07) |
| Split invoice | `TEST-002`, S1 → CE, 6,000 mUSD, +30 days | Split-transfer 4,000 to S2 |
| Rejection invoice | `TEST-003`, S1 → CE, 1,000 mUSD, +30 days | Rejection and resubmission |
| Freeze invoice | `TEST-004`, S1 → CE, 2,000 mUSD, +30 days | Freeze / unfreeze |
| Maturity seed 1 | `TEST-OD-001`, S1 → CE, 3,000 mUSD, **due +30 min** (console) | Confirmed and financed to F1; used for overdue tests (TC-F21) |
| Maturity seed 2 | `TEST-OD-002`, S1 → CE, 1,000 mUSD, **due +30 min** (console) | Left unconfirmed; confirmed after maturity (TC-F08-04) |
| Maturity seed 3 | `TEST-OD-003`, S1 → CE, 1,000 mUSD, **due +30 min** (console) | Confirmed and kept by S1; transferred after maturity (TC-F12-05) |
| PDF files | `invoice_ok.pdf` (valid PDF), `fake.pdf` (renamed .txt), `image.png` | File validation |

---

## 1. Accounts & Permissions (F-01 – F-05)

### F-01 Wallet Login

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F01-01 | Login with an authorised role | S1 | Click "Connect Wallet" on the home page → connect MetaMask → sign the login message | A signature request appears (not a transaction, no gas); after signing, the supplier dashboard opens; header shows address, role and network | ☐ | |
| TC-F01-02 | Each role lands on its own page | CE/F1/AU/ADM | Log in with each account in turn | Core-enterprise dashboard / funder dashboard / auditor overview / admin registration review respectively | ☐ | |
| TC-F01-03 | Unauthorised address | X | Connect wallet and log in | Only the registration page is available; manually opening `/supplier/dashboard` returns no data (API 403) | ☐ | |
| TC-F01-04 | Switch wallet account | S1 → CE | While logged in as S1, switch to CE in MetaMask | Page switches to the core-enterprise view automatically, without manual refresh | ☐ | |
| TC-F01-05 | Wrong network | S1 | Switch MetaMask to mainnet or another testnet | Page prompts to switch to Sepolia with a one-click switch; no transaction can be sent until switched | ☐ | |
| TC-F01-06 | Reject login signature | S1 | Click "Reject" on the signature request | Clear "signature cancelled" message; stays logged out; page does not hang | ☐ | |
| TC-F01-07 | Call API without login | — | Open `/api/me` in an incognito window | HTTP 401, `{"error":{"code":"AUTH_REQUIRED",...}}` | ☐ | |
| TC-F01-08 | Logout | S1 | Click logout | Session cleared, back to home page; `/api/me` now returns 401 | ☐ | |

### F-02 Enterprise Registration

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F02-01 | Submit application | X | Fill in company name and contact, choose "Supplier", submit | Success message; status shown as "Pending" | ☐ | |
| TC-F02-02 | Duplicate application | X | Submit again while pending | Rejected with "application already exists" (API 409 `ENTERPRISE_ALREADY_EXISTS`) | ☐ | |
| TC-F02-03 | Missing required field | X | Leave company name empty | Blocked by the frontend; if bypassed, API 422 `INVALID_ENTERPRISE_DATA` | ☐ | |
| TC-F02-04 | Reapply after rejection | X | After rejection in TC-F03-03, submit again | Allowed; status back to "Pending"; previous rejection reason visible | ☐ | |

### F-03 Approve Registration & Grant Role

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F03-01 | Approve and grant role | ADM | On the registration review page, approve X → sign `grantRole` in MetaMask | Transaction succeeds, `RoleGranted` emitted; application marked "Approved" with tx hash recorded; X enters the role's pages after refresh | ☐ | |
| TC-F03-02 | Non-admin cannot grant | S1 | Call `grantRole` directly via Etherscan "Write Contract" or console | Reverts with `Unauthorized` | ☐ | |
| TC-F03-03 | Rejection requires a reason | ADM | Reject with an empty reason / with a reason | Empty: blocked (API 422 `REJECT_REASON_REQUIRED`); with reason: status "Rejected", reason visible to applicant | ☐ | |
| TC-F03-04 | One role per address | ADM | Grant Funder to S1, who is already a Supplier | Reverted by the contract | ☐ | |
| TC-F03-05 | Non-admin calls review API | S1 | `GET /api/enterprises` | HTTP 403 | ☐ | |

### F-04 Revoke Role

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F04-01 | Revoke role | ADM | On the Roles & System page, revoke X's Supplier role | `RoleRevoked` emitted; X removed from the authorised list | ☐ | |
| TC-F04-02 | Writes rejected after revocation | X | Try to upload an invoice (`submitInvoice`) | Reverts with `Unauthorized`; UI shows a permission message | ☐ | |
| TC-F04-03 | Revoked address can receive another role | ADM | Grant Auditor to X | Succeeds | ☐ | |
| TC-F04-04 | Non-admin cannot revoke | S1 | Call `revokeRole` | `Unauthorized` | ☐ | |

### F-05 Emergency Pause & Resume

> ⚠️ Pausing affects the whole team. Notify the group chat before running these cases and unpause immediately afterwards.

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F05-01 | Pause the system | ADM | Click "Pause" on the Roles & System page | `Paused` emitted; UI shows the system is paused | ☐ | |
| TC-F05-02 | Business writes fail while paused | S1 | Upload invoice / split-transfer / request financing | All fail with "System is paused" (`SystemPaused`), ideally already at the gas-estimate stage | ☐ | |
| TC-F05-03 | Reads unaffected while paused | S1/AU | Browse dashboard, invoice list, event log | Displayed normally | ☐ | |
| TC-F05-04 | Emergency actions still allowed while paused | ADM/AU | Admin grants/revokes a role; auditor freezes a receivable | Succeed (by design – interface doc item 8) | ☐ | |
| TC-F05-05 | Non-admin cannot pause | S1 | Call `pause` | `Unauthorized` | ☐ | |
| TC-F05-06 | Resume | ADM | Click "Resume" | `Unpaused` emitted; S1 can upload an invoice again | ☐ | |

---

## 2. Invoices (F-06 – F-10)

### F-06 Upload Invoice

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F06-01 | Valid upload | S1 | Enter `TEST-101`, buyer CE, 10,000, +30 days, `invoice_ok.pdf` → submit and sign | PDF uploaded and hash returned; `submitInvoice` succeeds, `InvoiceSubmitted` emitted; invoice shown as "Pending" in My Invoices | ✅ Pass (as `TEST-102`, on-chain #5; success modal auto-redirects after a few seconds) | `TC-F06-01.png`; tx `0x3c72d626` |
| TC-F06-02 | Zero or negative amount | S1 | Amount 0 / −5 | Blocked by frontend; if bypassed, API 422 `INVALID_AMOUNT`, contract `InvalidAmount` | ☐ | |
| TC-F06-03 | Due date not in the future | S1 | Due date today or yesterday | Blocked by frontend; API 422 `INVALID_DUE_DATE`, contract `InvalidDueDate` | ☐ | |
| TC-F06-04 | Non-PDF file | S1 | Upload `image.png`, `fake.pdf` | Rejected, API 422 `INVALID_FILE_TYPE` | ☐ | |
| TC-F06-05 | Buyer is not a core enterprise | S1 | Buyer address = F1 or X | Rejected by contract (`InvalidBuyer`) or backend role check | ☐ | |
| TC-F06-06 | Non-supplier uploads | CE | Open the upload page or call `POST /api/invoices/file` | API 403 `ROLE_REQUIRED`; contract `Unauthorized` | ☐ | |
| TC-F06-07 | File too large | S1 | Upload a PDF above the size limit | API 413 `FILE_TOO_LARGE` with a clear UI message | ☐ | |

### F-07 Duplicate Registration Prevention

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F07-01 | Resubmit identical invoice | S1 | Submit `TEST-101`, CE, 10,000 again while pending | Rejected with "invoice already exists" (backend 409 `INVOICE_ALREADY_UPLOADED` or contract `InvoiceAlreadyExists`) | ✅ Pass — backend `409 INVOICE_ALREADY_UPLOADED`, MetaMask not opened (on-chain layer verified separately in TC-F07-03) | `TC-F07-01.png` |
| TC-F07-02 | Resubmit a confirmed invoice | S1 | Submit `TEST-101` again after it is confirmed | Still rejected | ☐ | |
| TC-F07-03 | Bypass backend, call contract directly | S1 | Call `submitInvoice` on Etherscan with `TEST-101`'s parameters | Reverts with `InvoiceAlreadyExists` – proves interception is on-chain, independent of the backend | ✅ Pass — `InvoiceAlreadyExists(5)` via console `estimateGas` (no tx sent) | `TC-F07-03.png` |
| TC-F07-04 | Rejected invoice can be resubmitted | S1 | After `TEST-003` is rejected (TC-F09-01), submit it again with the same data | Allowed (rejection releases the dedup key) | ☐ | |
| TC-F07-05 | Observation: amount changed only | S1 | Same number and buyer as `TEST-101`, amount 10,001 | Record the actual result. The dedup key includes the amount, so by design this is accepted; discuss this limitation in the report | ☐ | |

### F-08 Confirm Invoice

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F08-01 | Confirm and mint receivable | CE | Open `TEST-101` on Pending Invoices, view PDF → confirm | `InvoiceConfirmed`, `ReceivableMinted` emitted; a 10,000 receivable appears in S1's My Receivables | ✅ Pass — invoice #5 Confirmed; receivable #5 minted to S1 (10,000, Active) | `TC-F08-01.png`; tx `0xa423e023` |
| TC-F08-02 | Only the invoiced buyer can confirm | Another core enterprise or S1 | Call `confirmInvoice(<TEST-001 id>)` | `NotInvoiceBuyer` / `Unauthorized` | ☐ | |
| TC-F08-03 | Confirm twice | CE | Confirm `TEST-101` again | Rejected | ☐ | |
| TC-F08-04 | **(after maturity)** Confirm after due date | CE | Confirm `TEST-OD-002` after its due date has passed | `InvalidDueDate` | ☐ | |

### F-09 Reject Invoice

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F09-01 | Reject invoice | CE | Reject `TEST-003` with reason "Amount does not match contract" | `InvoiceRejected` emitted; status "Rejected"; no receivable minted; S1 can see the reason | ☐ | |
| TC-F09-02 | No reason | CE | Leave reason empty | Blocked by frontend and rejected by contract | ☐ | |

### F-10 Invoice List & Details

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F10-01 | Filter by status | S1 | Switch between Pending / Confirmed / Rejected on My Invoices | List matches actual statuses | ☐ | |
| TC-F10-02 | Download PDF and verify hash | S1/CE | Open invoice details, download PDF | Download works; page shows that the file hash **matches** the on-chain `fileHash` | ❌ Fail (BUG-08) — no download link or hash-match indicator in the UI; backend `GET /api/invoices/6/file` returns the correct PDF | `TC-F10-02-api.png`, `TC-F10-02.png` |
| TC-F10-03 | Unrelated party cannot download | S2/F1 | Open `/api/invoices/<id>/file` of an S1 invoice | HTTP 403 | ✅ Pass — S2 gets `403 ROLE_REQUIRED` "You may not download this invoice." | `TC-F10-03.png` |
| TC-F10-04 | Auditor/admin can download | AU/ADM | Same as above | Download succeeds | ✅ Pass (AU) — `GET /api/invoices/6/file` downloads the PDF (23.7 KB); ADM not yet checked | `TC-F10-04.png` |

---

## 3. Receivables (F-11 – F-14)

### F-11 My Receivables

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F11-01 | Balance matches chain | S1 | Open My Receivables; call `ReceivableToken.balanceOf(S1, id)` on Etherscan | Amount, core enterprise, due date and status match on-chain data | ✅ Pass — #4 (1,000, due 2026-10-12 17:18:18) and #5 (10,000, due 2026-11-13) match on-chain `balanceOf`; #2 (transferred to F1) correctly absent | `TC-F11-01.png` |
| TC-F11-02 | Funder sees acquired receivable | F1 | After funding in the main flow, open My Loans | Receivable acquired from S1 is listed | ☐ | |

### F-12 Split & Transfer

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F12-01 | Partial split transfer | S1 | Transfer 4,000 of `TEST-002` to S2 | `ReceivableTransferred` emitted; S1 holds 2,000, S2 holds 4,000 | ☐ | |
| TC-F12-02 | Exceeds balance | S1 | Transfer 99,999 | Rejected with `ERC1155InsufficientBalance`; clear UI message | ☐ | |
| TC-F12-03 | Recipient is not a supplier | S1 | Transfer to F1, CE or X | Rejected with `InvalidRecipient` | ☐ | |
| TC-F12-04 | Receivable frozen | S1 | Transfer `TEST-004` after it is frozen (see TC-F13-02) | Rejected with `ReceivableIsFrozen` | ☐ | |
| TC-F12-05 | **(after maturity)** Receivable matured | S1 | Transfer part of the `TEST-OD-003` receivable to S2 after its due date | Rejected with `ReceivableMatured` | ✅ Pass — rejected at gas estimation with `ReceivableMatured` (`0x5e4046db`), no tx sent; message shown as raw hex (BUG-06) | `TC-F12-05.png` |
| TC-F12-06 | Funder cannot transfer | F1 | Try to transfer a held receivable | Rejected | ☐ | |

### F-13 Freeze & Unfreeze

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F13-01 | Freeze receivable | AU | On Receivable Tracing, find `TEST-004` → freeze with reason "Suspected fictitious trade" | `ReceivableFrozen` emitted; status shown as "Frozen" | ☐ | |
| TC-F13-02 | Frozen cannot be transferred/financed/redeemed | S1 | Transfer or request financing on the frozen receivable | Both rejected with `ReceivableIsFrozen` | ☐ | |
| TC-F13-03 | Reason required | AU | Freeze / unfreeze with an empty reason | Rejected | ☐ | |
| TC-F13-04 | Non-auditor cannot freeze | S1/ADM | Call `freeze` | `Unauthorized` | ☐ | |
| TC-F13-05 | Unfreeze restores previous state | AU → S1 | Unfreeze (with reason) → S1 transfers again | `ReceivableUnfrozen` emitted; transfer succeeds | ☐ | |

### F-14 Receivable History

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F14-01 | Full timeline | AU | After the main flow, look up the `TEST-101` receivable | Chronological: minted → financing requested → funded → repaid → redeemed, each with a transaction link | ☐ | |
| TC-F14-02 | Split record | AU | Look up the `TEST-002` receivable | Shows the 4,000 transfer S1 → S2 | ☐ | |
| TC-F14-03 | Sync latency | AU | Time from sending a transaction until it appears in the timeline | ≤ 30 s (non-functional requirement) | ☐ | |

---

## 4. Financing & Repayment (F-15 – F-22)

### F-15 Request Financing

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F15-01 | Request financing | S1 | My Receivables → `TEST-101` → request financing for 10,000 | `FinancingRequested` emitted; receivable escrowed in FinancingPool; S1's balance decreases; status "Awaiting quotes" | ☐ | |
| TC-F15-02 | Exceeds balance | S1 | Request 20,000 | Rejected | ☐ | |
| TC-F15-03 | Same amount cannot back two requests | S1 | Request again on `TEST-101` after the full amount is escrowed | Rejected (escrowed balance is 0) – **counts toward the duplicate-financing interception rate** | ☐ | |
| TC-F15-04 | Non-supplier requests | F1 | Call `requestFinancing` | `Unauthorized` | ☐ | |

### F-16 Submit Quote

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F16-01 | Quote (with approval) | F1 | In the Financing Market, pick the `TEST-101` request, discount 3 % → UI guides `approve` of mUSD → `submitQuote` | Both transactions succeed; `Approval`, `QuoteSubmitted` emitted; supplier's net payout shown as 9,700 | ☐ | |
| TC-F16-02 | Multiple funders quote | F2 | Quote 2.5 % on the same request | Succeeds; S1 sees both quotes on My Financing | ☐ | |
| TC-F16-03 | Payout calculation | — | Compare UI value with `previewPayout(amount, bps)` | Identical | ☐ | |
| TC-F16-04 | Invalid discount rate | F1 | Enter 100 % or more | Rejected | ☐ | |
| TC-F16-05 | No approval / insufficient balance | F1 | Quote without `approve` / with insufficient mUSD | Rejected with `ERC20InsufficientAllowance` / `ERC20InsufficientBalance`; clear message | ☐ | |
| TC-F16-06 | Withdraw quote | F2 | Withdraw the quote from TC-F16-02 | `QuoteWithdrawn` emitted; locked mUSD returned to F2 | ☐ | |

### F-17 Accept Quote & Disburse

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F17-01 | Accept quote | S1 | Accept F1's quote on My Financing | Single transaction: receivable to F1 and 9,700 mUSD to S1; `FinancingFunded` emitted. **Record block time for the time-to-financing metric** | ☐ | |
| TC-F17-02 | Non-requester accepts | S2 | Call `acceptQuote` | Rejected | ☐ | |
| TC-F17-03 | Accept a withdrawn quote | S1 | Accept the quote withdrawn in TC-F16-06 | Rejected | ☐ | |
| TC-F17-04 | Accept twice | S1 | After funding, accept another quote | Rejected – **counts toward the duplicate-financing interception rate** | ☐ | |

### F-18 Cancel Financing Request

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F18-01 | Cancel before acceptance | S1 | Request financing with S1's remaining 2,000 of `TEST-002` → cancel | `FinancingCancelled` emitted; receivable returned to S1 | ☐ | |
| TC-F18-02 | Cannot accept after cancel | S1 | Accept a quote on the cancelled request | Rejected | ☐ | |
| TC-F18-03 | Cannot cancel after funding | S1 | Cancel the funded `TEST-101` request | Rejected | ☐ | |

### F-19 Repay at Maturity

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F19-01 | Repay (with approval) | CE | On Payables, click repay for `TEST-101` → guided `approve` → `repay` | Full face value 10,000 paid into FinancingPool; `Repaid` emitted; receivable status "Repaid" | ☐ | |
| TC-F19-02 | Non-buyer repays | S1/F1 | Call `repay` | Rejected | ☐ | |
| TC-F19-03 | Repay twice | CE | Repay again | Rejected | ☐ | |
| TC-F19-04 | Payables sorted | CE | Open Payables | Sorted by due date | ☐ | |

### F-20 Redeem

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F20-01 | Funder redeems | F1 | Redeem `TEST-101` on My Loans | Receivable burned; 10,000 mUSD received 1:1; `Redeemed` emitted. F1 profit = 10,000 − 9,700 = 300 | ☐ | |
| TC-F20-02 | Redeem before repayment | F1 | Redeem before CE has repaid | Rejected | ☐ | |
| TC-F20-03 | Split holders redeem separately | S1, S2 | After `TEST-002` is repaid, each redeems | S2 receives 4,000, S1 receives 2,000 | ☐ | |
| TC-F20-04 | Redeem frozen receivable | F1 | Redeem a repaid but frozen receivable | Rejected with `ReceivableIsFrozen` | ☐ | |

### F-21 Mark Overdue

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F21-01 | Mark before due date | F1 | Before maturity, mark `TEST-OD-001` overdue | Rejected with `NotOverdueYet` | ✅ Pass (display issue → BUG-06) | `TC-F21-01.png`; rejected at gas estimation (`NotOverdueYet`), no tx sent |
| TC-F21-02 | **(after maturity)** Mark after due date | F1 | After the due date, with CE not having repaid | `MarkedOverdue` emitted; CE's overdue record visible on the dashboard (`overdueCount` +1) | ✅ Pass — receivable #2 status Overdue; `overdueCount(CE)` = 1 (dashboard visibility checked in TC-F23-02) | `TC-F21-02.png`; tx `0xd1a69653` |
| TC-F21-03 | Non-holder marks | F2 | Call `markOverdue` | Rejected | ☐ | |
| TC-F21-04 | **(after maturity)** Late repayment after overdue | CE → F1 | CE repays → F1 redeems | Status changes Overdue → Repaid; redemption succeeds | ☐ | |

### F-22 Test Stablecoin Faucet

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F22-01 | Claim | F1 | Click "Get test tokens" | mUSD balance +100,000; `Transfer` emitted | ✅ Pass (after KI-02 workaround) | `TC-F22-01.png`; tx `0xf7dc7a77` |

---

## 5. Dashboard & Audit (F-23 – F-26)

| ID | Scenario | Account | Steps / Input | Expected Result | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-F23-01 | Supplier dashboard | S1 | Open dashboard | Total receivables held, amount financed, pending items, charts; figures match reality | ☐ | |
| TC-F23-02 | Core-enterprise dashboard | CE | Same | Pending invoices, total payables, upcoming payments, overdue records | ☐ | |
| TC-F23-03 | Funder dashboard | F1 | Same | Total funded, outstanding amount, overdue count | ☐ | |
| TC-F23-04 | Auditor overview | AU | Same | Platform invoice count, total receivables, total financing, overdue rate | ☐ | |
| TC-F23-05 | Data isolation | S2 | Open dashboard | Only S2's own data; nothing from S1 | ☐ | |
| TC-F23-06 | Mobile display | Any | Chrome DevTools iPhone viewport, or a real phone | Layout intact, no horizontal scrolling, buttons tappable | ☐ | |
| TC-F24-01 | Transaction history | S1 | Open Transaction History | All of S1's on-chain transactions listed, each with a working Etherscan link | ☐ | |
| TC-F25-01 | Event log | AU/ADM | Open Event Log | All contract events listed | ☐ | |
| TC-F25-02 | Filter by type/time/address | AU | Filter by `InvoiceSubmitted`, a date, S1's address | Correct results | ☐ | |
| TC-F25-03 | Ordinary roles see related events only | S1 | `GET /api/events` | Only events related to S1 | ☐ | |
| TC-F26-01 | Gas estimate | Any | Before any on-chain transaction | Estimated gas fee is shown before MetaMask opens | ☐ | |
| TC-F26-02 | User rejects signature | S1 | Click "Reject" in MetaMask | Modal moves to the failure stage with "cancelled by user"; can be closed and retried | ☐ | |
| TC-F26-03 | Insufficient ETH | New account | Send a transaction with no Sepolia ETH | Insufficient-balance message | ☐ | |
| TC-F26-04 | Contract revert reason | S1 | Any revert case above | Specific, human-readable reason shown – not a raw hex string | ☐ | |

---

## 6. Permission Matrix Cross-Check (PRD §2)

The PRD requires that "both the contracts and the backend enforce permissions; hiding buttons in the frontend does not count". For each row, call the contract (Etherscan Write Contract) or API with an **unauthorised role**; every call is expected to be rejected.

| Operation | Unauthorised account used | Contract-layer rejection | Backend-layer rejection | Result |
|---|---|---|---|---|
| Grant/revoke role | S1 | `grantRole` → `Unauthorized` | `PATCH /api/enterprises/<id>` → 403 | ☐ |
| Pause/resume | AU | `pause` → `Unauthorized` | — | ☐ |
| Upload invoice | CE | `submitInvoice` → `Unauthorized` | `POST /api/invoices/file` → 403 | ☐ |
| Confirm/reject invoice | S1 | `confirmInvoice` → reverted | — | ☐ |
| Split/transfer | F1 | `transferReceivable` → reverted | — | ☐ |
| Request financing | CE | `requestFinancing` → `Unauthorized` | — | ☐ |
| Quote | S1 | `submitQuote` → `Unauthorized` | — | ☐ |
| Repay | F1 | `repay` → reverted | — | ☐ |
| Mark overdue | CE | `markOverdue` → reverted | — | ☐ |
| Freeze/unfreeze | ADM | `freeze` → `Unauthorized` | — | ☐ |
| View all events | S1 | — | `GET /api/events` returns related events only | ☐ |
| View registration applications | S1 | — | `GET /api/enterprises` → 403 | ☐ |

---

## 7. On-Chain Transaction Coverage (20 Types)

Each transaction type needs at least one successful Sepolia transaction as evidence. Copy "Gas Used" from Etherscan and compare with the Foundry benchmark.

| # | Transaction | Sender | Test case | Tx hash (Etherscan link) | Gas used (on-chain) | Foundry benchmark | Result |
|---|---|---|---|---|---:|---:|---|
| 1 | `grantRole` | ADM | TC-F03-01 | | | 96,583 | ☐ |
| 2 | `revokeRole` | ADM | TC-F04-01 | | | 35,650 | ☐ |
| 3 | `pause` | ADM | TC-F05-01 | | | 47,041 | ☐ |
| 4 | `unpause` | ADM | TC-F05-06 | | | — | ☐ |
| 5 | `submitInvoice` | S1 | TC-F06-01 | | | 173,254 | ☐ |
| 6 | `confirmInvoice` | CE | TC-F08-01 | | | 124,931 | ☐ |
| 7 | `rejectInvoice` | CE | TC-F09-01 | | | 43,332 | ☐ |
| 8 | `transferReceivable` | S1 | TC-F12-01 | | | 74,640 | ☐ |
| 9 | `freeze` | AU | TC-F13-01 | | | 35,915 | ☐ |
| 10 | `unfreeze` | AU | TC-F13-05 | | | 35,909 | ☐ |
| 11 | `requestFinancing` | S1 | TC-F15-01 | | | 145,491 | ☐ |
| 12 | `submitQuote` | F1 | TC-F16-01 | | | 152,198 | ☐ |
| 13 | `withdrawQuote` | F2 | TC-F16-06 | | | 49,922 | ☐ |
| 14 | `acceptQuote` | S1 | TC-F17-01 | | | 131,343 | ☐ |
| 15 | `cancelRequest` | S1 | TC-F18-01 | | | 78,436 | ☐ |
| 16 | `repay` | CE | TC-F19-01 | | | 83,586 | ☐ |
| 17 | `redeem` | F1 | TC-F20-01 | | | 64,043 | ☐ |
| 18 | `markOverdue` | F1 | TC-F21-02 | | | 76,931 | ☐ |
| 19 | `faucet` | F1 | TC-F22-01 | | | 50,675 | ☐ |
| 20 | `approve` (mUSD) | F1/CE | TC-F16-01 | | | — | ☐ |

> Foundry benchmarks are taken from [gas-optimization.md](../../contracts/docs/gas-optimization.md) (post-optimisation, `--isolate` mode). Transactions that write to a fresh storage slot may cost slightly more on-chain; this is expected.

---

## 8. Non-Functional Requirements

| ID | Category | Method | Target | Measured | Result |
|---|---|---|---|---|---|
| TC-NF-01 | Performance | Chrome DevTools Network: full load time of each query page (excluding Render cold start – warm up with one visit first) | ≤ 3 s | | ☐ |
| TC-NF-02 | Sync latency | Time from transaction confirmation until new data appears in the UI/API (same as TC-F14-03) | ≤ 30 s | | ☐ |
| TC-NF-03 | Responsiveness | Check all 19 pages at 375 px, 768 px and 1440 px | No misalignment, no horizontal scrolling | | ☐ |
| TC-NF-04 | Compatibility | Latest Chrome + MetaMask | Full flow usable | | ☐ |
| TC-NF-05 | Security: private keys | Review backend code and environment-variable list | Backend stores no private keys | | ☐ |
| TC-NF-06 | Security: information leakage | Open `/api/health/ready`; trigger several errors | No database/RPC URLs or stack traces exposed | | ☐ |
| TC-NF-07 | Availability | Check the health endpoint daily during submission and demo period | Continuously reachable | | ☐ |

---

## 9. Execution Summary (fill in after execution)

| Module | Cases | Pass | Fail | Blocked | Pass rate |
|---|---:|---:|---:|---:|---:|
| Accounts & Permissions F-01–05 | 27 | | | | |
| Invoices F-06–10 | 22 | | | | |
| Receivables F-11–14 | 16 | | | | |
| Financing & Repayment F-15–22 | 30 | | | | |
| Dashboard & Audit F-23–26 | 14 | | | | |
| Permission matrix | 12 | | | | |
| Non-functional | 7 | | | | |
| **Total** | **128** | | | | |
