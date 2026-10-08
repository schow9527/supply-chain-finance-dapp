// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC1155} from "@openzeppelin/contracts/token/ERC1155/ERC1155.sol";
import {SafeCast} from "@openzeppelin/contracts/utils/math/SafeCast.sol";
import {RoleManager} from "./RoleManager.sol";
import {RoleGuarded} from "./utils/RoleGuarded.sol";
import {Roles} from "./utils/Roles.sol";

/// @title ReceivableToken
/// @notice ERC-1155 receivable vouchers. Token id == confirmed invoice id; amount == face value
///         in stablecoin base units, so a voucher can be split across many holders.
///         Only InvoiceRegistry mints, only FinancingPool burns / changes repayment status.
contract ReceivableToken is ERC1155, RoleGuarded {
    enum Status {
        None,
        Active, // confirmed, not yet repaid
        Repaid, // core enterprise paid; holders may redeem 1:1
        Overdue // past due and unpaid, flagged by a funder
    }

    /// @dev Packed into 2 storage slots (uint96 covers 7.9e22 mUSD at 6 decimals).
    struct Receivable {
        // slot 0
        address buyer; // core enterprise that owes the money
        uint64 dueDate;
        Status status;
        bool frozen;
        // slot 1
        address originalSupplier;
        uint96 faceValue;
    }

    mapping(uint256 => Receivable) private _receivables;

    address public invoiceRegistry;
    address public financingPool;

    event SystemContractsSet(address invoiceRegistry, address financingPool);
    event ReceivableMinted(
        uint256 indexed id, address indexed supplier, address indexed buyer, uint256 faceValue, uint64 dueDate
    );
    event ReceivableTransferred(uint256 indexed id, address indexed from, address indexed to, uint256 amount);
    event ReceivableFrozen(uint256 indexed id, address indexed auditor, string reason);
    event ReceivableUnfrozen(uint256 indexed id, address indexed auditor, string reason);
    event ReceivableStatusChanged(uint256 indexed id, Status status);

    error SystemContractsAlreadySet();
    error ZeroAddress();
    error OnlyInvoiceRegistry();
    error OnlyFinancingPool();
    error ReceivableNotFound(uint256 id);
    error ReceivableAlreadyExists(uint256 id);
    error ReceivableIsFrozen(uint256 id);
    error ReceivableNotFrozen(uint256 id);
    error ReceivableNotActive(uint256 id, Status status);
    error ReceivableMatured(uint256 id, uint64 dueDate);
    error InvalidRecipient(address to);
    error ReasonRequired();
    error ZeroAmount();

    constructor(RoleManager roleManager_) ERC1155("") RoleGuarded(roleManager_) {}

    modifier onlyInvoiceRegistry() {
        _onlyInvoiceRegistry();
        _;
    }

    modifier onlyFinancingPool() {
        _onlyFinancingPool();
        _;
    }

    function _onlyInvoiceRegistry() private view {
        if (msg.sender != invoiceRegistry) revert OnlyInvoiceRegistry();
    }

    function _onlyFinancingPool() private view {
        if (msg.sender != financingPool) revert OnlyFinancingPool();
    }

    // ---------------------------------------------------------------------
    // Admin wiring (one-time)
    // ---------------------------------------------------------------------

    function setSystemContracts(address invoiceRegistry_, address financingPool_)
        external
        onlyRoleOf(Roles.ADMIN)
    {
        if (invoiceRegistry != address(0)) revert SystemContractsAlreadySet();
        if (invoiceRegistry_ == address(0) || financingPool_ == address(0)) revert ZeroAddress();
        invoiceRegistry = invoiceRegistry_;
        financingPool = financingPool_;
        emit SystemContractsSet(invoiceRegistry_, financingPool_);
    }

    // ---------------------------------------------------------------------
    // Views
    // ---------------------------------------------------------------------

    function getReceivable(uint256 id) external view returns (Receivable memory) {
        return _receivables[id];
    }

    /// @notice FinancingPool may move any holder's vouchers without a separate
    ///         setApprovalForAll transaction; it only does so on the holder's own request.
    function isApprovedForAll(address account, address operator) public view override returns (bool) {
        return operator == financingPool || super.isApprovedForAll(account, operator);
    }

    // ---------------------------------------------------------------------
    // User actions
    // ---------------------------------------------------------------------

    /// @notice Split-transfer part of a voucher to another registered supplier.
    /// @dev The sender's SUPPLIER role is enforced in _update.
    function transferReceivable(address to, uint256 id, uint256 amount) external {
        if (amount == 0) revert ZeroAmount();
        safeTransferFrom(msg.sender, to, id, amount, "");
        emit ReceivableTransferred(id, msg.sender, to, amount);
    }

    function freeze(uint256 id, string calldata reason) external onlyRoleOf(Roles.AUDITOR) {
        Receivable storage r = _existing(id);
        if (r.frozen) revert ReceivableIsFrozen(id);
        if (bytes(reason).length == 0) revert ReasonRequired();
        r.frozen = true;
        emit ReceivableFrozen(id, msg.sender, reason);
    }

    function unfreeze(uint256 id, string calldata reason) external onlyRoleOf(Roles.AUDITOR) {
        Receivable storage r = _existing(id);
        if (!r.frozen) revert ReceivableNotFrozen(id);
        if (bytes(reason).length == 0) revert ReasonRequired();
        r.frozen = false;
        emit ReceivableUnfrozen(id, msg.sender, reason);
    }

    // ---------------------------------------------------------------------
    // System hooks
    // ---------------------------------------------------------------------

    function mint(address supplier, uint256 id, address buyer, uint256 faceValue, uint64 dueDate)
        external
        onlyInvoiceRegistry
    {
        if (_receivables[id].status != Status.None) revert ReceivableAlreadyExists(id);
        if (faceValue == 0) revert ZeroAmount();
        _receivables[id] = Receivable({
            buyer: buyer,
            dueDate: dueDate,
            status: Status.Active,
            frozen: false,
            originalSupplier: supplier,
            faceValue: SafeCast.toUint96(faceValue)
        });
        _mint(supplier, id, faceValue, "");
        emit ReceivableMinted(id, supplier, buyer, faceValue, dueDate);
    }

    function burn(address holder, uint256 id, uint256 amount) external onlyFinancingPool {
        _burn(holder, id, amount);
    }

    function setStatus(uint256 id, Status status) external onlyFinancingPool {
        _existing(id).status = status;
        emit ReceivableStatusChanged(id, status);
    }

    // ---------------------------------------------------------------------
    // Transfer rules
    // ---------------------------------------------------------------------

    /// @dev Enforced on every holder-to-holder move (mint / burn are gated by their callers):
    ///      - system not paused, voucher not frozen
    ///      - FinancingPool may move vouchers between pool, suppliers and funders
    ///      - anyone else: only supplier -> supplier, only while Active and before the due date
    function _update(address from, address to, uint256[] memory ids, uint256[] memory values) internal override {
        if (from != address(0) && to != address(0)) {
            _checkNotPaused();
            bool byPool = msg.sender == financingPool;
            if (byPool) {
                if (to != financingPool) {
                    bytes32 toRole = roleManager.roleOf(to);
                    if (toRole != Roles.SUPPLIER && toRole != Roles.FUNDER) revert InvalidRecipient(to);
                }
            } else {
                if (roleManager.roleOf(from) != Roles.SUPPLIER) revert Unauthorized(from, Roles.SUPPLIER);
                if (roleManager.roleOf(to) != Roles.SUPPLIER) revert InvalidRecipient(to);
            }
            for (uint256 i; i < ids.length; ++i) {
                Receivable storage r = _receivables[ids[i]];
                if (r.frozen) revert ReceivableIsFrozen(ids[i]);
                if (!byPool) {
                    if (r.status != Status.Active) revert ReceivableNotActive(ids[i], r.status);
                    if (block.timestamp >= r.dueDate) revert ReceivableMatured(ids[i], r.dueDate);
                }
            }
        }
        super._update(from, to, ids, values);
    }

    function _existing(uint256 id) private view returns (Receivable storage r) {
        r = _receivables[id];
        if (r.status == Status.None) revert ReceivableNotFound(id);
    }
}
