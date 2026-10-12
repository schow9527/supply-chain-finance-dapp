/**
 * UI Feedback & 4-Stage Transaction Lifecycle Manager
 * Handles: Toast notifications, Confirmation dialogs, and 4-Stage Tx Lifecycle Modal (F-26).
 * Aligned with Custom Errors from Member 1's contracts.
 */
(function (root, factory) {
    if (typeof module === "object" && module.exports) {
        module.exports = factory();
    } else {
        root.UIFeedback = factory();
    }
}(typeof self !== "undefined" ? self : this, function () {

    const TX_STAGES = {
        ESTIMATING: "ESTIMATING",         // 1. Gas estimation
        WAITING_WALLET: "WAITING_WALLET", // 2. Waiting for wallet confirmation
        CONFIRMING: "CONFIRMING",         // 3. Confirming on-chain
        SUCCESS: "SUCCESS",               // 4. Transaction successful
        FAILED: "FAILED"                  // 4. Transaction failed
    };

    const CUSTOM_ERROR_MESSAGES = {
        "SafeCastOverflowedUintDowncast": "Input amount is too large and exceeds system capacity.",
        "SystemPaused": "System is currently in emergency pause. Write operations are blocked.",
        "EnforcedPause": "System is currently in emergency pause. Write operations are blocked.",
        "Unauthorized": "Current account is not authorized to perform this action.",
        "AccessControlUnauthorizedAccount": "Unauthorized: Current account lacks the required contract role.",
        "AccountAlreadyHasRole": "This account already holds an on-chain role and cannot be granted repeatedly.",
        "InvoiceAlreadyExists": "Duplicate rejected: This invoice number and buyer combination is already registered on-chain.",
        "InvoiceNotFound": "Invoice record not found.",
        "InvoiceNotPending": "Invoice status does not allow this action.",
        "NotInvoiceBuyer": "Authorization failed: The accepting buyer for this invoice is not the current account.",
        "InvalidBuyer": "The buyer must be a core enterprise registered on the platform.",
        "InvalidAmount": "Amount must be greater than zero.",
        "InvalidDueDate": "Invoice due date must be in the future.",
        "InvalidFileHash": "Invalid file hash.",
        "InvalidInvoiceNo": "Invoice number cannot be empty.",
        "InvalidRecipient": "Transfer recipient must be a registered supplier account.",
        "ReceivableIsFrozen": "This receivable token has been frozen by an auditor. Transfer, financing, and redemption are disabled.",
        "ReceivableMatured": "This receivable token has passed its due date.",
        "ReceivableNotActive": "Receivable token is not active.",
        "ReceivableNotFinanceable": "This receivable token is currently ineligible for financing.",
        "NotOverdueYet": "Invoice has not passed its due date and cannot be marked overdue.",
        "QuoteNotActive": "This quote is expired or has been revoked.",
        "QuoteNotFound": "Quote record not found.",
        "RequestNotFound": "Financing request not found.",
        "RequestNotOpen": "This financing request has been cancelled or already funded.",
        "NotRequestOwner": "Only the supplier who created the financing request can perform this action.",
        "NotQuoteOwner": "Only the funder who submitted the quote can revoke it.",
        "NotReceivableBuyer": "Only the core enterprise buyer can repay this receivable token.",
        "NotRepayable": "This receivable cannot be repaid or has already been settled.",
        "NotRedeemable": "The core enterprise has not repaid yet; the pool cannot be redeemed.",
        "NothingToRedeem": "Current account holds no redeemable balance for this token.",
        "ERC1155InsufficientBalance": "Insufficient receivable token balance.",
        "ERC20InsufficientBalance": "Insufficient mUSD stablecoin balance.",
        "ERC20InsufficientAllowance": "Insufficient mUSD allowance. Please approve tokens first.",
        "ReasonRequired": "Please provide a reason."
    };

    /**
     * Translates revert reason, custom error, or RPC error into friendly message
     */
    function parseBlockchainError(err) {
        if (!err) return "Unknown error";
        const message = err.message || String(err);
        
        // Check user rejection
        if (err.code === "ACTION_REJECTED" || message.includes("user rejected") || message.includes("User denied")) {
            return "Transaction signature was cancelled in MetaMask.";
        }

        // Check custom error from ethers v6 (error.revert?.name)
        const customName = err.revert?.name || (err.info?.error?.data?.name);
        if (customName && CUSTOM_ERROR_MESSAGES[customName]) {
            return CUSTOM_ERROR_MESSAGES[customName];
        }

        // Check matching error name in message string
        for (const [key, text] of Object.entries(CUSTOM_ERROR_MESSAGES)) {
            if (message.includes(key)) {
                return text;
            }
        }

        if (message.includes("insufficient funds for gas") || message.includes("insufficient funds")) {
            return "Insufficient Sepolia ETH in wallet to pay gas fees.";
        }

        return message.length > 120 ? message.slice(0, 120) + "..." : message;
    }

    class TxLifecycleModal {
        constructor() {
            this.currentStage = null;
            this.txHash = null;
            this.gasEstimate = null;
        }

        render() {
            if (typeof document === "undefined") return;
            let el = document.getElementById("tx-lifecycle-modal");
            if (!el) {
                el = document.createElement("div");
                el.id = "tx-lifecycle-modal";
                el.className = "modal-overlay hidden";
                el.innerHTML = `
                    <div class="modal-box tx-modal">
                        <div class="modal-header">
                            <h3 id="tx-modal-title">Transaction in Progress</h3>
                            <button class="modal-close-btn" onclick="UIFeedback.txModal.close()">×</button>
                        </div>
                        <div class="modal-body">
                            <!-- Step indicator -->
                            <div class="step-wizard">
                                <div id="step-1" class="step-item">1. Estimate Gas</div>
                                <div id="step-2" class="step-item">2. Wallet Confirm</div>
                                <div id="step-3" class="step-item">3. On-Chain Confirm</div>
                                <div id="step-4" class="step-item">4. Complete</div>
                            </div>

                            <div class="tx-stage-content" id="tx-stage-content">
                                <div class="spinner-wrapper"><div class="spinner"></div></div>
                                <p id="tx-status-desc">Processing...</p>
                            </div>

                            <div id="tx-details-box" class="tx-details hidden">
                                <div><strong>Estimated Fee: </strong><span id="tx-gas-text">-</span></div>
                                <div id="tx-hash-row" class="hidden"><strong>Transaction Hash: </strong><a id="tx-hash-link" target="_blank" href="#">-</a></div>
                            </div>
                        </div>
                        <div class="modal-footer" id="tx-modal-footer">
                            <button id="tx-modal-action-btn" class="btn btn-secondary" onclick="UIFeedback.txModal.close()">Close</button>
                        </div>
                    </div>
                `;
                document.body.appendChild(el);
            }
            return el;
        }

        setStage(stage, payload = {}) {
            this.currentStage = stage;
            this.render();
            const modal = document.getElementById("tx-lifecycle-modal");
            if (!modal) return;

            modal.classList.remove("hidden");
            const titleEl = document.getElementById("tx-modal-title");
            const descEl = document.getElementById("tx-status-desc");
            const detailsEl = document.getElementById("tx-details-box");
            const gasEl = document.getElementById("tx-gas-text");
            const hashRowEl = document.getElementById("tx-hash-row");
            const hashLinkEl = document.getElementById("tx-hash-link");
            const actionBtn = document.getElementById("tx-modal-action-btn");

            // Update step highlights
            [1, 2, 3, 4].forEach(i => {
                const s = document.getElementById(`step-${i}`);
                if (s) s.className = "step-item";
            });

            if (stage === TX_STAGES.ESTIMATING) {
                // Reset spinner if replaced by icon in previous tx
                const spinnerWrapper = document.querySelector(".spinner-wrapper");
                if (spinnerWrapper) spinnerWrapper.innerHTML = '<div class="spinner"></div>';
                document.getElementById("step-1")?.classList.add("active");
                titleEl.innerText = "Stage 1: Gas Fee Estimation (F-26)";
                descEl.innerText = "Estimating transaction Gas Limit and fees on Sepolia testnet...";
                detailsEl.classList.remove("hidden");
                gasEl.innerText = payload.gas ? `${payload.gas} Gas` : "Calculating...";
                hashRowEl.classList.add("hidden");
                actionBtn.classList.add("hidden");
            } else if (stage === TX_STAGES.WAITING_WALLET) {
                document.getElementById("step-1")?.classList.add("done");
                document.getElementById("step-2")?.classList.add("active");
                titleEl.innerText = "Stage 2: Waiting for MetaMask Confirmation";
                descEl.innerText = "Please review and confirm the transaction in MetaMask...";
                if (payload.gas) gasEl.innerText = `${payload.gas} Gas (approx. ${payload.eth || "~0.001"} ETH)`;
                actionBtn.classList.add("hidden");
            } else if (stage === TX_STAGES.CONFIRMING) {
                document.getElementById("step-1")?.classList.add("done");
                document.getElementById("step-2")?.classList.add("done");
                document.getElementById("step-3")?.classList.add("active");
                titleEl.innerText = "Stage 3: Transaction Broadcasted, Mining";
                descEl.innerText = "Transaction broadcasted to Ethereum testnet. Waiting for block confirmation...";
                if (payload.txHash) {
                    hashRowEl.classList.remove("hidden");
                    hashLinkEl.innerText = `${payload.txHash.slice(0, 10)}...${payload.txHash.slice(-8)}`;
                    hashLinkEl.href = `https://sepolia.etherscan.io/tx/${payload.txHash}`;
                }
                actionBtn.classList.add("hidden");
            } else if (stage === TX_STAGES.SUCCESS) {
                [1, 2, 3, 4].forEach(i => document.getElementById(`step-${i}`)?.classList.add("done"));
                titleEl.innerText = "Stage 4: Transaction Successful! 🎉";
                const spinnerWrapper = document.querySelector(".spinner-wrapper");
                if (spinnerWrapper) spinnerWrapper.innerHTML = '<div style="font-size:3rem;text-align:center;">✅</div>';
                descEl.innerHTML = `<span style="color:#10b981;font-weight:600;">${payload.message || "On-chain transaction confirmed successfully!"}</span>`;
                actionBtn.classList.remove("hidden");
                actionBtn.innerText = "Done & Close";
            } else if (stage === TX_STAGES.FAILED) {
                titleEl.innerText = "Transaction Failed / Rejected ⚠️";
                const spinnerWrapper = document.querySelector(".spinner-wrapper");
                if (spinnerWrapper) spinnerWrapper.innerHTML = '<div style="font-size:3rem;text-align:center;">❌</div>';
                const errMsg = parseBlockchainError(payload.error);
                descEl.innerHTML = `<span style="color:#ef4444;font-weight:600;">${errMsg}</span>`;
                actionBtn.classList.remove("hidden");
                actionBtn.innerText = "Dismiss";
            }
        }

        close() {
            const modal = document.getElementById("tx-lifecycle-modal");
            if (modal) modal.classList.add("hidden");
        }
    }

    const txModal = new TxLifecycleModal();

    function showToast(message, type = "info", duration = 3500) {
        if (typeof document === "undefined") return;
        let container = document.getElementById("toast-container");
        if (!container) {
            container = document.createElement("div");
            container.id = "toast-container";
            container.className = "toast-container";
            document.body.appendChild(container);
        }

        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        const icons = { info: "ℹ️", success: "✅", warning: "⚠️", error: "❌" };
        toast.innerHTML = `<span class="toast-icon">${icons[type] || ""}</span><span>${message}</span>`;
        container.appendChild(toast);

        setTimeout(() => {
            toast.classList.add("fade-out");
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    return {
        TX_STAGES,
        CUSTOM_ERROR_MESSAGES,
        parseBlockchainError,
        txModal,
        showToast
    };
}));
