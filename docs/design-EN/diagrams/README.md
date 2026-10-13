# Diagram Collection (Member 5: System Design & Presentation)

> The 5 diagram types required by the technical report. Each diagram ships as an editable mermaid source (`.mmd`, rendered natively by GitHub) plus an exported PNG for reports and slides.

## 01. System Architecture

Four layers: user layer -> frontend layer -> blockchain layer (Sepolia) + backend layer (Flask/Render) -> data layer; on-chain/off-chain separation of duties, no private keys at the backend.

![System Architecture](01-system-architecture.png)

<details><summary>mermaid source</summary>

```mermaid
flowchart TB
    subgraph U["User Layer (5 Roles)"]
        U1["Supplier"]
        U2["Core Enterprise"]
        U3["Financier"]
        U4["Auditor"]
        U5["Admin"]
    end

    subgraph FE["Frontend Layer (HTML + CSS + JS, 19 views)"]
        FE1["Supplier Workspace<br/>Dashboard / Upload / Invoices / Receivables / Financing"]
        FE2["Core Enterprise Workspace<br/>Dashboard / Pending / Payables"]
        FE3["Financier Workspace<br/>Dashboard / Market / Assets"]
        FE4["Auditor Workspace<br/>Audit Board / Provenance Tracking"]
        FE5["Admin Workspace<br/>Registration Review / Roles &amp; System Control"]
        FE6["Public Pages<br/>Landing / Register / Transactions / Event Logs"]
        FE7["Ethers.js Contract Calls<br/>Gas Estimation · Tx Status"]
    end

    subgraph WALLET["Wallet"]
        MM["MetaMask<br/>Transaction Signing"]
    end

    subgraph CHAIN["Blockchain Layer (Sepolia Testnet)"]
        C1["RoleManager.sol<br/>Roles + Emergency Pause"]
        C2["InvoiceRegistry.sol<br/>Invoice Registration + Deduplication"]
        C3["ReceivableToken.sol (ERC-1155)<br/>Receivable Mint / Split / Freeze"]
        C4["FinancingPool.sol<br/>Request / Quote / Atomic Funding / Repay / Redeem"]
        C5["MockStablecoin.sol (ERC-20)<br/>Test Stablecoin mUSD + faucet"]
    end

    subgraph BE["Backend Layer (Python Flask, Render)"]
        B1["REST API<br/>Enterprises / Invoices / Receivables / Financing / Dashboard / Audit"]
        B2["Web3.py Event Listener<br/>On-chain Event Sync"]
        B3["File Storage<br/>Invoice PDF (off-chain) + SHA-256 Hash"]
    end

    subgraph DB["Data Layer (SQLite / PostgreSQL, 7 Tables)"]
        D1["enterprises · invoices · holdings<br/>financing_requests · quotes<br/>chain_events · sync_state"]
    end

    U --> FE
    FE -->|"Ethers.js submits transactions"| MM
    MM -->|"Signed & broadcast"| CHAIN
    FE -->|"REST queries (off-chain data / cache)"| B1
    CHAIN -->|"On-chain events"| B2
    B2 --> D1
    B1 --> D1
    B1 --> B3
    C1 -.->|"Access control"| C2
    C2 -.->|"Mint on confirmation"| C3
    C4 -.->|"Transfer / Burn tokens"| C3
    C4 -.->|"mUSD settlement"| C5
```

</details>

## 02. Contract Interaction (Sequence)

Invoice registration -> confirmation & minting -> split transfer -> financing request -> quote locking -> atomic funding -> repayment -> redemption / overdue.

![Contract Interaction](02-contract-interaction.png)

<details><summary>mermaid source</summary>

