/**
 * Global Configuration & Utility Constants for Supply Chain Finance DApp
 * Aligned with Member 1's deployed Sepolia contracts (Foundry).
 * Currency: mUSD (6 decimals, 1e6 = 1 mUSD).
 */
(function (root, factory) {
    if (typeof module === "object" && module.exports) {
        module.exports = factory();
    } else {
        root.AppConfig = factory();
    }
}(typeof self !== "undefined" ? self : this, function () {
    const SEPOLIA_CHAIN_ID_DEC = 11155111;
    const SEPOLIA_CHAIN_ID_HEX = "0xaa36a7";
    const TOKEN_DECIMALS = 6;

    const ROLES = {
        ADMIN: "ADMIN",
        SUPPLIER: "SUPPLIER",
        CORE_ENTERPRISE: "CORE_ENTERPRISE",
        FUNDER: "FUNDER",
        FINANCIER: "FUNDER", // alias
        AUDITOR: "AUDITOR",
        NONE: "NONE"
    };

    const ROLE_LABELS = {
        ADMIN: "平台管理员",
        SUPPLIER: "供应商",
        CORE_ENTERPRISE: "核心企业",
        FUNDER: "资金方 / 银行",
        FINANCIER: "资金方 / 银行",
        AUDITOR: "审计员",
        NONE: "未入驻企业"
    };

    // Deployed addresses on Sepolia (11155111) by Member 1
    const DEFAULT_ADDRESSES = {
        RoleManager: "0x82f86a2B31C424b4833b5BAb82464eB7f69B6a2E",
        ReceivableToken: "0x3c9EcDdf7e788F7B8e04D4177d04B3c291E0368f",
        MockStablecoin: "0xE3C713Db876c97600141Ba34C7Cb68898CF1E04F",
        InvoiceRegistry: "0x39605C1D4FCE3D85DC14f7f283899b984dd1eD7a",
        FinancingPool: "0x2bb0A6e688C331248fe8575121F799B5286985c6"
    };

    /**
     * Utility: Calculate actual funded payout amount
     * formula: fundedAmount = amount * (10000 - discountRateBps) / 10000
     */
    function calculateFundedAmount(amount, discountRateBps) {
        const amt = BigInt(amount);
        const bps = BigInt(discountRateBps);
        if (bps >= 10000n) {
            throw new Error("Discount rate cannot be 100% or greater");
        }
        return (amt * (10000n - bps)) / 10000n;
    }

    /**
     * Utility: Format basis points to readable percentage (e.g., 500 bps -> "5.00%")
     */
    function formatBps(bps) {
        const val = Number(bps) / 100;
        return val.toFixed(2) + "%";
    }

    /**
     * Utility: Convert human-readable token amount (e.g. "1000") to 6-decimal units
     */
    function parseTokens(amountStr) {
        if (!amountStr || isNaN(Number(amountStr))) {
            throw new Error("Invalid token amount");
        }
        const parts = String(amountStr).split(".");
        let whole = parts[0];
        let fraction = parts[1] || "";
        if (fraction.length > TOKEN_DECIMALS) {
            fraction = fraction.substring(0, TOKEN_DECIMALS);
        } else {
            fraction = fraction.padEnd(TOKEN_DECIMALS, "0");
        }
        return (BigInt(whole) * 10n ** BigInt(TOKEN_DECIMALS) + BigInt(fraction)).toString();
    }

    /**
     * Utility: Convert 6-decimal token units to human-readable string with commas
     */
    function formatTokens(unitsStr, decimals = 2) {
        if (!unitsStr) return "0.00";
        const bi = BigInt(unitsStr);
        const factor = 10n ** BigInt(TOKEN_DECIMALS);
        const whole = bi / factor;
        const fraction = bi % factor;
        const fracStr = fraction.toString().padStart(TOKEN_DECIMALS, "0").slice(0, decimals);
        return `${Number(whole).toLocaleString()}.${fracStr}`;
    }

    /**
     * Utility: Format Unix timestamp to YYYY-MM-DD HH:mm
     */
    function formatTimestamp(ts) {
        if (!ts) return "-";
        const date = new Date(Number(ts) * 1000);
        return date.toLocaleString("zh-CN", { hour12: false });
    }

    /**
     * Utility: Truncate Ethereum address for display (0x1234...abcd)
     */
    function shortenAddress(addr) {
        if (!addr || addr.length < 10) return addr || "";
        return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
    }

    return {
        SEPOLIA_CHAIN_ID_DEC,
        SEPOLIA_CHAIN_ID_HEX,
        TOKEN_DECIMALS,
        ROLES,
        ROLE_LABELS,
        DEFAULT_ADDRESSES,
        calculateFundedAmount,
        formatBps,
        parseTokens,
        formatTokens,
        formatTimestamp,
        shortAddress: shortenAddress
    };
}));
