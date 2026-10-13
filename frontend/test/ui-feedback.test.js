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
    assert.match(UIFeedback.parseBlockchainError(userCancelErr), /Transaction signature was cancelled in MetaMask/);

    // 2. Custom error: InvoiceAlreadyExists
    const dupErr = { revert: { name: "InvoiceAlreadyExists" } };
    assert.match(UIFeedback.parseBlockchainError(dupErr), /Duplicate rejected: This invoice number and buyer combination is already registered on-chain/);

    // 3. Custom error: SystemPaused
    const pauseErr = { revert: { name: "SystemPaused" } };
    assert.match(UIFeedback.parseBlockchainError(pauseErr), /System is currently in emergency pause/);

    // 4. Custom error: ReceivableIsFrozen
    const freezeErr = { revert: { name: "ReceivableIsFrozen" } };
    assert.match(UIFeedback.parseBlockchainError(freezeErr), /This receivable token has been frozen by an auditor/);

    // 5. Custom error: Unauthorized
    const unauthErr = { revert: { name: "Unauthorized" } };
    assert.match(UIFeedback.parseBlockchainError(unauthErr), /Current account is not authorized to perform this action/);

    // 6. Insufficient balance string
    const balErr = { message: "insufficient funds for gas * price + value" };
    assert.match(UIFeedback.parseBlockchainError(balErr), /Insufficient Sepolia ETH in wallet to pay gas fees/);
});

test("UIFeedback - Decodes raw revert data when ethers reports unknown custom error", () => {
    // ethers leaves err.revert null for some estimateGas failures via MetaMask
    const fakeIface = {
        parseError(data) {
            if (data.startsWith("0x11ed168a")) return { name: "NotOverdueYet" };
            throw new Error("no matching error");
        }
    };
    const otherIface = { parseError() { throw new Error("no matching error"); } };
    const rawErr = {
        message: 'execution reverted (unknown custom error) (action="estimateGas", data="0x11ed168a0000")',
        revert: null,
        data: "0x11ed168a0000000000000000000000000000000000000000000000000000000000000002"
    };
    assert.match(UIFeedback.parseBlockchainError(rawErr, [otherIface, fakeIface]), /cannot be marked overdue/);

    // Nested provider error shape
    const nestedErr = { message: "execution reverted", error: { data: rawErr.data } };
    assert.match(UIFeedback.parseBlockchainError(nestedErr, [fakeIface]), /cannot be marked overdue/);

    // Undecodable data falls back to the raw message
    const unknownErr = { message: "execution reverted", data: "0xdeadbeef" };
    assert.strictEqual(UIFeedback.parseBlockchainError(unknownErr, [fakeIface]), "execution reverted");
});
