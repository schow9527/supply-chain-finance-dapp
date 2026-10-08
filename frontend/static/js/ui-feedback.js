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
        ESTIMATING: "ESTIMATING",      // 1. Gas 预估
        WAITING_WALLET: "WAITING_WALLET", // 2. 等待钱包确认
        CONFIRMING: "CONFIRMING",      // 3. 链上确认中
        SUCCESS: "SUCCESS",            // 4. 交易成功
        FAILED: "FAILED"               // 4. 交易失败
    };

    const CUSTOM_ERROR_MESSAGES = {
        "SafeCastOverflowedUintDowncast": "输入金额过大，超出了系统所允许的最大限度。",
        "SystemPaused": "系统当前处于紧急暂停状态，写操作已被熔断。",
        "EnforcedPause": "系统当前处于紧急暂停状态，写操作已被熔断。",
        "Unauthorized": "当前账户没有执行该操作的权限。",
        "AccessControlUnauthorizedAccount": "权限不足：当前账户未被授予该合约角色。",
        "AccountAlreadyHasRole": "该账户已经拥有链上角色，不能重复授予。",
        "InvoiceAlreadyExists": "防重拦截：该发票号与承兑买方组合已在链上登记，禁止重复提交。",
        "InvoiceNotFound": "未找到指定编号的发票记录。",
        "InvoiceNotPending": "发票当前状态不允许执行此操作。",
        "NotInvoiceBuyer": "权限校验失败：该发票开具的承兑买方并非当前账户。",
        "InvalidBuyer": "采购方必须是已在平台注册的核心企业。",
        "InvalidAmount": "金额必须大于 0。",
        "InvalidDueDate": "发票到期日必须晚于当前时间。",
        "InvalidFileHash": "文件哈希值无效。",
        "InvalidInvoiceNo": "发票编号不能为空。",
        "InvalidRecipient": "转让接收方必须是已注册的供应商账户。",
        "ReceivableIsFrozen": "该应收凭证已被审计员链上冻结，禁止流转、贴现或兑付。",
        "ReceivableMatured": "该凭证已超过到期日。",
        "ReceivableNotActive": "凭证当前状态不可用。",
        "ReceivableNotFinanceable": "该凭证当前状态不可申请融资。",
        "NotOverdueYet": "发票尚未超过到期日，无法标记逾期。",
        "QuoteNotActive": "该报价已失效或已被撤销。",
        "QuoteNotFound": "未找到该报价记录。",
        "RequestNotFound": "未找到该融资申请单。",
        "RequestNotOpen": "该融资申请已被取消或已完成放款。",
        "NotRequestOwner": "只有发起融资的供应商才能操作该申请单。",
        "NotQuoteOwner": "只有报价的资金方才能撤回该报价。",
        "NotReceivableBuyer": "只有核心企业买方才能为该凭证清偿付款。",
        "NotRepayable": "该凭证当前不可还款或已完成清偿。",
        "NotRedeemable": "核心企业尚未付款结清，资金池暂不可兑付。",
        "NothingToRedeem": "当前账户未持有可兑付的凭证余额。",
        "ERC1155InsufficientBalance": "应收凭证持有份额不足。",
        "ERC20InsufficientBalance": "mUSD 稳定币余额不足。",
        "ERC20InsufficientAllowance": "mUSD 稳定币授权额度不足，请先执行授权。",
        "ReasonRequired": "请填写必填的原因说明。"
    };

    /**
     * Translates revert reason, custom error, or RPC error into friendly message
     */
    function parseBlockchainError(err) {
        if (!err) return "未知错误";
        const message = err.message || String(err);
        
        // Check user rejection
        if (err.code === "ACTION_REJECTED" || message.includes("user rejected") || message.includes("User denied")) {
            return "用户已在 MetaMask 中取消了交易签名。";
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
            return "钱包内 Sepolia 测试 ETH 不足，无法支付 Gas 费用。";
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
                            <h3 id="tx-modal-title">链上交易处理中</h3>
                            <button class="modal-close-btn" onclick="UIFeedback.txModal.close()">×</button>
                        </div>
                        <div class="modal-body">
                            <!-- Step indicator -->
                            <div class="step-wizard">
                                <div id="step-1" class="step-item">1. 预估 Gas</div>
                                <div id="step-2" class="step-item">2. 钱包确认</div>
                                <div id="step-3" class="step-item">3. 链上确认</div>
                                <div id="step-4" class="step-item">4. 完成</div>
                            </div>

                            <div class="tx-stage-content" id="tx-stage-content">
                                <div class="spinner-wrapper"><div class="spinner"></div></div>
                                <p id="tx-status-desc">正在处理中...</p>
                            </div>

                            <div id="tx-details-box" class="tx-details hidden">
                                <div><strong>预估费用：</strong><span id="tx-gas-text">-</span></div>
                                <div id="tx-hash-row" class="hidden"><strong>交易哈希：</strong><a id="tx-hash-link" target="_blank" href="#">-</a></div>
                            </div>
                        </div>
                        <div class="modal-footer" id="tx-modal-footer">
                            <button id="tx-modal-action-btn" class="btn btn-secondary" onclick="UIFeedback.txModal.close()">关闭</button>
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
                // 重置 spinner（上一次交易可能把它替换成了图标）
                const spinnerWrapper = document.querySelector(".spinner-wrapper");
                if (spinnerWrapper) spinnerWrapper.innerHTML = '<div class="spinner"></div>';
                document.getElementById("step-1")?.classList.add("active");
                titleEl.innerText = "第一阶段：Gas 费用预估 (F-26)";
                descEl.innerText = "正在向 Sepolia 测试网预估本笔交易的 Gas Limit 与费用...";
                detailsEl.classList.remove("hidden");
                gasEl.innerText = payload.gas ? `${payload.gas} Gas` : "计算中...";
                hashRowEl.classList.add("hidden");
                actionBtn.classList.add("hidden");
            } else if (stage === TX_STAGES.WAITING_WALLET) {
                document.getElementById("step-1")?.classList.add("done");
                document.getElementById("step-2")?.classList.add("active");
                titleEl.innerText = "第二阶段：等待 MetaMask 签名";
                descEl.innerText = "请在弹出的 MetaMask 窗口中核对交易并点击“确认”...";
                if (payload.gas) gasEl.innerText = `${payload.gas} Gas (约 ${payload.eth || "~0.001"} ETH)`;
                actionBtn.classList.add("hidden");
            } else if (stage === TX_STAGES.CONFIRMING) {
                document.getElementById("step-1")?.classList.add("done");
                document.getElementById("step-2")?.classList.add("done");
                document.getElementById("step-3")?.classList.add("active");
                titleEl.innerText = "第三阶段：交易已广播，区块打包中";
                descEl.innerText = "交易已成功广播至以太坊测试网，正在等待矿工确认...";
                if (payload.txHash) {
                    hashRowEl.classList.remove("hidden");
                    hashLinkEl.innerText = `${payload.txHash.slice(0, 10)}...${payload.txHash.slice(-8)}`;
                    hashLinkEl.href = `https://sepolia.etherscan.io/tx/${payload.txHash}`;
                }
                actionBtn.classList.add("hidden");
            } else if (stage === TX_STAGES.SUCCESS) {
                [1, 2, 3, 4].forEach(i => document.getElementById(`step-${i}`)?.classList.add("done"));
                titleEl.innerText = "第四阶段：交易执行成功！🎉";
                const spinnerWrapper = document.querySelector(".spinner-wrapper");
                if (spinnerWrapper) spinnerWrapper.innerHTML = '<div style="font-size:3rem;text-align:center;">✅</div>';
                descEl.innerHTML = `<span style="color:#10b981;font-weight:600;">${payload.message || "链上交易已顺利确认！"}</span>`;
                actionBtn.classList.remove("hidden");
                actionBtn.innerText = "完成并关闭";
            } else if (stage === TX_STAGES.FAILED) {
                titleEl.innerText = "交易未完成 / 失败 ⚠️";
                const spinnerWrapper = document.querySelector(".spinner-wrapper");
                if (spinnerWrapper) spinnerWrapper.innerHTML = '<div style="font-size:3rem;text-align:center;">❌</div>';
                const errMsg = parseBlockchainError(payload.error);
                descEl.innerHTML = `<span style="color:#ef4444;font-weight:600;">${errMsg}</span>`;
                actionBtn.classList.remove("hidden");
                actionBtn.innerText = "知道了";
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
