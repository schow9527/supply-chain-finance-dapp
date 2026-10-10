/**
 * Web3 Provider & State Manager for Supply Chain Finance DApp
 * Handles: MetaMask connection, Network guard (Sepolia), Account routing.
 *
 * 核心设计：本项目是多页面应用（MPA），每次页面跳转都会重新加载此脚本。
 * 因此必须在每次 DOMContentLoaded 时静默地重新检测 MetaMask 已授权账户，
 * 而不是要求用户再次手动点击"连接"。
 */

window.DAppState = {
    provider: null,
    signer: null,
    account: null,
    role: "NONE",
    sessionAuthenticated: false,
    contractClient: null,
    apiClient: null,
    isReady: false,
    _addresses: null,
    _abis: null
};

async function initWeb3() {
    window.DAppState.apiClient = new window.ApiClient();

    // Load deployed addresses
    let addresses = window.AppConfig.DEFAULT_ADDRESSES;
    try {
        const resp = await fetch("/static/js/deployed_addresses.json");
        if (resp.ok) {
            const data = await resp.json();
            if (data.contracts) addresses = data.contracts;
        }
    } catch (_) {}
    window.DAppState._addresses = addresses;

    // Load ABIs
    const abis = {};
    const contractNames = ["RoleManager", "ReceivableToken", "InvoiceRegistry", "FinancingPool", "MockStablecoin"];
    for (const name of contractNames) {
        try {
            const r = await fetch(`/static/js/abi/${name}.json`);
            if (r.ok) abis[name] = await r.json();
        } catch (_) {}
    }
    window.DAppState._abis = abis;

    if (window.ethereum) {
        window.DAppState.provider = new ethers.BrowserProvider(window.ethereum);

        // 先用 eth_accounts 静默查询（不弹窗）
        let accounts = await window.DAppState.provider.send("eth_accounts", []).catch(() => []);

        // 如果 eth_accounts 返回空，尝试直接通过 ethereum.request 再查一次
        // 某些 MetaMask 版本对 ethers BrowserProvider 包装后的 send 行为不一致
        if (accounts.length === 0 && window.ethereum.selectedAddress) {
            accounts = [window.ethereum.selectedAddress];
        }

        if (accounts.length > 0) {
            // 初始化 contractClient（需要在 handleAccountsChanged 之前，
            // 因为里面要用 contractClient 查链上角色）
            window.DAppState.signer = await window.DAppState.provider.getSigner();
            window.DAppState.contractClient = new window.ContractClient(
                window.DAppState.provider,
                window.DAppState.signer,
                addresses,
                abis
            );
            await handleAccountsChanged(accounts);
        }
    }

    window.DAppState.isReady = true;
    updateUI();
}

async function connectWallet() {
    if (!window.ethereum) {
        UIFeedback.showToast("未检测到 MetaMask 插件，请先安装！", "warning");
        window.open("https://metamask.io/download/", "_blank");
        return;
    }

    try {
        if (!window.DAppState.provider) {
            window.DAppState.provider = new ethers.BrowserProvider(window.ethereum);
        }
        const accounts = await window.DAppState.provider.send("eth_requestAccounts", []);

        // 确保 signer 和 contractClient 在角色检测前就位
        window.DAppState.signer = await window.DAppState.provider.getSigner();
        if (!window.DAppState.contractClient && window.DAppState._addresses && window.DAppState._abis) {
            window.DAppState.contractClient = new window.ContractClient(
                window.DAppState.provider,
                window.DAppState.signer,
                window.DAppState._addresses,
                window.DAppState._abis
            );
        }

        await handleAccountsChanged(accounts);
        await ensureSepoliaNetwork();
        await authenticateWallet();
        UIFeedback.showToast("钱包连接成功！", "success");
    } catch (err) {
        console.error("User rejected or failed:", err);
        if (!err.isWalletAuthError) {
            UIFeedback.showToast(UIFeedback.parseBlockchainError(err), "error");
        }
    }
}

async function handleAccountsChanged(accounts) {
    if (!accounts || accounts.length === 0) {
        window.DAppState.account = null;
        window.DAppState.signer = null;
        window.DAppState.role = "NONE";
        window.DAppState.sessionAuthenticated = false;
        updateUI();
        return;
    }

    window.DAppState.account = accounts[0];
    window.DAppState.signer = await window.DAppState.provider.getSigner();

    // Query on-chain role via RoleManager (per Member 1 interface spec)
    try {
        if (window.DAppState.contractClient && window.DAppState.contractClient.contracts.RoleManager) {
            const rm = window.DAppState.contractClient.contracts.RoleManager;
            const isReg = await rm.isRegistered(window.DAppState.account);
            if (isReg) {
                const r = await rm.roleOf(window.DAppState.account);
                const supplierHash = ethers.keccak256(ethers.toUtf8Bytes("SUPPLIER"));
                const coreHash = ethers.keccak256(ethers.toUtf8Bytes("CORE_ENTERPRISE"));
                const funderHash = ethers.keccak256(ethers.toUtf8Bytes("FUNDER"));
                const auditorHash = ethers.keccak256(ethers.toUtf8Bytes("AUDITOR"));

                if (r === "0x0000000000000000000000000000000000000000000000000000000000000000") {
                    window.DAppState.role = "ADMIN";
                } else if (r === supplierHash) {
                    window.DAppState.role = "SUPPLIER";
                } else if (r === coreHash) {
                    window.DAppState.role = "CORE_ENTERPRISE";
                } else if (r === funderHash) {
                    window.DAppState.role = "FINANCIER";
                } else if (r === auditorHash) {
                    window.DAppState.role = "AUDITOR";
                }
            }
        }
    } catch (_) {}

    // Restore the HttpOnly backend session used by protected APIs. If there is
    // no matching session, keep the wallet connected but fail closed for API UI.
    await restoreSessionForAccount();
}

