// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ERC1155Holder} from "@openzeppelin/contracts/token/ERC1155/utils/ERC1155Holder.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {RoleManager} from "./RoleManager.sol";
import {ReceivableToken} from "./ReceivableToken.sol";
import {RoleGuarded} from "./utils/RoleGuarded.sol";

/// @title FinancingPool
/// @notice Discount financing of receivable vouchers, maturity repayment and redemption.
///
///         Flow: supplier requests financing (voucher amount escrowed here) -> funders quote a
///         discount rate (payout escrowed here) -> supplier accepts one quote (voucher to funder,
///         payout to supplier, atomically) -> core enterprise repays face value at maturity ->
///         every holder redeems vouchers 1:1 for stablecoin.
contract FinancingPool is RoleGuarded, ERC1155Holder, ReentrancyGuard {
    using SafeERC20 for IERC20;

    uint16 public constant BPS = 10_000;

    enum RequestStatus {
        None,
        Open,
        Funded,
        Cancelled
    }

    enum QuoteStatus {
        None,
        Active,
        Accepted,
        Withdrawn
    }

    struct Request {
        uint256 receivableId;
        address supplier;
        RequestStatus status;
        uint256 amount; // voucher amount (face value units) escrowed
        uint256 acceptedQuoteId;
    }

    struct Quote {
        uint256 requestId;
        address funder;
        uint16 discountBps;
        QuoteStatus status;
        uint256 payout; // stablecoin escrowed; what the supplier receives
    }

    IERC20 public immutable stablecoin;
    ReceivableToken public immutable receivableToken;

    uint256 public requestCount;
    uint256 public quoteCount;
    mapping(uint256 => Request) private _requests;
    mapping(uint256 => Quote) private _quotes;
    /// @notice Number of receivables flagged overdue per core enterprise.
    mapping(address => uint256) public overdueCount;

    event FinancingRequested(
        uint256 indexed requestId, uint256 indexed receivableId, address indexed supplier, uint256 amount
    );
    event QuoteSubmitted(
        uint256 indexed quoteId, uint256 indexed requestId, address indexed funder, uint16 discountBps, uint256 payout
    );
    event QuoteWithdrawn(uint256 indexed quoteId, uint256 indexed requestId, address indexed funder);
    event FinancingFunded(
        uint256 indexed requestId,
        uint256 indexed quoteId,
        uint256 indexed receivableId,
        address supplier,
        address funder,
        uint256 amount,
        uint256 payout
    );
    event FinancingCancelled(uint256 indexed requestId, uint256 indexed receivableId, address indexed supplier);
    event Repaid(uint256 indexed receivableId, address indexed buyer, uint256 amount);
    event Redeemed(uint256 indexed receivableId, address indexed holder, uint256 amount);
    event MarkedOverdue(uint256 indexed receivableId, address indexed buyer, address indexed funder);

    error ZeroAmount();
    error RequestNotFound(uint256 requestId);
    error RequestNotOpen(uint256 requestId, RequestStatus status);
    error NotRequestOwner(uint256 requestId, address caller);
    error QuoteNotFound(uint256 quoteId);
    error QuoteNotActive(uint256 quoteId, QuoteStatus status);
    error QuoteRequestMismatch(uint256 quoteId, uint256 requestId);
    error NotQuoteOwner(uint256 quoteId, address caller);
    error InvalidDiscount(uint16 discountBps);
    error ReceivableNotFinanceable(uint256 receivableId);
    error NotReceivableBuyer(uint256 receivableId, address caller);
    error NotRepayable(uint256 receivableId, ReceivableToken.Status status);
    error NotRedeemable(uint256 receivableId, ReceivableToken.Status status);
    error ReceivableIsFrozen(uint256 receivableId);
    error NothingToRedeem(uint256 receivableId);
    error NotOverdueYet(uint256 receivableId, uint64 dueDate);
    error NotReceivableHolder(uint256 receivableId, address caller);

    constructor(RoleManager roleManager_, ReceivableToken receivableToken_, IERC20 stablecoin_)
        RoleGuarded(roleManager_)
    {
        receivableToken = receivableToken_;
        stablecoin = stablecoin_;
    }

    // ---------------------------------------------------------------------
    // Views
    // ---------------------------------------------------------------------

    function getRequest(uint256 requestId) external view returns (Request memory) {
        return _requests[requestId];
    }

    function getQuote(uint256 quoteId) external view returns (Quote memory) {
        return _quotes[quoteId];
    }

    function previewPayout(uint256 amount, uint16 discountBps) public pure returns (uint256) {
        return amount * (BPS - discountBps) / BPS;
    }

    // ---------------------------------------------------------------------
    // Financing
    // ---------------------------------------------------------------------

    /// @notice Escrows `amount` of the caller's voucher in this pool, so the same amount can
    ///         never back two open requests.
    function requestFinancing(uint256 receivableId, uint256 amount)
        external
        whenActive
        nonReentrant
        onlyRoleOf(roleManager.SUPPLIER())
        returns (uint256 requestId)
    {
        if (amount == 0) revert ZeroAmount();
        _requireFinanceable(receivableId);

        requestId = ++requestCount;
        _requests[requestId] = Request({
            receivableId: receivableId,
            supplier: msg.sender,
            status: RequestStatus.Open,
            amount: amount,
            acceptedQuoteId: 0
        });
        emit FinancingRequested(requestId, receivableId, msg.sender, amount);

        // Reverts with ERC1155InsufficientBalance if the caller does not hold enough.
        receivableToken.safeTransferFrom(msg.sender, address(this), receivableId, amount, "");
    }

    /// @notice Funder offers a discount rate; the resulting payout is escrowed immediately so that
    ///         acceptance can never fail for lack of funder balance or allowance.
    ///         Requires prior stablecoin.approve(pool, payout).
    function submitQuote(uint256 requestId, uint16 discountBps)
        external
        whenActive
        nonReentrant
        onlyRoleOf(roleManager.FUNDER())
        returns (uint256 quoteId)
    {
        if (discountBps >= BPS) revert InvalidDiscount(discountBps);
        Request storage req = _openRequest(requestId);
        _requireFinanceable(req.receivableId);

        uint256 payout = previewPayout(req.amount, discountBps);
        quoteId = ++quoteCount;
        _quotes[quoteId] = Quote({
            requestId: requestId,
            funder: msg.sender,
            discountBps: discountBps,
            status: QuoteStatus.Active,
            payout: payout
        });
        emit QuoteSubmitted(quoteId, requestId, msg.sender, discountBps, payout);

        stablecoin.safeTransferFrom(msg.sender, address(this), payout);
    }

    /// @notice Funder takes back an unaccepted quote (any time, including after the request closed).
    function withdrawQuote(uint256 quoteId) external whenActive nonReentrant {
        Quote storage q = _activeQuote(quoteId);
        if (q.funder != msg.sender) revert NotQuoteOwner(quoteId, msg.sender);

        q.status = QuoteStatus.Withdrawn;
        emit QuoteWithdrawn(quoteId, q.requestId, msg.sender);

        stablecoin.safeTransfer(msg.sender, q.payout);
    }

    /// @notice Atomic settlement: voucher -> funder and payout -> supplier in one transaction.
    function acceptQuote(uint256 requestId, uint256 quoteId) external whenActive nonReentrant {
        Request storage req = _openRequest(requestId);
        if (req.supplier != msg.sender) revert NotRequestOwner(requestId, msg.sender);
        Quote storage q = _activeQuote(quoteId);
        if (q.requestId != requestId) revert QuoteRequestMismatch(quoteId, requestId);
        _requireFinanceable(req.receivableId);

        req.status = RequestStatus.Funded;
        req.acceptedQuoteId = quoteId;
        q.status = QuoteStatus.Accepted;
        emit FinancingFunded(requestId, quoteId, req.receivableId, msg.sender, q.funder, req.amount, q.payout);

        receivableToken.safeTransferFrom(address(this), q.funder, req.receivableId, req.amount, "");
        stablecoin.safeTransfer(msg.sender, q.payout);
    }

    /// @notice Cancel before any quote is accepted; escrowed voucher returns to the supplier.
    ///         Other funders then withdraw their quotes via withdrawQuote.
    function cancelRequest(uint256 requestId) external whenActive nonReentrant {
        Request storage req = _openRequest(requestId);
        if (req.supplier != msg.sender) revert NotRequestOwner(requestId, msg.sender);

        req.status = RequestStatus.Cancelled;
        emit FinancingCancelled(requestId, req.receivableId, msg.sender);

        receivableToken.safeTransferFrom(address(this), msg.sender, req.receivableId, req.amount, "");
    }

    // ---------------------------------------------------------------------
    // Maturity
    // ---------------------------------------------------------------------

    /// @notice Core enterprise pays the full face value. Allowed before or after the due date
    ///         (including once flagged overdue). Requires prior stablecoin.approve(pool, faceValue).
    function repay(uint256 receivableId) external whenActive nonReentrant {
        ReceivableToken.Receivable memory r = receivableToken.getReceivable(receivableId);
        if (r.buyer != msg.sender) revert NotReceivableBuyer(receivableId, msg.sender);
        if (r.status != ReceivableToken.Status.Active && r.status != ReceivableToken.Status.Overdue) {
            revert NotRepayable(receivableId, r.status);
        }

        receivableToken.setStatus(receivableId, ReceivableToken.Status.Repaid);
        emit Repaid(receivableId, msg.sender, r.faceValue);

        stablecoin.safeTransferFrom(msg.sender, address(this), r.faceValue);
    }

    /// @notice Current holder burns all of their voucher units and receives stablecoin 1:1.
    function redeem(uint256 receivableId) external whenActive nonReentrant {
        ReceivableToken.Receivable memory r = receivableToken.getReceivable(receivableId);
        if (r.status != ReceivableToken.Status.Repaid) revert NotRedeemable(receivableId, r.status);
        if (r.frozen) revert ReceivableIsFrozen(receivableId);
        uint256 balance = receivableToken.balanceOf(msg.sender, receivableId);
        if (balance == 0) revert NothingToRedeem(receivableId);

        receivableToken.burn(msg.sender, receivableId, balance);
        emit Redeemed(receivableId, msg.sender, balance);

        stablecoin.safeTransfer(msg.sender, balance);
    }

    /// @notice A funder holding the voucher flags it overdue once past due and unpaid.
    function markOverdue(uint256 receivableId)
        external
        whenActive
        nonReentrant
        onlyRoleOf(roleManager.FUNDER())
    {
        ReceivableToken.Receivable memory r = receivableToken.getReceivable(receivableId);
        if (receivableToken.balanceOf(msg.sender, receivableId) == 0) {
            revert NotReceivableHolder(receivableId, msg.sender);
        }
        if (r.status != ReceivableToken.Status.Active) revert NotRepayable(receivableId, r.status);
        if (block.timestamp <= r.dueDate) revert NotOverdueYet(receivableId, r.dueDate);

        overdueCount[r.buyer] += 1;
        emit MarkedOverdue(receivableId, r.buyer, msg.sender);

        receivableToken.setStatus(receivableId, ReceivableToken.Status.Overdue);
    }

    // ---------------------------------------------------------------------
    // Internal
    // ---------------------------------------------------------------------

    function _requireFinanceable(uint256 receivableId) private view {
        ReceivableToken.Receivable memory r = receivableToken.getReceivable(receivableId);
        if (r.frozen) revert ReceivableIsFrozen(receivableId);
        if (r.status != ReceivableToken.Status.Active || block.timestamp >= r.dueDate) {
            revert ReceivableNotFinanceable(receivableId);
        }
    }

    function _openRequest(uint256 requestId) private view returns (Request storage req) {
        req = _requests[requestId];
        if (req.status == RequestStatus.None) revert RequestNotFound(requestId);
        if (req.status != RequestStatus.Open) revert RequestNotOpen(requestId, req.status);
    }

    function _activeQuote(uint256 quoteId) private view returns (Quote storage q) {
        q = _quotes[quoteId];
        if (q.status == QuoteStatus.None) revert QuoteNotFound(quoteId);
        if (q.status != QuoteStatus.Active) revert QuoteNotActive(quoteId, q.status);
    }
}