```mermaid
sequenceDiagram
    autonumber
    actor S as Supplier
    actor CE as Core Enterprise
    actor F as Financier
    participant IR as InvoiceRegistry
    participant RT as ReceivableToken<br/>(ERC-1155)
    participant FP as FinancingPool
    participant USD as MockStablecoin<br/>(ERC-20)

    Note over S,IR: 1. Invoice Registration (1st gate against duplicate financing)
    S->>IR: submitInvoice(invoiceNo, buyer, amount, dueDate, fileHash)
    alt Dedup key invoiceNo+buyer+supplier+amount already exists
        IR-->>S: revert InvoiceAlreadyExists
    else First registration
        IR-->>S: emit InvoiceSubmitted
    end

    Note over CE,RT: 2. Confirmation mints an equal-value receivable
    CE->>IR: confirmInvoice(invoiceId)
    IR->>RT: mint(supplier, receivableId, amount)
    RT-->>CE: emit InvoiceConfirmed + ReceivableMinted

    Note over S,RT: 3. Split Transfer (optional, credit flows downstream)
    S->>RT: transferReceivable(to, id, amount)
    RT-->>S: emit ReceivableTransferred

    Note over S,FP: 4. Financing Request (token escrowed into the pool)
    S->>FP: requestFinancing(id, amount)
    FP->>RT: Escrow transfer (TransferSingle to pool)

    Note over F,FP: 5. Quote (discount rate in bps, funds locked)
    F->>USD: approve(pool, payout)
    F->>FP: submitQuote(requestId, discountBps)
    FP->>USD: Lock quote funds

    Note over S,USD: 6. Accept Quote: atomic funding (all-or-nothing)
    S->>FP: acceptQuote(requestId, quoteId)
    FP->>RT: Token ownership -> Financier
    FP->>USD: Discounted payout -> Supplier
    FP-->>S: emit FinancingFunded

    Note over CE,FP: 7. Repayment at Maturity
    CE->>USD: approve(pool, faceValue)
    CE->>FP: repay(id)
    FP-->>CE: emit Repaid

    Note over F,FP: 8. Redemption (1:1 burn for mUSD)
    F->>FP: redeem(id)
    FP->>RT: Burn tokens
    FP->>USD: Face value -> Holder
    FP-->>F: emit Redeemed

    Note over F,FP: 9. Overdue: financier marks it on-chain
    F->>FP: markOverdue(id)
    FP-->>F: emit MarkedOverdue (visible on dashboards)
```

</details>

## 03. Data Model (ER)

The backend's 7 tables: enterprises, invoices, holdings, financing requests, quotes, chain events, and the sync cursor.

![Data Model](03-data-model.png)

<details><summary>mermaid source</summary>

```mermaid
erDiagram
    ENTERPRISES ||--o{ INVOICES : "issues as supplier"
    ENTERPRISES ||--o{ INVOICES : "confirms as core enterprise"
    INVOICES ||--|| HOLDINGS : "confirmed invoice becomes holding"
    HOLDINGS ||--o{ FINANCING_REQUESTS : "financed via request"
    FINANCING_REQUESTS ||--o{ QUOTES : "receives quotes"
    ENTERPRISES ||--o{ QUOTES : "submits as financier"

    ENTERPRISES {
        int id PK
        string wallet_address "unique wallet address"
        string company_name
        string contact
        string role "applied role Supplier/Core/Financier"
        string status "pending / approved / rejected"
        string reject_reason
        string grant_tx_hash "on-chain grant tx hash"
    }

    INVOICES {
        int id PK
        int onchain_invoice_id
        string invoice_no "from InvoiceSubmitted event"
        string supplier
        string buyer
        int amount "mUSD smallest unit"
        date due_date
        string file_hash "SHA-256 of PDF"
        string file_path "off-chain file path"
        string status "Pending / Confirmed / Rejected"
    }

    HOLDINGS {
        int id PK
        int receivable_id "ERC-1155 tokenId"
        string holder
        int balance "held share balance"
    }

    FINANCING_REQUESTS {
        int id PK
        int onchain_request_id
        int receivable_id
        string supplier
        int amount
        string status "Open / Funded / Cancelled"
        int accepted_quote_id
    }

    QUOTES {
        int id PK
        int onchain_quote_id
        int request_id
        string funder
        int discount_bps "basis points, 1/10000"
        int payout "actual payout amount"
        string status "Active / Accepted / Withdrawn"
    }

    CHAIN_EVENTS {
        int id PK
        int block_number
        string tx_hash
        string contract_name
        string event_name
        json args "decoded event args"
        datetime created_at
    }

    SYNC_STATE {
        string contract_name PK
        int last_block "last synced block height"
    }
```

</details>

## 04. Business Flow

Core flow: upload -> on-chain dedup -> core-enterprise confirmation -> token minting -> split / finance / hold -> quote & settlement -> repayment -> redemption loop, with reject, cancel, overdue, and freeze branches.

![Business Flow](04-business-flow.png)

<details><summary>mermaid source</summary>

