// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {SafeCast} from "@openzeppelin/contracts/utils/math/SafeCast.sol";
import {RoleManager} from "./RoleManager.sol";
import {ReceivableToken} from "./ReceivableToken.sol";
import {RoleGuarded} from "./utils/RoleGuarded.sol";
import {Roles} from "./utils/Roles.sol";

/// @title InvoiceRegistry
/// @notice Suppliers register invoices (PDF kept off-chain, its hash on-chain); the named core
///         enterprise confirms or rejects. Confirmation mints an equal-value receivable voucher.
contract InvoiceRegistry is RoleGuarded {
    enum InvoiceStatus {
        None,
        Pending,
        Confirmed,
        Rejected
    }

    /// @dev Packed into 4 storage slots. The invoice number itself is only emitted in
    ///      InvoiceSubmitted (the backend indexes it); on-chain we keep its dedup key.
    struct Invoice {
        // slot 0
        address supplier;
        uint64 dueDate;
        InvoiceStatus status;
        // slot 1
        address buyer;
        uint96 amount;
        // slot 2
        bytes32 fileHash; // hash of the off-chain PDF
        // slot 3
        bytes32 dedupKey; // keccak256(invoiceNo, supplier, buyer, amount)
    }

    ReceivableToken public immutable receivableToken;

    uint256 public invoiceCount;
    mapping(uint256 => Invoice) private _invoices;
    /// @notice dedupKey => invoice id currently holding it (0 if free).
    mapping(bytes32 => uint256) public invoiceIdByKey;

    event InvoiceSubmitted(
        uint256 indexed invoiceId,
        address indexed supplier,
        address indexed buyer,
        string invoiceNo,
        uint256 amount,
        uint64 dueDate,
        bytes32 fileHash
    );
    event InvoiceConfirmed(uint256 indexed invoiceId, address indexed buyer);
    event InvoiceRejected(uint256 indexed invoiceId, address indexed buyer, string reason);

    error InvoiceAlreadyExists(uint256 existingInvoiceId);
    error InvoiceNotFound(uint256 invoiceId);
    error InvoiceNotPending(uint256 invoiceId, InvoiceStatus status);
    error NotInvoiceBuyer(uint256 invoiceId, address caller);
    error InvalidBuyer(address buyer);
    error InvalidAmount();
    error InvalidDueDate(uint64 dueDate);
    error InvalidFileHash();
    error InvalidInvoiceNo();
    error SupplierNoLongerRegistered(address supplier);
    error ReasonRequired();

    constructor(RoleManager roleManager_, ReceivableToken receivableToken_) RoleGuarded(roleManager_) {
        receivableToken = receivableToken_;
    }

    function computeDedupKey(string calldata invoiceNo, address supplier, address buyer, uint256 amount)
        public
        pure
        returns (bytes32)
    {
        return keccak256(abi.encode(invoiceNo, supplier, buyer, amount));
    }

    function getInvoice(uint256 invoiceId) external view returns (Invoice memory) {
        return _invoices[invoiceId];
    }

    function submitInvoice(
        string calldata invoiceNo,
        address buyer,
        uint256 amount,
        uint64 dueDate,
        bytes32 fileHash
    ) external whenActive onlyRoleOf(Roles.SUPPLIER) returns (uint256 invoiceId) {
        if (bytes(invoiceNo).length == 0) revert InvalidInvoiceNo();
        if (!roleManager.hasRole(Roles.CORE_ENTERPRISE, buyer)) revert InvalidBuyer(buyer);
        if (amount == 0) revert InvalidAmount();
        if (dueDate <= block.timestamp) revert InvalidDueDate(dueDate);
        if (fileHash == bytes32(0)) revert InvalidFileHash();

        bytes32 key = computeDedupKey(invoiceNo, msg.sender, buyer, amount);
        uint256 existing = invoiceIdByKey[key];
        if (existing != 0) revert InvoiceAlreadyExists(existing);

        invoiceId = ++invoiceCount;
        invoiceIdByKey[key] = invoiceId;
        _invoices[invoiceId] = Invoice({
            supplier: msg.sender,
            dueDate: dueDate,
            status: InvoiceStatus.Pending,
            buyer: buyer,
            amount: SafeCast.toUint96(amount),
            fileHash: fileHash,
            dedupKey: key
        });

        emit InvoiceSubmitted(invoiceId, msg.sender, buyer, invoiceNo, amount, dueDate, fileHash);
    }

    function confirmInvoice(uint256 invoiceId) external whenActive onlyRoleOf(Roles.CORE_ENTERPRISE) {
        Invoice storage inv = _pendingInvoiceOfCaller(invoiceId);
        if (inv.dueDate <= block.timestamp) revert InvalidDueDate(inv.dueDate);
        if (!roleManager.hasRole(Roles.SUPPLIER, inv.supplier)) {
            revert SupplierNoLongerRegistered(inv.supplier);
        }

        inv.status = InvoiceStatus.Confirmed;
        emit InvoiceConfirmed(invoiceId, msg.sender);

        receivableToken.mint(inv.supplier, invoiceId, inv.buyer, inv.amount, inv.dueDate);
    }

    /// @notice Rejection releases the dedup key so a corrected invoice can be resubmitted.
    function rejectInvoice(uint256 invoiceId, string calldata reason)
        external
        whenActive
        onlyRoleOf(Roles.CORE_ENTERPRISE)
    {
        if (bytes(reason).length == 0) revert ReasonRequired();
        Invoice storage inv = _pendingInvoiceOfCaller(invoiceId);

        inv.status = InvoiceStatus.Rejected;
        delete invoiceIdByKey[inv.dedupKey];
        emit InvoiceRejected(invoiceId, msg.sender, reason);
    }

    function _pendingInvoiceOfCaller(uint256 invoiceId) private view returns (Invoice storage inv) {
        inv = _invoices[invoiceId];
        if (inv.status == InvoiceStatus.None) revert InvoiceNotFound(invoiceId);
        if (inv.buyer != msg.sender) revert NotInvoiceBuyer(invoiceId, msg.sender);
        if (inv.status != InvoiceStatus.Pending) revert InvoiceNotPending(invoiceId, inv.status);
    }
}