async function restoreSessionForAccount() {
    if (!window.DAppState.account) return;
    try {
        const me = await window.DAppState.apiClient.getMe();
        if (me.wallet_address.toLowerCase() !== window.DAppState.account.toLowerCase()) {
            await window.DAppState.apiClient.logout();
            window.DAppState.sessionAuthenticated = false;
            updateUI();
            return;
        }
        window.DAppState.sessionAuthenticated = true;
        window.DAppState.role = me.role === "FUNDER" ? "FINANCIER" : (me.role || "NONE");
        window.DAppState.enterpriseName = me.enterprise_name || "";
    } catch (_) {
        // Keep the read-only on-chain role for display. Protected APIs still
        // fail closed because no HttpOnly session was authenticated.
        window.DAppState.sessionAuthenticated = false;
    }
    updateUI();
}

async function authenticateWallet() {
    const account = window.DAppState.account;
    if (!account || !window.DAppState.signer) return;
    try {
        const challenge = await window.DAppState.apiClient.requestNonce(account);
        const signature = await window.DAppState.signer.signMessage(challenge.message);
        await window.DAppState.apiClient.verifySignature(account, signature);
        await restoreSessionForAccount();
    } catch (err) {
        err.isWalletAuthError = true;
        window.DAppState.sessionAuthenticated = false;
        if (err && (err.code === 4001 || err.code === "ACTION_REJECTED")) {
            UIFeedback.showToast("已取消钱包登录签名；这不是链上交易，不会产生 Gas。", "warning");
        } else {
            UIFeedback.showToast(err.message || "钱包身份验证失败", "error");
        }
        throw err;
    }
}

async function ensureAuthenticated() {
    if (!window.DAppState.account || !window.DAppState.signer) {
        await connectWallet();
        return;
    }
    if (!window.DAppState.sessionAuthenticated) {
        await authenticateWallet();
    }
}

async function ensureSepoliaNetwork() {
    if (!window.DAppState.provider) return;
    const net = await window.DAppState.provider.getNetwork();
    if (net.chainId !== BigInt(window.AppConfig.SEPOLIA_CHAIN_ID_DEC)) {
        try {
            await window.ethereum.request({
                method: "wallet_switchEthereumChain",
                params: [{ chainId: window.AppConfig.SEPOLIA_CHAIN_ID_HEX }]
            });
        } catch (switchError) {
            if (switchError.code === 4902) {
                await window.ethereum.request({
                    method: "wallet_addEthereumChain",
                    params: [{
                        chainId: window.AppConfig.SEPOLIA_CHAIN_ID_HEX,
                        chainName: "Sepolia Testnet",
                        nativeCurrency: { name: "SepoliaETH", symbol: "ETH", decimals: 18 },
                        rpcUrls: ["https://rpc.sepolia.org"]
                    }]
                });
            }
        }
    }
}

async function claimTestTokens() {
    if (!window.DAppState.account) {
        UIFeedback.showToast("请先连接钱包！", "warning");
        return;
    }
    if (!window.DAppState.contractClient) {
        UIFeedback.showToast("合约客户端尚未就绪，请检查测试网配置", "warning");
        return;
    }
    try {
        await window.DAppState.contractClient.claimFaucet();
        UIFeedback.showToast("10,000 mUSDT 测试币已成功领取！", "success");
    } catch (err) {
        console.error(err);
    }
}

function updateUI() {
    const acc = window.DAppState.account;
    const role = window.DAppState.role;

    // Auto-fill wallet input on registration page if exists
    const walletInput = document.getElementById("wallet-address-input");
    if (walletInput && acc) {
        walletInput.value = acc;
    }

    const connectBtn = document.getElementById("connect-wallet-btn");
    if (connectBtn) {
        if (acc) {
            if (window.DAppState.sessionAuthenticated) {
                connectBtn.innerText = window.AppConfig.shortAddress(acc);
                connectBtn.className = "btn btn-outline";
            } else {
                connectBtn.innerText = "🔑 签名登录 (" + window.AppConfig.shortAddress(acc) + ")";
                connectBtn.className = "btn btn-primary";
            }
        } else {
            connectBtn.innerText = "连接 MetaMask";
            connectBtn.className = "btn btn-primary";
        }
    }

    const roleBadge = document.getElementById("role-badge");
    if (roleBadge) {
        roleBadge.innerText = window.AppConfig.ROLE_LABELS[role] || "未登录";
        roleBadge.className = `badge badge-${role === "NONE" ? "secondary" : "success"}`;
    }

    const netBadge = document.getElementById("network-badge");
    if (netBadge && window.DAppState.provider) {
        window.DAppState.provider.getNetwork().then(net => {
            if (net.chainId === BigInt(window.AppConfig.SEPOLIA_CHAIN_ID_DEC)) {
                netBadge.innerText = "Sepolia";
                netBadge.className = "badge badge-success";
            } else {
                netBadge.innerText = "网络错误";
                netBadge.className = "badge badge-warning";
            }
        }).catch(() => {});
    }

    // Broadcast account changed to all listening views
    if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("walletAccountChanged", { detail: { account: acc, role: role } }));
    }
}

// Event listeners for wallet
if (typeof window !== "undefined" && window.ethereum) {
    window.ethereum.on("accountsChanged", async (accs) => {
        try { await window.DAppState.apiClient.logout(); } catch (_) {}
        await handleAccountsChanged(accs);
    });
    window.ethereum.on("chainChanged", () => location.reload());
}

document.addEventListener("DOMContentLoaded", initWeb3);
