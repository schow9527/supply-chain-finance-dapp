// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./RoleManager.sol";
import "./ReceivableToken.sol";

/**
 * @title InvoiceRegistry
 * @dev Manages invoice submission, anti-duplicate registration, core enterprise confirmation and minting.
 * Corresponds to PRD section 5 & 6.
 */
contract InvoiceRegistry {
    RoleManager public roleManager;
    ReceivableToken public receivableToken;

    enum InvoiceStatus { PENDING, CONFIRMED, REJECTED }

    struct Invoice {
        uint256 id;
        string invoiceNo;
        address supplier;
        address buyer;
        uint256 amount;
        uint256 dueDate;
        bytes32 invoiceHash;
        InvoiceStatus status;
        string rejectReason;
    }

    uint256 public nextInvoiceId = 1;
    mapping(uint256 => Invoice) public invoices;
    mapping(bytes32 => bool) public registeredInvoices;

    event InvoiceSubmitted(
        uint256 indexed invoiceId,
        address indexed supplier,
        address indexed buyer,
        uint256 amount,
        uint256 dueDate,
        bytes32 invoiceHash,
        string invoiceNo
    );
    event InvoiceConfirmed(uint256 indexed invoiceId, address indexed buyer);
    event InvoiceRejected(uint256 indexed invoiceId, address indexed buyer, string reason);
    event ReceivableMinted(uint256 indexed invoiceId, address indexed supplier, uint256 amount);

    modifier onlySupplier() {
        require(roleManager.hasRole(roleManager.SUPPLIER_ROLE(), msg.sender), "InvoiceRegistry: Caller is not Supplier");
        _;
    }

    modifier whenNotPaused() {
        require(!roleManager.isPaused(), "InvoiceRegistry: System is paused");
        _;
    }

    constructor(address _roleManager, address _receivableToken) {
        require(_roleManager != address(0) && _receivableToken != address(0), "InvoiceRegistry: Invalid address");
        roleManager = RoleManager(_roleManager);
        receivableToken = ReceivableToken(_receivableToken);
    }

    function submitInvoice(
        address buyer,
        uint256 amount,
        uint256 dueDate,
        bytes32 invoiceHash,
        string calldata invoiceNo
    ) external onlySupplier whenNotPaused returns (uint256) {
        require(roleManager.hasRole(roleManager.CORE_ENTERPRISE_ROLE(), buyer), "InvoiceRegistry: Buyer must be CoreEnterprise");
        require(amount > 0, "InvoiceRegistry: Amount must be greater than zero");
        require(dueDate > block.timestamp, "InvoiceRegistry: Due date must be in future");
        require(bytes(invoiceNo).length > 0, "InvoiceRegistry: Invoice number required");

        // F-07: Anti-duplicate registration check
        bytes32 uniquenessHash = keccak256(abi.encodePacked(invoiceNo, buyer, msg.sender, amount));
        require(!registeredInvoices[uniquenessHash], "InvoiceRegistry: Invoice already registered");
        registeredInvoices[uniquenessHash] = true;

        uint256 invoiceId = nextInvoiceId++;
        invoices[invoiceId] = Invoice({
            id: invoiceId,
            invoiceNo: invoiceNo,
            supplier: msg.sender,
            buyer: buyer,
            amount: amount,
            dueDate: dueDate,
            invoiceHash: invoiceHash,
            status: InvoiceStatus.PENDING,
            rejectReason: ""
        });

        emit InvoiceSubmitted(invoiceId, msg.sender, buyer, amount, dueDate, invoiceHash, invoiceNo);
        return invoiceId;
    }

    function confirmInvoice(uint256 invoiceId) external whenNotPaused {
        Invoice storage inv = invoices[invoiceId];
        require(inv.id != 0, "InvoiceRegistry: Invoice not found");
        require(msg.sender == inv.buyer, "InvoiceRegistry: Only buyer can confirm");
        require(inv.status == InvoiceStatus.PENDING, "InvoiceRegistry: Invoice is not pending");

        inv.status = InvoiceStatus.CONFIRMED;
        emit InvoiceConfirmed(invoiceId, msg.sender);

        // F-08: Automatically mint equal receivable token to supplier
        receivableToken.mint(inv.supplier, invoiceId, inv.amount);
        emit ReceivableMinted(invoiceId, inv.supplier, inv.amount);
    }

    function rejectInvoice(uint256 invoiceId, string calldata reason) external whenNotPaused {
        Invoice storage inv = invoices[invoiceId];
        require(inv.id != 0, "InvoiceRegistry: Invoice not found");
        require(msg.sender == inv.buyer, "InvoiceRegistry: Only buyer can reject");
        require(inv.status == InvoiceStatus.PENDING, "InvoiceRegistry: Invoice is not pending");
        require(bytes(reason).length > 0, "InvoiceRegistry: Rejection reason required");

        inv.status = InvoiceStatus.REJECTED;
        inv.rejectReason = reason;

        emit InvoiceRejected(invoiceId, msg.sender, reason);
    }

    function getInvoice(uint256 invoiceId) external view returns (Invoice memory) {
        return invoices[invoiceId];
    }
}
