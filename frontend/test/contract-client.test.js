const test = require("node:test");
const assert = require("node:assert");
const ContractClient = require("../static/js/contract-client.js");

test("ContractClient - Instantiation and contracts map", () => {
    const mockProvider = {
        getFeeData: async () => ({ gasPrice: 20000000000n })
    };
    const mockSigner = {};
    const addresses = {
        RoleManager: "0x1111111111111111111111111111111111111111",
        InvoiceRegistry: "0x2222222222222222222222222222222222222222",
        ReceivableToken: "0x3333333333333333333333333333333333333333",
        FinancingPool: "0x4444444444444444444444444444444444444444",
        MockStablecoin: "0x5555555555555555555555555555555555555555"
    };

    const client = new ContractClient(mockProvider, mockSigner, addresses, {});
    assert.strictEqual(client.provider, mockProvider);
    assert.strictEqual(client.signer, mockSigner);
    assert.strictEqual(client.addresses.RoleManager, "0x1111111111111111111111111111111111111111");

    // Throws if calling uninitialized contract
    assert.rejects(async () => {
        await client.executeWithLifecycle("RoleManager", "pause", []);
    }, /Contract RoleManager not initialized/);
});
