/**
 * Web3 Provider & State Manager for Supply Chain Finance DApp
 * Handles: MetaMask connection, Network guard (Sepolia), Account routing, and Demo role simulation.
 */

window.DAppState = {
    provider: null,
    signer: null,
    account: null,
    role: "NONE",
    contractClient: null,
    apiClient: null,
    contractAddresses: null,
    contractAbis: null,
    isReady: false
};

async function initWeb3() {
    window.DAppState.apiClient = new window.ApiClient();

    // Load addresses if available
    let addresses = window.AppConfig.DEFAULT_ADDRESSES;
    try {
        const resp = await fetch("/static/js/deployed_addresses.json");
        if (resp.ok) {
            const data = await resp.json();
            if (data.contracts) addresses = data.contracts;
        }
    } catch (_) {}

    // Load ABIs
    const abis = {};
    const contractNames = ["RoleManager", "ReceivableToken", "InvoiceRegistry", "FinancingPool", "MockStablecoin"];
    for (const name of contractNames) {
        try {
            const r = await fetch(`/static/js/abi/${name}.json`);
            if (r.ok) abis[name] = await r.json();
        } catch (_) {}
    }
    window.DAppState.contractAddresses = addresses;
    window.DAppState.contractAbis = abis;

    if (window.ethereum) {
        window.DAppState.provider = new ethers.BrowserProvider(window.ethereum);
        
        // Check if already authorized
        const accounts = await window.DAppState.provider.send("eth_accounts", []).catch(() => []);
        if (accounts.length > 0) {
            await handleAccountsChanged(accounts);
        }

        // Init contract client
        if (window.DAppState.signer) {
            window.DAppState.contractClient = new window.ContractClient(
                window.DAppState.provider,
                window.DAppState.signer,
                addresses,
                abis
            );
            await restoreSessionForAccount();
        }
    }

    renderDemoSwitcher();
    updateUI();
}

async function connectWallet() {
    if (!window.ethereum) {
        UIFeedback.showToast("未检测到 MetaMask 插件，请先安装！", "warning");
        window.open("https://metamask.io/download/", "_blank");
        return;
    }

    try {
        const accounts = await window.DAppState.provider.send("eth_requestAccounts", []);
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
        updateUI();
        return;
    }

    window.DAppState.account = accounts[0];
    window.DAppState.signer = await window.DAppState.provider.getSigner();
    window.DAppState.role = "NONE";
    if (window.DAppState.contractAddresses && window.DAppState.contractAbis) {
        window.DAppState.contractClient = new window.ContractClient(
            window.DAppState.provider,
            window.DAppState.signer,
            window.DAppState.contractAddresses,
            window.DAppState.contractAbis
        );
    }
    updateUI();
}

async function restoreSessionForAccount() {
    if (!window.DAppState.account) return;
    try {
        const me = await window.DAppState.apiClient.getMe();
        if (me.wallet_address.toLowerCase() !== window.DAppState.account.toLowerCase()) {
            await window.DAppState.apiClient.logout();
            return;
        }
        window.DAppState.role = me.role === "FUNDER" ? "FINANCIER" : (me.role || "NONE");
        window.DAppState.enterpriseName = me.enterprise_name || "";
        updateUI();
    } catch (_) {
        window.DAppState.role = "NONE";
    }
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
        window.DAppState.role = "NONE";
        if (err && (err.code === 4001 || err.code === "ACTION_REJECTED")) {
            UIFeedback.showToast("已取消钱包登录签名；这不是链上交易，不会产生 Gas。", "warning");
        } else {
            UIFeedback.showToast(err.message || "钱包身份验证失败", "error");
        }
        throw err;
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
            connectBtn.innerText = window.AppConfig.shortAddress(acc);
            connectBtn.className = "btn btn-outline";
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

/**
 * Demo Switcher widget to help Member 6 test and record demo video across 5 roles
 */
function renderDemoSwitcher() {
    if (!["localhost", "127.0.0.1"].includes(window.location.hostname)) return;
    if (document.getElementById("demo-switcher-widget")) return;
    const div = document.createElement("div");
    div.id = "demo-switcher-widget";
    div.className = "demo-switcher";
    div.innerHTML = `
        <div class="demo-switcher-header" onclick="this.parentElement.classList.toggle('collapsed')">
            <span>🛠️ 演示角色模拟器 (视频录制助手)</span>
            <span class="toggle-icon">▼</span>
        </div>
        <div class="demo-switcher-body">
            <small>点击模拟不同角色界面 (无需反复换私钥)：</small>
            <div class="role-pills">
                <button class="pill-btn" onclick="simulateRole('SUPPLIER')">供应商</button>
                <button class="pill-btn" onclick="simulateRole('CORE_ENTERPRISE')">核心企业</button>
                <button class="pill-btn" onclick="simulateRole('FINANCIER')">资金方</button>
                <button class="pill-btn" onclick="simulateRole('AUDITOR')">审计员</button>
                <button class="pill-btn" onclick="simulateRole('ADMIN')">管理员</button>
                <button class="pill-btn pill-reset" onclick="simulateRole('NONE')">重置</button>
            </div>
            <div style="margin-top:8px;">
                <button class="btn btn-sm btn-outline" style="width:100%;" onclick="claimTestTokens()">💧 领取 10,000 测试稳定币</button>
            </div>
        </div>
    `;
    document.body.appendChild(div);
}

function simulateRole(role) {
    window.DAppState.role = role;
    if (!window.DAppState.account) {
        window.DAppState.account = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8";
    }
    updateUI();
    UIFeedback.showToast(`已切换至【${window.AppConfig.ROLE_LABELS[role] || role}】模拟视图`, "info");
    
    // Auto route if on landing or specific console
    const routeMap = {
        SUPPLIER: "/supplier/dashboard",
        CORE_ENTERPRISE: "/core_enterprise/dashboard",
        FINANCIER: "/financier/dashboard",
        AUDITOR: "/auditor/overview",
        ADMIN: "/admin/registrations"
    };
    if (routeMap[role] && window.location.pathname === "/") {
        window.location.href = routeMap[role];
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
