# On-Chain Negative & Permission Checks

> **Owner**: YANG SHUYI (Member 6)
> **Executed**: 2026-10-12 ~20:30 SGT against Sepolia at block ≈ 11898877
> **Method**: `eth_call` simulation of each transaction **from the real test-account address** against the deployed contracts (state as of that block). A revert in `eth_call` is exactly what the transaction would do on-chain, without spending gas. Revert data is decoded against the custom errors declared in `contracts/contracts/**/*.sol` and OpenZeppelin errors.
> **Script**: [`scripts/onchain_sim.py`](../scripts/onchain_sim.py) (requires `pycryptodome`)

These checks verify the **contract layer** of PRD §2 ("both the contracts and the backend enforce permissions; hiding buttons in the frontend does not count"). UI-level behaviour is covered separately by screenshots in `../screenshots/`.

State at execution: receivable #5 held by F1 (6,000, financed via request #3) and S2 (4,000); request #3 Funded; quote #5 Withdrawn; invoice #3 Pending but past due; receivable #4 held by S1, matured.

| # | Check | Caller | Result |
|---|---|---|---|
| 1 | PM-1 grantRole by S1 | S1 | ✅ `REVERT AccessControlUnauthorizedAccount` |
| 2 | PM-1 revokeRole by S1 | S1 | ✅ `REVERT AccessControlUnauthorizedAccount` |
| 3 | PM-2 pause by AU | AU | ✅ `REVERT AccessControlUnauthorizedAccount` |
| 4 | PM-3 submitInvoice by CE | CE | ✅ `REVERT Unauthorized` |
| 5 | PM-4 confirmInvoice by S1 | S1 | ✅ `REVERT Unauthorized` |
| 6 | PM-5 transferReceivable by F1 | F1 | ✅ `REVERT Unauthorized` |
| 7 | PM-6 requestFinancing by CE | CE | ✅ `REVERT Unauthorized` |
| 8 | PM-7 submitQuote by S1 | S1 | ✅ `REVERT Unauthorized` |
| 9 | PM-8 repay by F1 | F1 | ✅ `REVERT NotReceivableBuyer` |
| 10 | PM-9 markOverdue by CE | CE | ✅ `REVERT Unauthorized` |
| 11 | PM-10 freeze by ADM2 | ADM2 | ✅ `REVERT Unauthorized` |
| 12 | TC-F03-02 grantRole by S1 | S1 | ✅ `REVERT AccessControlUnauthorizedAccount` |
| 13 | TC-F03-04 grant 2nd role to S1 (by ADM2) | by ADM2 | ✅ `REVERT AccountAlreadyHasRole` |
| 14 | TC-F04-04 revokeRole by S1 | S1 | ✅ `REVERT AccessControlUnauthorizedAccount` |
| 15 | TC-F05-05 pause by S1 | S1 | ✅ `REVERT AccessControlUnauthorizedAccount` |
| 16 | TC-F06-02 amount=0 (S1) | S1 | ✅ `REVERT InvalidAmount` |
| 17 | TC-F06-03 due date in past (S1) | S1 | ✅ `REVERT InvalidDueDate` |
| 18 | TC-F06-05 buyer=F1 not core enterprise (S1) | S1 | ✅ `REVERT InvalidBuyer` |
| 19 | TC-F06-06 submitInvoice by CE | CE | ✅ `REVERT Unauthorized` |
| 20 | TC-F08-02 confirm #5 by S1 (not buyer) | S1 | ✅ `REVERT Unauthorized` |
| 21 | TC-F08-03 confirm #5 twice (CE) | CE | ✅ `REVERT InvoiceNotPending` |
| 22 | TC-F09-02 reject #3 without reason (CE) | CE | ✅ `REVERT ReasonRequired` |
| 23 | TC-F12-06 F1 transfers held #5 |  | ✅ `REVERT Unauthorized` |
| 24 | TC-F13-03 freeze without reason (AU) | AU | ✅ `REVERT ReasonRequired` |
| 25 | TC-F13-04 freeze by S1 | S1 | ✅ `REVERT Unauthorized` |
| 26 | TC-F13-04 freeze by ADM2 | ADM2 | ✅ `REVERT Unauthorized` |
| 27 | TC-F15-04 requestFinancing by F1 | F1 | ✅ `REVERT Unauthorized` |
| 28 | TC-F16-04 quote 10000 bps (F1, contract) | F1, contract | ✅ `REVERT InvalidDiscount` |
| 29 | TC-F17-04 S1 acceptQuote(3,4) again | 3,4 | ✅ `REVERT RequestNotOpen` |
| 30 | TC-F18-03 S1 cancelRequest(3) after funded | 3 | ✅ `REVERT RequestNotOpen` |
| 31 | TC-F19-02 repay #5 by S1 | S1 | ✅ `REVERT NotReceivableBuyer` |
| 32 | TC-F19-02 repay #5 by F1 | F1 | ✅ `REVERT NotReceivableBuyer` |
| 33 | TC-F20-02 redeem #5 before repay (F1) | F1 | ✅ `REVERT NotRedeemable` |
| 34 | TC-F21-03 markOverdue #4 by non-holder F2 | non-holder | ✅ `REVERT NotReceivableHolder` |
| 35 | OK submitInvoice by S1 | S1 | ✅ `SUCCESS` |
| 36 | OK freeze #5 by AU | AU | ✅ `SUCCESS` |
| 37 | OK grantRole AUDITOR to X by ADM2 | ADM2 | ✅ `SUCCESS` |
| 38 | TC-F07-02 resubmit TEST-102 after confirmation (S1) | S1 | ✅ `REVERT InvoiceAlreadyExists` |

**Summary**: 38/38 checks behaved as expected — every unauthorised or invalid call reverted with the specific custom error, and the three authorised control calls (`OK …`) simulate successfully, confirming the reverts are caused by the access/business rules rather than by the test harness.
