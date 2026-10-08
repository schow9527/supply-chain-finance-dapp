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
        async executeWithLifecycle(contractName, methodName, args = [], successMsg = "交易已成功上链！") {
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
            return this.executeWithLifecycle("RoleManager", "grantRole", [roleBytes32, account], "已成功为企业分配链上角色！");
        }

        async revokeRole(roleBytes32, account) {
            return this.executeWithLifecycle("RoleManager", "revokeRole", [roleBytes32, account], "已成功撤销该账户角色！");
        }

        async pauseSystem() {
            return this.executeWithLifecycle("RoleManager", "pause", [], "系统已成功进入紧急熔断暂停状态！");
        }

        async unpauseSystem() {
            return this.executeWithLifecycle("RoleManager", "unpause", [], "系统已成功解除暂停，恢复正常！");
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
                "发票已成功提交上链登记！"
            );
        }

        async confirmInvoice(invoiceId) {
            return this.executeWithLifecycle("InvoiceRegistry", "confirmInvoice", [invoiceId], "发票已确认，等额应收凭证已自动铸造！");
        }

        async rejectInvoice(invoiceId, reason) {
            return this.executeWithLifecycle("InvoiceRegistry", "rejectInvoice", [invoiceId, reason], "发票已拒绝。");
        }

        // ==================== 3. ReceivableToken Functions ====================
        async transferReceivable(to, id, amount) {
            return this.executeWithLifecycle("ReceivableToken", "transferReceivable", [to, id, amount], "凭证拆分转让成功！");
        }

        async freezeReceivable(id, reason) {
            return this.executeWithLifecycle("ReceivableToken", "freeze", [id, reason], "凭证已被审计员链上冻结！");
        }

        async unfreezeReceivable(id, reason = "经审查核实无误解除冻结") {
            return this.executeWithLifecycle("ReceivableToken", "unfreeze", [id, reason], "凭证已成功解除冻结！");
        }

        // ==================== 4. FinancingPool Functions ====================
        async requestFinancing(receivableId, amount) {
            return this.executeWithLifecycle("FinancingPool", "requestFinancing", [receivableId, amount], "融资申请已成功提交，凭证已托管至资金池！");
        }

        async submitQuote(requestId, discountBps) {
            return this.executeWithLifecycle("FinancingPool", "submitQuote", [requestId, discountBps], "报价已成功提交并锁定放款资金！");
        }

        async withdrawQuote(quoteId) {
            return this.executeWithLifecycle("FinancingPool", "withdrawQuote", [quoteId], "报价已撤回，锁定资金已退回钱包！");
        }

        async acceptQuote(requestId, quoteId) {
            return this.executeWithLifecycle("FinancingPool", "acceptQuote", [requestId, quoteId], "已成功接受报价，放款资金已当场到账！");
        }

        async cancelFinancingRequest(requestId) {
            return this.executeWithLifecycle("FinancingPool", "cancelRequest", [requestId], "融资申请已取消，托管凭证已退回。");
        }

        async repayInvoice(receivableId) {
            return this.executeWithLifecycle("FinancingPool", "repay", [receivableId], "到期还款已结清！");
        }

        async redeemReceivable(receivableId) {
            return this.executeWithLifecycle("FinancingPool", "redeem", [receivableId], "凭证已销毁，1:1 稳定币兑付已到账！");
        }

        async markOverdue(receivableId) {
            return this.executeWithLifecycle("FinancingPool", "markOverdue", [receivableId], "已标记为逾期账款！");
        }

        // ==================== 5. MockStablecoin Functions ====================
        async claimFaucet() {
            return this.executeWithLifecycle("MockStablecoin", "faucet", [], "已成功领取 100,000 mUSD 测试代币！");
        }

        async approveStablecoin(spender, amount) {
            return this.executeWithLifecycle("MockStablecoin", "approve", [spender, amount], "稳定币扣款授权成功！");
        }
    }

    return ContractClient;
}));
