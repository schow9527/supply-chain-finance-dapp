# Supply Chain Finance DApp - User Manual

> **Version**: v1.0 (2026-10-13)
> **Audience**: Suppliers, Core Enterprises, Financiers, Auditors, Administrators
> **Deployment**: see the project README for the Render URL
> **Related docs**: [PRD](../PRD.md) · [Contract Interface](../../contracts/docs/interface.md) · [UI Wireframes](../wireframes/README.md)

---

## Contents

1. [Getting Ready](#1-getting-ready)
2. [Roles & Permission Matrix](#2-roles--permission-matrix)
3. [Common Operations](#3-common-operations)
4. [Supplier Guide](#4-supplier-guide)
5. [Core Enterprise Guide](#5-core-enterprise-guide)
6. [Financier Guide](#6-financier-guide)
7. [Auditor Guide](#7-auditor-guide)
8. [Administrator Guide](#8-administrator-guide)
9. [FAQ & Troubleshooting](#9-faq--troubleshooting)
10. [Glossary](#10-glossary)

---

## 1. Getting Ready

### 1.1 Install and Configure MetaMask

1. Install the [MetaMask](https://metamask.io/) browser extension (Chrome / Edge recommended).
2. Open MetaMask -> network selector (top left) -> choose the **Sepolia testnet**.
   - If it is not listed: Settings -> Networks -> show test networks, then enable Sepolia.
3. You need one wallet address per role (5 demo accounts in total).

### 1.2 Claim Test Tokens

| Token | Purpose | How to Claim |
| :--- | :--- | :--- |
| Sepolia ETH | Pay gas for on-chain transactions | Sepolia faucets (e.g. sepoliafaucet.com, Google Web3 Faucet) |
| mUSD test stablecoin | Quote funding, repayment | Click "Faucet" in the DApp (`faucet()`), fixed amount per claim |

### 1.3 Entry Points

- **Wallet not connected**: browse the landing page only; click "Connect MetaMask" to start.
- **Address not registered**: you are routed to the registration page.
- **Authorized address**: you are routed to your role's workspace automatically.

---

## 2. Roles & Permission Matrix

| Action | Admin | Supplier | Core Enterprise | Financier | Auditor |
| :--- | :--: | :--: | :--: | :--: | :--: |
| Submit registration application |  | ✓ | ✓ | ✓ |  |
| Review registration, grant / revoke roles | ✓ |  |  |  |  |
| Emergency pause / unpause | ✓ |  |  |  |  |
| Upload invoices |  | ✓ |  |  |  |
| Confirm / reject invoices |  |  | ✓ |  |  |
| Split & transfer receivables |  | ✓ |  |  |  |
| Request financing |  | ✓ |  |  |  |
| Quote & fund |  |  |  | ✓ |  |
| Repay at maturity |  |  | ✓ |  |  |
| Mark overdue |  |  |  | ✓ |  |
| Freeze / unfreeze receivables |  |  |  |  | ✓ |
| View own records | ✓ | ✓ | ✓ | ✓ | ✓ |
| View all records & event logs | ✓ |  |  |  | ✓ |

> Permissions are enforced at the **contract level**. Hiding buttons in the UI is only a convenience, not a security boundary.

---

## 3. Common Operations

### 3.1 Connecting a Wallet

Click "Connect MetaMask" on the landing page -> approve in MetaMask. Your abbreviated address appears top right.

- After switching accounts, the page re-routes automatically based on the new address's on-chain role.
- Unregistered addresses can only see the registration page.

### 3.2 Anatomy of an On-chain Transaction

Every "on-chain" button (submit invoice, confirm, quote, repay, ...) follows this flow:

1. **Client-side validation**: form checks (amount > 0, due date in the future, ...).
2. **Gas estimation**: estimated gas shown near the button.
3. **MetaMask signing**: confirm the transaction in the popup.
4. **Awaiting confirmation**: the transaction is broadcast to Sepolia; the page shows a pending state.
5. **Result**: success shows the tx hash with a block-explorer link; failure shows the decoded contract error.

### 3.3 Transaction History & Event Logs

- **Transaction History** (all roles): every on-chain transaction of the current address, filterable by type, each with a Sepolia explorer link.
- **Contract Event Logs** (admin & auditor): all contract events, filterable by type, time, and address.

---

## 4. Supplier Guide

### 4.1 Registration

1. After connecting your wallet, fill in **company name** and **contact person**.
2. Select role "Supplier" and submit.
3. Wait for admin review (track status on the progress bar).
4. Once approved, **refresh the page** to enter the supplier workspace.

### 4.2 Uploading an Invoice (Core Step)

1. Open "Upload Invoice" from the sidebar.
2. Fill in: invoice no., core enterprise address (must be a registered core enterprise), amount (mUSD), due date (must be in the future).
3. Upload the invoice PDF: the file is stored off-chain, and its **SHA-256 hash** is computed and filled in automatically (read-only).
4. Review and click "Submit On-chain", then confirm in MetaMask.
5. The contract dedups on "invoice no. + buyer + seller + amount":
   - **Already exists** -> the transaction reverts with "Invoice already exists" (the first gate against duplicate financing).
   - **Passed** -> status becomes "Pending", awaiting core-enterprise confirmation.

### 4.3 Managing Receivables

Open "My Receivables". Each token shows: ID, core enterprise, face value, due date, status (Active / Frozen / Overdue).

**Split transfer**:

1. Click "Split Transfer" on a token row.
2. Enter the recipient (**registered suppliers only**) and the share (<= your balance).
3. Confirm on-chain. Frozen or matured tokens cannot be transferred.

**Request financing**:

1. Click "Request Financing" and enter an amount (<= your balance).
2. On submit, the token is **auto-escrowed into the pool** - the same shares cannot back two open requests (the second gate).
3. The request appears as "Open" under "My Financing".

### 4.4 Handling Quotes

1. Under "My Financing", open an open request to see all financier quotes.
2. Each quote shows the discount rate and the **payout you receive** (= amount x (1 - discount rate)).
3. Pick the best quote and click "Accept":
   - One atomic transaction moves the token to the financier and the discounted funds to you; any failure rolls back everything.
4. If no quote satisfies you, "Cancel Request" returns the token, and you can re-request anytime.

> Note: tokens held by financiers can no longer be transferred - they can only be held to redemption. This is the third gate against double financing.

---

## 5. Core Enterprise Guide

### 5.1 Confirming / Rejecting Invoices

1. The dashboard shows pending invoice count and amount.
2. Open "Pending Invoices" and click "Preview" to view the PDF online. Verify:
   - the file hash matches the on-chain hash (verified automatically);
   - amount and due date match your internal ERP payables.
3. **Confirm**: click "Confirm (on-chain)". An equal-value ERC-1155 receivable is minted to the supplier automatically.
   - You can only confirm invoices issued to your own enterprise (enforced by the contract).
4. **Reject**: a reason is required. The dedup key is released so the supplier can fix and resubmit.

### 5.2 Repayment at Maturity

1. "Payables Ledger" lists all payables sorted by due date (including those financed to financiers).
2. "Upcoming alerts" appear before due dates.
3. Click "Repay Now":
   - If your mUSD allowance is insufficient, the page first guides you through `approve`;
   - Then `repay` pays the full face value into the financing pool.
4. After repayment, token holders can redeem.
5. **Overdue**: financiers will mark the item overdue; the record is visible platform-wide and affects your credit.

> Payment is still accepted after overdue; the token status moves from Overdue back to Repaid.

---

## 6. Financier Guide

### 6.1 Quoting in the Financing Market

1. "Financing Market" lists all open requests (supplier, amount, due date).
2. Click "Quote" and enter the **discount rate** (in bps, 300 = 3.00%).
3. The page previews live: supplier payout and your expected return.
4. You must `approve` and lock the mUSD funds before submitting the quote (two-step wizard).
5. Multiple financiers can quote the same request; the supplier picks one.
6. Until accepted, you can "Withdraw Quote" to reclaim the locked funds.

### 6.2 Managing Funded Assets

"My Funded Assets" shows every token you hold (face value, due date, status):

- **Funded**: the token is in your wallet; wait for the core enterprise to repay.
- **Redeem**: after repayment, click "Redeem" - burn the token and receive mUSD 1:1 (full balance at once).
- **Mark overdue**: available only after the due date if unpaid.
- **After overdue**: you can keep waiting; once the enterprise pays, the status recovers and you redeem normally.

### 6.3 Claiming Test Tokens

Use the "Faucet" entry to claim fixed-amount mUSD for demos. Make sure you have Sepolia ETH for gas.

---

## 7. Auditor Guide

### 7.1 Global Audit Board

Platform-wide view: total invoices, total transfer volume, overdue rate, frozen tokens, and the latest suspicious events (blocked duplicates, freezes, overdue marks).

### 7.2 Provenance Tracking

1. Enter a receivable ID to see its full lifecycle tree:
   Mint -> Split transfer -> Financing request -> Funding -> Repayment -> Redemption, each step with timestamp and tx hash.
2. Enforcement actions on suspicious tokens:
   - **Freeze**: a reason is required. Frozen tokens cannot be transferred, financed, or redeemed.
   - **Unfreeze**: after verification, with a recorded reason.
3. Freeze and unfreeze remain available even while the system is paused, for emergency response; every action is recorded on-chain.

---

## 8. Administrator Guide

### 8.1 Registration Review

1. "Registration Review" lists pending enterprises (name, address, applied role, submission time).
2. **Approve**: click "Approve (on-chain)" -> sign `grantRole` in MetaMask -> the applicant enters their workspace after refreshing. The grant tx hash is saved automatically.
3. **Reject**: a reason is required and kept on record.
4. One address can hold exactly one role at a time.

### 8.2 Roles & System Control

- **Revoke role**: execute `revokeRole` on offending addresses; afterwards all their writes are rejected by the contract.
- **Emergency pause**: click "Pause Now" in a systemic-risk situation. All business writes fail with "System paused"; reads are unaffected. **Exception**: admin role grants/revokes and auditor freeze/unfreeze still work while paused.
- **Unpause**: resume full functionality after the risk is cleared.

---

## 9. FAQ & Troubleshooting

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| "Invoice already exists" | The combo invoiceNo + buyer + seller + amount is already registered | Check for duplicate submission; if the original was rejected, resubmit after the dedup key is released |
| "System paused" | Admin triggered the emergency pause | Contact the admin; reads still work while paused |
| "Unauthorized(account, role)" | Wrong role or a revoked role | Verify the logged-in address; ask the admin to check the role |
| "Receivable is frozen" | The auditor froze the token | Contact the auditor for review and unfreezing |
| "Invalid recipient" | Split-transfer target is not a registered supplier | Ask the recipient to register and pass review first |
| "ERC20 insufficient balance / allowance" | Not enough mUSD or approve allowance | Claim faucet tokens; follow the page's approve guidance |
| "Not overdue yet" | Marking overdue before the due date | Only allowed after the due date and before repayment |
| Transaction stuck pending | Sepolia congestion or low gas | Speed up in MetaMask (higher gas) or wait; do not resubmit |
| Page unchanged after switching accounts | Frontend missed the account change | Refresh the page; make sure MetaMask is unlocked |
| Hash mismatch on invoice detail | The PDF was modified | Any content change alters the hash; use the original PDF |

> Full error reference: [contract interface doc, error table](../../contracts/docs/interface.md).

---

## 10. Glossary

| Term | Definition |
| :--- | :--- |
| Receivable | The payment obligation a core enterprise confirms it owes a supplier |
| Receivable token | The ERC-1155 digital token minted after confirmation; splittable, transferable, financeable |
| Split transfer | Partial transfer of a token's shares to another supplier |
| Discount rate (bps) | Basis points; 300 = 3.00%. Payout = amount x (1 - discount rate) |
| Atomic funding | One transaction that moves the token to the financier and funds to the supplier; all-or-nothing |
| Redemption (redeem) | After repayment, the holder burns the token and receives mUSD 1:1 |
| Dedup key | Hash of invoiceNo + buyer + seller + amount; the basis of on-chain deduplication |
| mUSD | MockStablecoin, a USDT-like test stablecoin (6 decimals) |
| Sepolia | The Ethereum testnet this project deploys to |
| Gas | On-chain transaction fee, paid in Sepolia ETH |
