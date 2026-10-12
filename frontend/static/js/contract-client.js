/**
 * ContractClient: High-level wrapper for 5 smart contracts and 20 on-chain transactions.
 * Aligned with Member 1's deployed Sepolia contracts (Foundry).
 * Automatically wraps calls with the 4-stage UI lifecycle modal (F-26).
 */
(function (root, factory) {
    if (typeof module === "object" && module.exports) {
        module.exports = factory();
    } else {
        root.ContractClient = factory();
    }
}(typeof self !== "undefined" ? self : this, function () {

    class ContractClient {
        constructor(provider, signer, addresses = {}, abis = {}) {
            this.provider = provider;
            this.signer = signer;
            this.addresses = addresses;
            this.abis = abis;
            this.contracts = {};

            if (provider && signer) {
                this._initContracts();
            }
        }

        _initContracts() {
            if (typeof ethers === "undefined") return;
            const names = ["RoleManager", "ReceivableToken", "InvoiceRegistry", "FinancingPool", "MockStablecoin"];
            names.forEach(name => {
                if (this.addresses[name] && this.abis[name]) {
                    this.contracts[name] = new ethers.Contract(
                        this.addresses[name],
                        this.abis[name],
                        this.signer || this.provider
                    );
                }
            });
        }

        /**
         * Generic runner executing transaction across 4 stages with UI feedback
         */
        async executeWithLifecycle(contractName, methodName, args = [], successMsg = "Transaction confirmed successfully on-chain!") {
            const feedback = typeof window !== "undefined" && window.UIFeedback ? window.UIFeedback : null;
            const contract = this.contracts[contractName];
            if (!contract) {
                throw new Error(`Contract ${contractName} not initialized. Check deployed address.`);
            }

            try {
                // Stage 1: Estimating Gas (F-26)
                if (feedback) {
                    feedback.txModal.setStage(feedback.TX_STAGES.ESTIMATING);
                }
                const gasEstimate = await contract[methodName].estimateGas(...args).catch(() => 300000n);
                const feeData = await this.provider.getFeeData().catch(() => ({ gasPrice: 20000000000n }));
                const gasCostWei = gasEstimate * (feeData.gasPrice || 20000000000n);
                const gasCostEth = (Number(gasCostWei) / 1e18).toFixed(5);

                // Stage 2: Waiting for MetaMask confirmation
                if (feedback) {
                    feedback.txModal.setStage(feedback.TX_STAGES.WAITING_WALLET, {
                        gas: gasEstimate.toString(),
                        eth: gasCostEth
                    });
                }

                // Trigger transaction
                const tx = await contract[methodName](...args);

                // Stage 3: Confirming on-chain
                if (feedback) {
                    feedback.txModal.setStage(feedback.TX_STAGES.CONFIRMING, { txHash: tx.hash });
                }

                const receipt = await tx.wait(1);

                // Stage 4: Success
                if (feedback) {
                    feedback.txModal.setStage(feedback.TX_STAGES.SUCCESS, {
                        message: successMsg,
                        txHash: receipt.hash
                    });
                }

                return receipt;
            } catch (err) {
                console.error(`Error executing ${contractName}.${methodName}:`, err);
                if (feedback) {
                    feedback.txModal.setStage(feedback.TX_STAGES.FAILED, { error: err });
                }
                throw err;
            }
        }

        // ==================== 1. RoleManager Functions ====================
        async grantRole(roleBytes32, account) {
            return this.executeWithLifecycle("RoleManager", "grantRole", [roleBytes32, account], "Role granted successfully on-chain!");
        }

        async revokeRole(roleBytes32, account) {
            return this.executeWithLifecycle("RoleManager", "revokeRole", [roleBytes32, account], "Role revoked successfully on-chain!");
        }

        async pauseSystem() {
            return this.executeWithLifecycle("RoleManager", "pause", [], "System has entered emergency pause state!");
        }

        async unpauseSystem() {
            return this.executeWithLifecycle("RoleManager", "unpause", [], "System has been unpaused and restored to normal!");
        }

        async isRegistered(account) {
            return this.contracts.RoleManager.isRegistered(account);
        }

        async roleOf(account) {
            return this.contracts.RoleManager.roleOf(account);
        }

        // ==================== 2. InvoiceRegistry Functions ====================
        // Note signature: (invoiceNo, buyer, amount, dueDate, fileHash)
        async submitInvoice(invoiceNo, buyer, amountUnits, dueDateTs, fileHashBytes32) {
            return this.executeWithLifecycle(
                "InvoiceRegistry",
                "submitInvoice",
                [invoiceNo, buyer, amountUnits, dueDateTs, fileHashBytes32],
                "Invoice registered successfully on-chain!"
            );
        }

        async confirmInvoice(invoiceId) {
            return this.executeWithLifecycle("InvoiceRegistry", "confirmInvoice", [invoiceId], "Invoice confirmed! Equivalent receivable token has been minted.");
        }

        async rejectInvoice(invoiceId, reason) {
            return this.executeWithLifecycle("InvoiceRegistry", "rejectInvoice", [invoiceId, reason], "Invoice has been rejected.");
        }

        // ==================== 3. ReceivableToken Functions ====================
        async transferReceivable(to, id, amount) {
            return this.executeWithLifecycle("ReceivableToken", "transferReceivable", [to, id, amount], "Receivable token split and transferred successfully!");
        }

        async freezeReceivable(id, reason) {
            return this.executeWithLifecycle("ReceivableToken", "freeze", [id, reason], "Receivable token has been frozen on-chain by auditor!");
        }

        async unfreezeReceivable(id, reason = "Verified and unfrozen") {
            return this.executeWithLifecycle("ReceivableToken", "unfreeze", [id, reason], "Receivable token has been unfrozen successfully!");
        }

        // ==================== 4. FinancingPool Functions ====================
        async requestFinancing(receivableId, amount) {
            return this.executeWithLifecycle("FinancingPool", "requestFinancing", [receivableId, amount], "Financing request submitted! Token escrowed into pool.");
        }

        async submitQuote(requestId, discountBps) {
            return this.executeWithLifecycle("FinancingPool", "submitQuote", [requestId, discountBps], "Quote submitted and funding locked successfully!");
        }

        async withdrawQuote(quoteId) {
            return this.executeWithLifecycle("FinancingPool", "withdrawQuote", [quoteId], "Quote withdrawn. Locked funds returned to wallet!");
        }

        async acceptQuote(requestId, quoteId) {
            return this.executeWithLifecycle("FinancingPool", "acceptQuote", [requestId, quoteId], "Quote accepted! Funds disbursed to wallet immediately!");
        }

        async cancelFinancingRequest(requestId) {
            return this.executeWithLifecycle("FinancingPool", "cancelRequest", [requestId], "Financing request cancelled. Escrowed token returned.");
        }

        async repayInvoice(receivableId) {
            return this.executeWithLifecycle("FinancingPool", "repay", [receivableId], "Due payment settled successfully!");
        }

        async redeemReceivable(receivableId) {
            return this.executeWithLifecycle("FinancingPool", "redeem", [receivableId], "Token burned! 1:1 mUSD redemption credited to wallet!");
        }

        async markOverdue(receivableId) {
            return this.executeWithLifecycle("FinancingPool", "markOverdue", [receivableId], "Marked as overdue on-chain!");
        }

        // ==================== 5. MockStablecoin Functions ====================
        async claimFaucet() {
            return this.executeWithLifecycle("MockStablecoin", "faucet", [], "Successfully claimed 100,000 mUSD test tokens!");
        }

        async approveStablecoin(spender, amount) {
            return this.executeWithLifecycle("MockStablecoin", "approve", [spender, amount], "mUSD allowance approved successfully!");
        }
    }

    return ContractClient;
}));
