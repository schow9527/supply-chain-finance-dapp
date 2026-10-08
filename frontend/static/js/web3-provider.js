/**
 * Web3 Provider & MetaMask connection module for Supply Chain Finance DApp
 * Target network: Sepolia (11155111)
 */

let provider = null;
let signer = null;
let userAddress = null;

const SEPOLIA_CHAIN_ID = "0xaa36a7"; // 11155111 in hex

async function connectWallet() {
    if (!window.ethereum) {
        alert("请先安装 MetaMask 钱包插件！");
        return;
    }

    try {
        provider = new ethers.BrowserProvider(window.ethereum);
        const accounts = await provider.send("eth_requestAccounts", []);
        if (accounts.length > 0) {
            userAddress = accounts[0];
            signer = await provider.getSigner();
            
            const btn = document.getElementById("connect-wallet-btn");
            if (btn) {
                btn.innerText = `${userAddress.slice(0, 6)}...${userAddress.slice(-4)}`;
                btn.classList.remove("btn-primary");
                btn.classList.add("btn-outline");
            }

            await checkNetwork();
            await fetchRole(userAddress);
        }
    } catch (err) {
        console.error("连接钱包失败:", err);
    }
}

async function checkNetwork() {
    if (!window.ethereum) return;
    const network = await provider.getNetwork();
    const networkBadge = document.getElementById("network-badge");
    if (!networkBadge) return;

    if (network.chainId === 11155111n) {
        networkBadge.innerText = "Sepolia 测试网";
        networkBadge.className = "badge badge-success";
    } else {
        networkBadge.innerText = `网络错误 (${network.name})`;
        networkBadge.className = "badge badge-warning";
    }
}

async function fetchRole(address) {
    const roleBadge = document.getElementById("role-badge");
    if (!roleBadge) return;

    try {
        const res = await fetch(`/api/me?address=${address}`);
        if (res.ok) {
            const data = await res.json();
            roleBadge.innerText = data.role || "未分配角色";
            roleBadge.className = "badge badge-success";
        } else {
            roleBadge.innerText = "未注册用户";
            roleBadge.className = "badge badge-secondary";
        }
    } catch (e) {
        roleBadge.innerText = "访客模式";
    }
}

// 监听账户变更
if (window.ethereum) {
    window.ethereum.on("accountsChanged", (accounts) => {
        if (accounts.length === 0) {
            location.reload();
        } else {
            connectWallet();
        }
    });

    window.ethereum.on("chainChanged", () => {
        location.reload();
    });
}
