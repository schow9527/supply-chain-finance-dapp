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

test("UIFeedback - Custom Error & Revert Parsing", () => {
    // 1. User cancelled in MetaMask
    const userCancelErr = { code: "ACTION_REJECTED", message: "User denied transaction signature" };
    assert.match(UIFeedback.parseBlockchainError(userCancelErr), /用户已在 MetaMask 中取消了交易签名/);

    // 2. Custom error: InvoiceAlreadyExists
    const dupErr = { revert: { name: "InvoiceAlreadyExists" } };
    assert.match(UIFeedback.parseBlockchainError(dupErr), /防重拦截：该发票号与承兑买方组合已在链上登记/);

    // 3. Custom error: SystemPaused
    const pauseErr = { revert: { name: "SystemPaused" } };
    assert.match(UIFeedback.parseBlockchainError(pauseErr), /系统当前处于紧急暂停状态/);

    // 4. Custom error: ReceivableIsFrozen
    const freezeErr = { revert: { name: "ReceivableIsFrozen" } };
    assert.match(UIFeedback.parseBlockchainError(freezeErr), /已被审计员链上冻结/);

    // 5. Custom error: Unauthorized
    const unauthErr = { revert: { name: "Unauthorized" } };
    assert.match(UIFeedback.parseBlockchainError(unauthErr), /当前账户没有执行该操作的权限/);

    // 6. Insufficient balance string
    const balErr = { message: "insufficient funds for gas * price + value" };
    assert.match(UIFeedback.parseBlockchainError(balErr), /钱包内 Sepolia 测试 ETH 不足/);
});
