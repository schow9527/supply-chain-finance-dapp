const test = require("node:test");
const assert = require("node:assert");
const UIFeedback = require("../static/js/ui-feedback.js");

test("UIFeedback - Transaction Stages", () => {
    assert.strictEqual(UIFeedback.TX_STAGES.ESTIMATING, "ESTIMATING");
    assert.strictEqual(UIFeedback.TX_STAGES.WAITING_WALLET, "WAITING_WALLET");
    assert.strictEqual(UIFeedback.TX_STAGES.CONFIRMING, "CONFIRMING");
    assert.strictEqual(UIFeedback.TX_STAGES.SUCCESS, "SUCCESS");
    assert.strictEqual(UIFeedback.TX_STAGES.FAILED, "FAILED");
});

test("UIFeedback - Blockchain Revert Error Parsing", () => {
    // User cancelled in MetaMask
    const userCancelErr = { code: "ACTION_REJECTED", message: "User denied transaction signature" };
    assert.match(UIFeedback.parseBlockchainError(userCancelErr), /用户已在 MetaMask 中取消了交易签名/);

    // Anti-duplicate invoice
    const dupErr = { message: "execution reverted: InvoiceRegistry: Invoice already registered" };
    assert.match(UIFeedback.parseBlockchainError(dupErr), /防重拦截：该发票号、买家与金额组合已被登记/);

    // System paused
    const pauseErr = { message: "execution reverted: RoleManager: System is paused" };
    assert.match(UIFeedback.parseBlockchainError(pauseErr), /系统当前处于紧急暂停状态/);

    // Frozen receivable
    const freezeErr = { message: "execution reverted: ReceivableToken: Receivable is frozen" };
    assert.match(UIFeedback.parseBlockchainError(freezeErr), /已被审计员冻结/);

    // Insufficient balance
    const balErr = { message: "insufficient funds for transfer" };
    assert.match(UIFeedback.parseBlockchainError(balErr), /钱包余额不足/);
});