```mermaid
flowchart TD
    START([Supplier issues invoice]) --> UPLOAD["Upload invoice metadata + PDF<br/>SHA-256 file hash on-chain"]
    UPLOAD --> DEDUP{"On-chain dedup check<br/>invoiceNo + buyer + seller + amount"}
    DEDUP -->|Exists| REJECT_DUP["Contract reverts<br/>InvoiceAlreadyExists"] --> END1([Process ends])
    DEDUP -->|Passed| PENDING["Status: Pending<br/>PDF off-chain, hash on-chain"]

    PENDING --> CE{"Core enterprise verifies"}
    CE -->|"Reject (reason required)"| REJECTED["Status: Rejected<br/>dedup key released, resubmittable"] --> END2([Process ends])
    CE -->|Confirm| MINT["Equal-value ERC-1155 receivable minted<br/>credit rights established"]

    MINT --> CHOICE{"Supplier chooses"}
    CHOICE -->|Split transfer| SPLIT["Transfer shares to a tier-2 supplier<br/>(registered suppliers only; not frozen/matured)"] --> CHOICE
    CHOICE -->|Hold to maturity| HOLD["Wait for core enterprise payment"]
    CHOICE -->|Request financing| RF["Request financing<br/>token auto-escrowed (no double pledge)"]

    RF --> QUOTE["Financiers quote (discount bps)<br/>quote funds locked in pool"]
    QUOTE --> ACCEPT{"Supplier picks a quote"}
    ACCEPT -->|Accept| FUND["Atomic funding: one tx moves<br/>token -> financier, funds -> supplier"]
    ACCEPT -->|Cancel request| CANCEL["Token returned to supplier"] --> CHOICE

    FUND --> DUE{"Maturity check"}
    DUE -->|Repaid on time| REPAY["Face value paid into pool"]
    DUE -->|Overdue| OVERDUE["Financier marks overdue<br/>recorded on-chain"] --> REPAY2["Payment still accepted after overdue"]
    REPAY2 --> REPAY

    REPAY --> REDEEM["Current holder burns token<br/>redeems mUSD 1:1"]
    REDEEM --> END3([Loop closed])

    FREEZE_NOTE["Auditor can freeze/unfreeze anytime<br/>frozen: no transfer, financing, or redemption"] -.-> MINT
```

</details>

## 05. UI Navigation

Navigation across the 19 pages/views: landing & wallet connect -> role check -> per-role workspaces -> shared transaction history and event logs.

![UI Navigation](05-ui-navigation.png)

<details><summary>mermaid source</summary>

```mermaid
flowchart TD
    LANDING["Landing Page<br/>Product intro · Connect MetaMask"] --> CHECK{"On-chain role check<br/>isRegistered + roleOf"}
    CHECK -->|Not registered| REG["Registration Page<br/>Company profile · Role selection<br/>Awaiting admin review"]
    REG -.->|"Approved & role granted on-chain"| CHECK
    CHECK -->|Supplier| S1["Supplier Dashboard<br/>Receivables / Funded / To-dos"]
    CHECK -->|Core Enterprise| C1["Core Enterprise Dashboard<br/>Pending count / Payables / Due soon alerts"]
    CHECK -->|Financier| F1["Financier Dashboard<br/>Funded / Receivables / Overdue monitor"]
    CHECK -->|Auditor| A1["Global Audit Board<br/>Invoices / Transfer volume / Overdue rate"]
    CHECK -->|Admin| AD1["Registration Review<br/>On-chain approve / reject"]

    S1 --> S2["Upload Invoice"]
    S1 --> S3["My Invoices<br/>Status filter · PDF verification"]
    S1 --> S4["My Receivables<br/>Split transfer · Request financing"]
    S1 --> S5["My Financing<br/>Review quotes · Accept / Cancel"]
    S4 --> S2

    C1 --> C2["Pending Invoices<br/>Preview PDF · Confirm / Reject"]
    C1 --> C3["Payables Ledger<br/>Sorted by due date · One-click repay"]

    F1 --> F2["Financing Market<br/>Open requests · Quote with discount rate"]
    F1 --> F3["My Funded Assets<br/>Redeem at maturity · Mark overdue"]

    A1 --> A2["Receivable Provenance<br/>Lifecycle tree · Freeze / Unfreeze"]

    AD1 --> AD2["Roles & System Control<br/>Revoke roles · Emergency pause / unpause"]

    S1 --> PUB["Transaction History (all roles)"]
    C1 --> PUB
    F1 --> PUB
    A1 --> PUB
    AD1 --> PUB
    PUB --> EV["Contract Event Logs (Admin / Auditor)<br/>Filter by type / time / address"]
```

</details>
