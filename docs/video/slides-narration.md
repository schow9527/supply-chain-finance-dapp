# Slide Narration (full deck, 13 slides)

> **Owner**: YANG SHUYI (Member 6)
> **Deck**: `scf-dapp-demo-en_revised.pptx` (Member 5)
> **Video order**: slides 1–9 → live website demo (≈ 5:30) → slides 10–13
> **Timing**: slides ≈ 4:25 + demo ≈ 5:30 = **≈ 9:55** (≈ 150 words per minute)

## Before the demo

**Slide 1 · Title (6 s)**
> This is our SC6113 group project: a Supply Chain Finance DApp built on Ethereum.

**Slide 2 · Background & problem (28 s)**
> Small suppliers deliver goods to large buyers, then wait months to be paid, while banks find it hard to lend against their invoices. Two problems make it worse: the same invoice can be financed at several banks, because banks don't share data, and the core enterprise's strong credit never reaches tier-two suppliers. Our goals are fast funding, duplicate-proof financing, splittable credit, and a full audit trail.

**Slide 3 · Solution overview (25 s)**
> Our solution: once a core enterprise confirms an invoice on-chain, it becomes a receivable token that can be split, transferred and financed. The flow runs from upload and confirmation, through financing and funding, to repayment and redemption. Five roles share one chain, using twenty transaction types across five smart contracts.

**Slide 4 · System architecture (22 s)**
> Users sign every transaction directly in MetaMask against our contracts on Sepolia, so the backend never holds private keys. Invoice PDFs stay off-chain and only their hashes go on-chain. A Flask backend on Render stores the files and indexes contract events for dashboards and audits.

**Slide 5 · Smart contract design (20 s)**
> RoleManager controls the five roles and an emergency pause. InvoiceRegistry registers and confirms invoices. ReceivableToken is the ERC-1155 receivable that can be split and frozen. FinancingPool handles escrow, quotes, settlement and repayment, and MockStablecoin is our test dollar. Slither reported no high or medium issues.

**Slide 6 · Core mechanism (25 s)**
> Duplicate financing is blocked by three gates. First, the registry rejects an invoice that already exists. Second, requesting financing escrows the token, so the same share can't back two requests. Third, tokens bought by a financier can't be transferred again. And because a rejected invoice releases its key, a supplier can fix it and resubmit.

**Slide 7 · Contract interaction (20 s)**
> Three design choices make the contracts safe to use. Confirmation mints the token in the same transaction. A quote locks the financier's funds up front, so acceptance never fails for lack of money. And acceptance swaps the token and the cash atomically: if anything fails, everything rolls back.

**Slide 8 · Business flow (20 s)**
> The main line has six steps across three roles, plus four recoverable branches: rejecting an invoice, cancelling a financing request, marking a receivable overdue while still accepting late payment, and an auditor freeze at any time.

**Slide 9 · UI design (15 s)**
> We built nineteen pages for the five roles. Every on-chain action shows a gas estimate first, then a four-stage progress window, and any failure shows the contract's reason. Let's see it live.

## Live website demo (≈ 5:30)

## After the demo

**Slide 10 · Data model & backend (20 s)**
> Behind the dashboards, the backend keeps business tables for enterprises, invoices, holdings, financing requests and quotes, all built from contract events. Every event is stored with its block and transaction hash, and a sync cursor lets the indexer resume without gaps or duplicates.

**Slide 11 · Gas optimization (15 s)**
> Storage packing and fewer cross-contract calls reduced gas by about ten percent across all functions, and by fifteen percent on the main financing flow, measured with identical settings before and after.

**Slide 12 · Deployment & verification (30 s)**
> The contracts are live on Sepolia and the app runs on Render. We tested the live system end to end with eight wallets: 128 test cases with none failing, all 35 unauthorized calls rejected, duplicate financing blocked seven times out of seven, and seven minutes twenty-four seconds from confirmation to cash. Testing found twelve defects, and ten were fixed and retested on the live site.

**Slide 13 · Summary (20 s)**
> In summary: a full on-chain loop from confirmation to redemption, duplicate financing blocked by mechanism rather than policy, and a real deployment on Sepolia that anyone can try. Built by our team of six. Thank you for watching.
