const test = require("node:test");
const assert = require("node:assert");
const AppConfig = require("../static/js/config.js");

test("AppConfig - Constants", () => {
    assert.strictEqual(AppConfig.SEPOLIA_CHAIN_ID_DEC, 11155111);
    assert.strictEqual(AppConfig.SEPOLIA_CHAIN_ID_HEX, "0xaa36a7");
    assert.strictEqual(AppConfig.ROLES.SUPPLIER, "SUPPLIER");
    assert.strictEqual(AppConfig.ROLES.CORE_ENTERPRISE, "CORE_ENTERPRISE");
    assert.strictEqual(AppConfig.ROLES.FINANCIER, "FINANCIER");
    assert.strictEqual(AppConfig.ROLES.AUDITOR, "AUDITOR");
    assert.strictEqual(AppConfig.ROLES.ADMIN, "ADMIN");
});

test("AppConfig - calculateFundedAmount formula", () => {
    // 100,000 at 5% (500 bps) discount -> 95,000
    const amount = 100000n;
    const bps = 500n;
    const funded = AppConfig.calculateFundedAmount(amount, bps);
    assert.strictEqual(funded, 95000n);

    // 50,000 at 3.5% (350 bps) discount -> 48,250
    const funded2 = AppConfig.calculateFundedAmount(50000n, 350n);
    assert.strictEqual(funded2, 48250n);

    // Rejects >= 10000 bps (100% or more)
    assert.throws(() => {
        AppConfig.calculateFundedAmount(100000n, 10000n);
    }, /Discount rate cannot be 100% or greater/);
});

test("AppConfig - formatBps", () => {
    assert.strictEqual(AppConfig.formatBps(500), "5.00%");
    assert.strictEqual(AppConfig.formatBps(350), "3.50%");
    assert.strictEqual(AppConfig.formatBps(10), "0.10%");
});

test("AppConfig - parseTokens and formatTokens", () => {
    const wei = AppConfig.parseTokens("1000");
    assert.strictEqual(wei, "1000000000000000000000");

    const formatted = AppConfig.formatTokens(wei);
    assert.strictEqual(formatted, "1,000.00");

    const weiFraction = AppConfig.parseTokens("2500.5");
    assert.strictEqual(weiFraction, "2500500000000000000000");
    assert.strictEqual(AppConfig.formatTokens(weiFraction), "2,500.50");
});

test("AppConfig - shortAddress", () => {
    const addr = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8";
    assert.strictEqual(AppConfig.shortAddress(addr), "0x7099...79C8");
    assert.strictEqual(AppConfig.shortAddress(""), "");
});
