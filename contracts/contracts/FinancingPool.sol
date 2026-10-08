// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./RoleManager.sol";
import "./ReceivableToken.sol";
import "./InvoiceRegistry.sol";
import "./MockStablecoin.sol";

/**
 * @title FinancingPool
 * @dev Manages financing requests, quotes, atomic funding, repayment, redemption, and overdue marking.
 * Matches PRD sections 5 & 6.
 */
contract FinancingPool {
    RoleManager public roleManager;
    ReceivableToken public receivableToken;
    InvoiceRegistry public invoiceRegistry;
    MockStablecoin public stablecoin;

    enum RequestStatus { PENDING_QUOTE, FUNDED, CANCELLED }
    enum RepayStatus { UNPAID, REPAID, OVERDUE }

    struct FinancingRequest {
        uint256 requestId;
        uint256 receivableId;
        address supplier;
        uint256 amount;
        RequestStatus status;
        uint256 acceptedQuoteId;
    }

    struct Quote {
        uint256 quoteId;
        uint256 requestId;
        address financier;
        uint256 discountRateBps; // e.g. 500 = 5.00%
        bool exists;
    }

    uint256 public nextRequestId = 1;
    uint256 public nextQuoteId = 1;

    // requestId => FinancingRequest
    mapping(uint256 => FinancingRequest) public requests;
    // quoteId => Quote
    mapping(uint256 => Quote) public quotes;
    // requestId => list of quoteIds
    mapping(uint256 => uint256[]) private _requestQuotes;

    // receivableId => RepayStatus
    mapping(uint256 => RepayStatus) public invoiceRepayStatus;
    // receivableId => total repaid stablecoin deposited
    mapping(uint256 => uint256) public repaidFunds;

    event FinancingRequested(uint256 indexed requestId, address indexed supplier, uint256 indexed receivableId, uint256 amount);
    event QuoteSubmitted(uint256 indexed requestId, uint256 indexed quoteId, address indexed financier, uint256 discountRateBps);
    event FinancingFunded(uint256 indexed requestId, uint256 indexed quoteId, address indexed supplier, address financier, uint256 fundedAmount);
    event FinancingCancelled(uint256 indexed requestId);
    event Repaid(uint256 indexed receivableId, address indexed buyer, uint256 amount);
    event Redeemed(uint256 indexed receivableId, address indexed holder, uint256 amount);
    event MarkedOverdue(uint256 indexed receivableId, address indexed buyer, address indexed marker);

    modifier onlySupplier() {
        require(roleManager.hasRole(roleManager.SUPPLIER_ROLE(), msg.sender), "FinancingPool: Caller is not Supplier");
        _;
    }

    modifier onlyFinancier() {
        require(roleManager.hasRole(roleManager.FINANCIER_ROLE(), msg.sender), "FinancingPool: Caller is not Financier");
        _;
    }

    modifier whenNotPaused() {
        require(!roleManager.isPaused(), "FinancingPool: System is paused");
        _;
    }

    constructor(
        address _roleManager,
        address _receivableToken,
        address _invoiceRegistry,
        address _stablecoin
    ) {
        roleManager = RoleManager(_roleManager);
        receivableToken = ReceivableToken(_receivableToken);
        invoiceRegistry = InvoiceRegistry(_invoiceRegistry);
        stablecoin = MockStablecoin(_stablecoin);
    }

    function requestFinancing(uint256 receivableId, uint256 amount) external onlySupplier whenNotPaused returns (uint256) {
        require(amount > 0, "FinancingPool: Amount must be > 0");
        require(!receivableToken.isFrozen(receivableId), "FinancingPool: Receivable is frozen");
        require(receivableToken.balanceOf(msg.sender, receivableId) >= amount, "FinancingPool: Insufficient balance");

        // Escrow receivable tokens to FinancingPool contract
        receivableToken.transferFrom(msg.sender, address(this), receivableId, amount);

        uint256 reqId = nextRequestId++;
        requests[reqId] = FinancingRequest({
            requestId: reqId,
            receivableId: receivableId,
            supplier: msg.sender,
            amount: amount,
            status: RequestStatus.PENDING_QUOTE,
            acceptedQuoteId: 0
        });

        emit FinancingRequested(reqId, msg.sender, receivableId, amount);
        return reqId;
    }

    function submitQuote(uint256 requestId, uint256 discountRateBps) external onlyFinancier whenNotPaused returns (uint256) {
        FinancingRequest storage req = requests[requestId];
        require(req.requestId != 0, "FinancingPool: Request not found");
        require(req.status == RequestStatus.PENDING_QUOTE, "FinancingPool: Request is not pending quote");
        require(discountRateBps < 10000, "FinancingPool: Discount rate must be < 100%");

        uint256 qId = nextQuoteId++;
        quotes[qId] = Quote({
            quoteId: qId,
            requestId: requestId,
            financier: msg.sender,
            discountRateBps: discountRateBps,
            exists: true
        });

        _requestQuotes[requestId].push(qId);
        emit QuoteSubmitted(requestId, qId, msg.sender, discountRateBps);
        return qId;
    }

    function getQuotesForRequest(uint256 requestId) external view returns (uint256[] memory) {
        return _requestQuotes[requestId];
    }

    function acceptQuote(uint256 requestId, uint256 quoteId) external whenNotPaused {
        FinancingRequest storage req = requests[requestId];
        require(req.requestId != 0, "FinancingPool: Request not found");
        require(req.status == RequestStatus.PENDING_QUOTE, "FinancingPool: Request already closed");
        require(msg.sender == req.supplier, "FinancingPool: Only supplier can accept quote");

        Quote storage q = quotes[quoteId];
        require(q.exists && q.requestId == requestId, "FinancingPool: Invalid quote for this request");

        // Check frozen status
        require(!receivableToken.isFrozen(req.receivableId), "FinancingPool: Receivable is frozen");

        // Calculate funded amount: amount * (10000 - discountRateBps) / 10000
        uint256 fundedAmount = (req.amount * (10000 - q.discountRateBps)) / 10000;

        // Update state first (Checks-Effects-Interactions pattern)
        req.status = RequestStatus.FUNDED;
        req.acceptedQuoteId = quoteId;

        // 1. Transfer stablecoin from Financier directly to Supplier
        bool success = stablecoin.transferFrom(q.financier, req.supplier, fundedAmount);
        require(success, "FinancingPool: Stablecoin transfer failed");

        // 2. Transfer escrowed receivable tokens from FinancingPool to Financier
        receivableToken.transferReceivable(q.financier, req.receivableId, req.amount);

        emit FinancingFunded(requestId, quoteId, req.supplier, q.financier, fundedAmount);
    }

    function cancelRequest(uint256 requestId) external whenNotPaused {
        FinancingRequest storage req = requests[requestId];
        require(req.requestId != 0, "FinancingPool: Request not found");
        require(msg.sender == req.supplier, "FinancingPool: Only supplier can cancel");
        require(req.status == RequestStatus.PENDING_QUOTE, "FinancingPool: Cannot cancel non-pending request");

        req.status = RequestStatus.CANCELLED;

        // Return escrowed receivable tokens to Supplier
        receivableToken.transferReceivable(req.supplier, req.receivableId, req.amount);

        emit FinancingCancelled(requestId);
    }

    function repay(uint256 receivableId) external whenNotPaused {
        InvoiceRegistry.Invoice memory inv = invoiceRegistry.getInvoice(receivableId);
        require(inv.id != 0, "FinancingPool: Invoice not found");
        require(msg.sender == inv.buyer, "FinancingPool: Only core enterprise can repay");
        require(invoiceRepayStatus[receivableId] != RepayStatus.REPAID, "FinancingPool: Already repaid");

        invoiceRepayStatus[receivableId] = RepayStatus.REPAID;
        repaidFunds[receivableId] += inv.amount;

        // Core enterprise pays total invoice amount to FinancingPool contract
        bool success = stablecoin.transferFrom(msg.sender, address(this), inv.amount);
        require(success, "FinancingPool: Repay stablecoin transfer failed");

        emit Repaid(receivableId, msg.sender, inv.amount);
    }

    function redeem(uint256 receivableId) external whenNotPaused {
        require(invoiceRepayStatus[receivableId] == RepayStatus.REPAID, "FinancingPool: Invoice not yet repaid");
        require(!receivableToken.isFrozen(receivableId), "FinancingPool: Receivable is frozen");

        uint256 balance = receivableToken.balanceOf(msg.sender, receivableId);
        require(balance > 0, "FinancingPool: No receivable balance to redeem");
        require(repaidFunds[receivableId] >= balance, "FinancingPool: Insufficient pool funds");

        repaidFunds[receivableId] -= balance;

        // Burn the caller's receivable tokens
        receivableToken.burn(msg.sender, receivableId, balance);

        // Send 1:1 stablecoin to caller
        bool success = stablecoin.transfer(msg.sender, balance);
        require(success, "FinancingPool: Stablecoin redemption transfer failed");

        emit Redeemed(receivableId, msg.sender, balance);
    }

    function markOverdue(uint256 receivableId) external onlyFinancier whenNotPaused {
        InvoiceRegistry.Invoice memory inv = invoiceRegistry.getInvoice(receivableId);
        require(inv.id != 0, "FinancingPool: Invoice not found");
        require(block.timestamp > inv.dueDate, "FinancingPool: Invoice is not past due date");
        require(invoiceRepayStatus[receivableId] != RepayStatus.REPAID, "FinancingPool: Invoice already repaid");

        invoiceRepayStatus[receivableId] = RepayStatus.OVERDUE;
        emit MarkedOverdue(receivableId, inv.buyer, msg.sender);
    }
}
