// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./RoleManager.sol";

/**
 * @title ReceivableToken
 * @dev ERC-1155 compliant/semi-fungible token representing accounts receivable.
 * Only InvoiceRegistry can mint; only FinancingPool can burn.
 * Auditor can freeze / unfreeze specific receivables.
 */
contract ReceivableToken {
    RoleManager public roleManager;
    address public invoiceRegistry;
    address public financingPool;

    // Token ID => account => balance
    mapping(uint256 => mapping(address => uint256)) private _balances;
    // Token ID => total supply
    mapping(uint256 => uint256) private _totalSupply;
    // Token ID => isFrozen
    mapping(uint256 => bool) public isFrozen;
    // Token ID => freeze reason
    mapping(uint256 => string) public freezeReason;

    // Operator approvals: owner => operator => approved
    mapping(address => mapping(address => bool)) private _operatorApprovals;

    event TransferSingle(address indexed operator, address indexed from, address indexed to, uint256 id, uint256 value);
    event ReceivableTransferred(address indexed from, address indexed to, uint256 indexed id, uint256 amount);
    event ReceivableFrozen(uint256 indexed id, string reason, address indexed auditor);
    event ReceivableUnfrozen(uint256 indexed id, address indexed auditor);
    event ApprovalForAll(address indexed account, address indexed operator, bool approved);

    modifier onlyInvoiceRegistry() {
        require(msg.sender == invoiceRegistry, "ReceivableToken: Caller is not InvoiceRegistry");
        _;
    }

    modifier onlyFinancingPool() {
        require(msg.sender == financingPool, "ReceivableToken: Caller is not FinancingPool");
        _;
    }

    modifier onlyAuditor() {
        require(roleManager.hasRole(roleManager.AUDITOR_ROLE(), msg.sender), "ReceivableToken: Caller is not Auditor");
        _;
    }

    modifier whenNotPaused() {
        require(!roleManager.isPaused(), "ReceivableToken: System is paused");
        _;
    }

    modifier notFrozen(uint256 id) {
        require(!isFrozen[id], "ReceivableToken: Receivable is frozen");
        _;
    }

    constructor(address _roleManager) {
        require(_roleManager != address(0), "ReceivableToken: Invalid RoleManager address");
        roleManager = RoleManager(_roleManager);
    }

    function setInvoiceRegistry(address _invoiceRegistry) external {
        require(roleManager.hasRole(roleManager.ADMIN_ROLE(), msg.sender), "ReceivableToken: Admin only");
        invoiceRegistry = _invoiceRegistry;
    }

    function setFinancingPool(address _financingPool) external {
        require(roleManager.hasRole(roleManager.ADMIN_ROLE(), msg.sender), "ReceivableToken: Admin only");
        financingPool = _financingPool;
    }

    function balanceOf(address account, uint256 id) public view returns (uint256) {
        return _balances[id][account];
    }

    function totalSupply(uint256 id) public view returns (uint256) {
        return _totalSupply[id];
    }

    function isApprovedForAll(address account, address operator) public view returns (bool) {
        return _operatorApprovals[account][operator] || operator == financingPool;
    }

    function setApprovalForAll(address operator, bool approved) external {
        _operatorApprovals[msg.sender][operator] = approved;
        emit ApprovalForAll(msg.sender, operator, approved);
    }

    function mint(address to, uint256 id, uint256 amount) external onlyInvoiceRegistry whenNotPaused {
        require(to != address(0), "ReceivableToken: Mint to zero address");
        _totalSupply[id] += amount;
        _balances[id][to] += amount;
        emit TransferSingle(msg.sender, address(0), to, id, amount);
    }

    function burn(address from, uint256 id, uint256 amount) external onlyFinancingPool whenNotPaused notFrozen(id) {
        require(_balances[id][from] >= amount, "ReceivableToken: Burn amount exceeds balance");
        _balances[id][from] -= amount;
        _totalSupply[id] -= amount;
        emit TransferSingle(msg.sender, from, address(0), id, amount);
    }

    function transferReceivable(address to, uint256 id, uint256 amount) external whenNotPaused notFrozen(id) {
        require(to != address(0), "ReceivableToken: Transfer to zero address");
        require(
            roleManager.hasRole(roleManager.SUPPLIER_ROLE(), to) ||
            roleManager.hasRole(roleManager.FINANCIER_ROLE(), to) ||
            to == financingPool,
            "ReceivableToken: Recipient must be registered supplier, financier, or pool"
        );
        require(_balances[id][msg.sender] >= amount, "ReceivableToken: Insufficient balance");

        _balances[id][msg.sender] -= amount;
        _balances[id][to] += amount;

        emit TransferSingle(msg.sender, msg.sender, to, id, amount);
        emit ReceivableTransferred(msg.sender, to, id, amount);
    }

    function transferFrom(address from, address to, uint256 id, uint256 amount) external whenNotPaused notFrozen(id) {
        require(msg.sender == from || isApprovedForAll(from, msg.sender), "ReceivableToken: Caller not owner nor approved");
        require(_balances[id][from] >= amount, "ReceivableToken: Insufficient balance");

        _balances[id][from] -= amount;
        _balances[id][to] += amount;

        emit TransferSingle(msg.sender, from, to, id, amount);
        emit ReceivableTransferred(from, to, id, amount);
    }

    function freeze(uint256 id, string calldata reason) external onlyAuditor whenNotPaused {
        require(!isFrozen[id], "ReceivableToken: Already frozen");
        isFrozen[id] = true;
        freezeReason[id] = reason;
        emit ReceivableFrozen(id, reason, msg.sender);
    }

    function unfreeze(uint256 id) external onlyAuditor whenNotPaused {
        require(isFrozen[id], "ReceivableToken: Not frozen");
        isFrozen[id] = false;
        freezeReason[id] = "";
        emit ReceivableUnfrozen(id, msg.sender);
    }
}
