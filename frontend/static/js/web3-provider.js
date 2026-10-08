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
        }
    }

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
        UIFeedback.showToast("钱包连接成功！", "success");
    } catch (err) {
        console.error("User rejected or failed:", err);
        UIFeedback.showToast(UIFeedback.parseBlockchainError(err), "error");
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

    // Fallback to backend API
    if (window.DAppState.role === "NONE") {
        try {
            const me = await window.DAppState.apiClient.getMe(window.DAppState.account);
            window.DAppState.role = me.role || "NONE";
            window.DAppState.enterpriseName = me.enterprise_name || "";
        } catch (_) {
            window.DAppState.role = "NONE";
        }
    }

    updateUI();
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

// Event listeners for wallet
if (typeof window !== "undefined" && window.ethereum) {
    window.ethereum.on("accountsChanged", (accs) => handleAccountsChanged(accs));
    window.ethereum.on("chainChanged", () => location.reload());
}

document.addEventListener("DOMContentLoaded", initWeb3);
