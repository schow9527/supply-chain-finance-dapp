/**
 * Global Configuration & Utility Constants for Supply Chain Finance DApp
 * Compatible with Browser and Node.js testing environments.
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

    const ROLES = {
        ADMIN: "ADMIN",
        SUPPLIER: "SUPPLIER",
        CORE_ENTERPRISE: "CORE_ENTERPRISE",
        FINANCIER: "FINANCIER",
        AUDITOR: "AUDITOR",
        NONE: "NONE"
    };

    const ROLE_LABELS = {
        ADMIN: "平台管理员",
        SUPPLIER: "供应商",
        CORE_ENTERPRISE: "核心企业",
        FINANCIER: "资金方 / 银行",
        AUDITOR: "审计员",
        NONE: "未入驻企业"
    };

    // Default addresses (updated after deployment)
    const DEFAULT_ADDRESSES = {
        RoleManager: "0x0000000000000000000000000000000000000000",
        ReceivableToken: "0x0000000000000000000000000000000000000000",
        InvoiceRegistry: "0x0000000000000000000000000000000000000000",
        FinancingPool: "0x0000000000000000000000000000000000000000",
        MockStablecoin: "0x0000000000000000000000000000000000000000"
    };

    /**
     * Utility: Calculate actual funded amount based on discount rate in basis points (1 bps = 0.01%)
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
     * Utility: Convert human-readable token amount (e.g. "1000") to 18-decimal wei string
     */
    function parseTokens(amountStr) {
        if (!amountStr || isNaN(Number(amountStr))) {
            throw new Error("Invalid token amount");
        }
        const parts = String(amountStr).split(".");
        let whole = parts[0];
        let fraction = parts[1] || "";
        if (fraction.length > 18) {
            fraction = fraction.substring(0, 18);
        } else {
            fraction = fraction.padEnd(18, "0");
        }
        return (BigInt(whole) * 10n ** 18n + BigInt(fraction)).toString();
    }

    /**
     * Utility: Convert 18-decimal wei string to human-readable number string with commas
     */
    function formatTokens(weiStr, decimals = 2) {
        if (!weiStr) return "0.00";
        const bi = BigInt(weiStr);
        const whole = bi / (10n ** 18n);
        const fraction = bi % (10n ** 18n);
        const fracStr = fraction.toString().padStart(18, "0").slice(0, decimals);
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
