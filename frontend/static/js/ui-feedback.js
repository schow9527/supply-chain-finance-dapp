/**
 * UI Feedback & 4-Stage Transaction Lifecycle Manager
 * Handles: Toast notifications, Confirmation dialogs, and 4-Stage Tx Lifecycle Modal (F-26).
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

    /**
     * Translates revert reason or RPC error into friendly message
     */
    function parseBlockchainError(err) {
        if (!err) return "未知错误";
        const message = err.message || String(err);
        
        if (err.code === "ACTION_REJECTED" || message.includes("user rejected") || message.includes("User denied")) {
            return "用户已在 MetaMask 中取消了交易签名。";
        }
        if (message.includes("Invoice already registered")) {
            return "防重拦截：该发票号、买家与金额组合已被登记，无法重复上链！";
        }
        if (message.includes("System is paused")) {
            return "系统当前处于紧急暂停状态，暂停所有写操作。";
        }
        if (message.includes("Receivable is frozen")) {
            return "该应收账款凭证已被审计员冻结，暂不可流转、融资或兑付。";
        }
        if (message.includes("Insufficient balance") || message.includes("insufficient funds")) {
            return "钱包余额不足或凭证持有份额不足。";
        }
        if (message.includes("Only core enterprise can repay") || message.includes("Only buyer can confirm")) {
            return "权限校验失败：当前账户非该发票对应的核心企业买方。";
        }
        if (message.includes("Discount rate must be < 100%")) {
            return "贴现率必须小于 100% (10000 基点)。";
        }
        if (message.includes("Due date must be in future")) {
            return "发票到期日必须晚于当前时间。";
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
                descEl.innerHTML = `<span style="color:#10b981;font-weight:600;">${payload.message || "链上交易已顺利确认！"}</span>`;
                actionBtn.classList.remove("hidden");
                actionBtn.innerText = "完成并关闭";
            } else if (stage === TX_STAGES.FAILED) {
                titleEl.innerText = "交易未完成 / 失败 ⚠️";
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
        parseBlockchainError,
        txModal,
        showToast
    };
}));
