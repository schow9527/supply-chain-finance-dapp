# UI Wireframes (Front-End Implementation Reference)

> Drawn by Member 5 as a page-by-page reference for Member 3's front-end implementation. 19 wireframes in total, mapping one-to-one to the 19 pages/views listed in PRD §8 "Front-End Page List".
> The red numbered callouts explain the design rationale and the acceptance criteria (F-xx) each element corresponds to — please check them one by one during implementation.

## How to Read

| No. | File | Page | Related Features |
| :--- | :--- | :--- | :--- |
| 00 | [00-landing-homepage.png](00-landing-homepage.png) | Landing / Homepage | F-01 |
| 01 | [01-register-application.png](01-register-application.png) | Registration Application | F-02 |
| 02 | [02-supplier-dashboard.png](02-supplier-dashboard.png) | Supplier Dashboard | F-23 |
| 03 | [03-supplier-upload-invoice.png](03-supplier-upload-invoice.png) | Upload Invoice | F-06, F-07 |
| 04 | [04-supplier-invoices.png](04-supplier-invoices.png) | My Invoices | F-10 |
| 05 | [05-supplier-receivables.png](05-supplier-receivables.png) | My Receivable Vouchers | F-11, F-12, F-15 |
| 06 | [06-supplier-financing.png](06-supplier-financing.png) | My Financing Management | F-17, F-18 |
| 07 | [07-core-dashboard.png](07-core-dashboard.png) | Core Enterprise Dashboard | F-23 |
| 08 | [08-core-pending-invoices.png](08-core-pending-invoices.png) | Pending Invoices | F-08, F-09 |
| 09 | [09-core-payables.png](09-core-payables.png) | Payables Ledger | F-19 |
| 10 | [10-financier-dashboard.png](10-financier-dashboard.png) | Financier Dashboard | F-23 |
| 11 | [11-financier-market.png](11-financier-market.png) | Financing Marketplace | F-16 |
| 12 | [12-financier-assets.png](12-financier-assets.png) | My Lending Assets | F-20, F-21 |
| 13 | [13-auditor-dashboard.png](13-auditor-dashboard.png) | Global Audit Board | F-23 |
| 14 | [14-auditor-tracking.png](14-auditor-tracking.png) | Voucher Penetration Tracking | F-13, F-14 |
| 15 | [15-admin-review.png](15-admin-review.png) | Qualification Review | F-03 |
| 16 | [16-admin-roles-control.png](16-admin-roles-control.png) | Roles & System Controls | F-04, F-05 |
| 17 | [17-transactions.png](17-transactions.png) | Transaction History Center | F-24 |
| 18 | [18-event-logs.png](18-event-logs.png) | Contract Event Logs | F-25 |

## Global Layout Rules

1. **Top navigation bar**: logo + global menu (Home / Dashboard / Transaction History / Event Logs) + wallet status capsule on the right (abbreviated address + connected state). After switching wallet accounts, the page re-renders automatically according to the new role (F-01).
2. **Left sidebar**: appears only on role workbench pages, listing that role's function menu; the current item is highlighted.
3. **Transaction feedback**: every on-chain button must go through four stages — MetaMask signing → transaction broadcast → waiting for confirmation → success/failure notice. On failure, display the decoded contract custom error (see the error table in `contracts/docs/interface.md`).
4. **Gas estimation**: show the estimated gas fee near the button before each transaction (F-26).
5. **Status badge colors**: pending/open = orange, success/normal/confirmed = green, failed/rejected/frozen = red, not-due/in-progress = blue, neutral = gray. Applied site-wide.

## Wireframes

### 00 Landing / Homepage
![Landing](00-landing-homepage.png)

### 01 Registration Application
![Registration](01-register-application.png)

### 02 Supplier Dashboard
![Supplier Dashboard](02-supplier-dashboard.png)

### 03 Upload Invoice
![Upload Invoice](03-supplier-upload-invoice.png)

### 04 My Invoices
![My Invoices](04-supplier-invoices.png)

### 05 My Receivable Vouchers
![My Receivables](05-supplier-receivables.png)

### 06 My Financing Management
![My Financing](06-supplier-financing.png)

### 07 Core Enterprise Dashboard
![Core Dashboard](07-core-dashboard.png)

### 08 Pending Invoices
![Pending Invoices](08-core-pending-invoices.png)

### 09 Payables Ledger
![Payables Ledger](09-core-payables.png)

### 10 Financier Dashboard
![Financier Dashboard](10-financier-dashboard.png)

### 11 Financing Marketplace
![Financing Market](11-financier-market.png)

### 12 My Lending Assets
![Lending Assets](12-financier-assets.png)

### 13 Global Audit Board
![Audit Board](13-auditor-dashboard.png)

### 14 Voucher Penetration Tracking
![Voucher Tracking](14-auditor-tracking.png)

### 15 Qualification Review
![Qualification Review](15-admin-review.png)

### 16 Roles & System Controls
![Roles & Controls](16-admin-roles-control.png)

### 17 Transaction History Center
![Transactions](17-transactions.png)

### 18 Contract Event Logs
![Event Logs](18-event-logs.png)
