// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {RoleManager} from "../contracts/RoleManager.sol";
import {ReceivableToken} from "../contracts/ReceivableToken.sol";
import {InvoiceRegistry} from "../contracts/InvoiceRegistry.sol";
import {FinancingPool} from "../contracts/FinancingPool.sol";
import {MockStablecoin} from "../contracts/MockStablecoin.sol";

/// @dev Deploys and wires the full system with one account per role.
abstract contract BaseTest is Test {
    RoleManager roles;
    ReceivableToken token;
    InvoiceRegistry registry;
    FinancingPool pool;
    MockStablecoin usd;

    address admin = makeAddr("admin");
    address supplier = makeAddr("supplier");
    address supplier2 = makeAddr("supplier2");
    address core = makeAddr("core");
    address funder = makeAddr("funder");
    address funder2 = makeAddr("funder2");
    address auditor = makeAddr("auditor");
    address stranger = makeAddr("stranger");

    uint256 constant FACE = 10_000e6;
    uint64 dueDate;
    bytes32 constant FILE_HASH = keccak256("invoice.pdf");

    function setUp() public virtual {
        vm.warp(1_760_000_000);
        dueDate = uint64(block.timestamp + 90 days);

        vm.startPrank(admin);
        roles = new RoleManager(admin);
        token = new ReceivableToken(roles);
        usd = new MockStablecoin();
        registry = new InvoiceRegistry(roles, token);
        pool = new FinancingPool(roles, token, usd);
        token.setSystemContracts(address(registry), address(pool));

        roles.grantRole(roles.SUPPLIER(), supplier);
        roles.grantRole(roles.SUPPLIER(), supplier2);
        roles.grantRole(roles.CORE_ENTERPRISE(), core);
        roles.grantRole(roles.FUNDER(), funder);
        roles.grantRole(roles.FUNDER(), funder2);
        roles.grantRole(roles.AUDITOR(), auditor);
        vm.stopPrank();

        address[3] memory payers = [core, funder, funder2];
        for (uint256 i; i < payers.length; ++i) {
            vm.startPrank(payers[i]);
            usd.faucet();
            usd.approve(address(pool), type(uint256).max);
            vm.stopPrank();
        }
    }

    // ---- helpers ----

    function _submit(string memory invoiceNo) internal returns (uint256 id) {
        vm.prank(supplier);
        id = registry.submitInvoice(invoiceNo, core, FACE, dueDate, FILE_HASH);
    }

    function _submitAndConfirm() internal returns (uint256 id) {
        id = _submit("INV-001");
        vm.prank(core);
        registry.confirmInvoice(id);
    }

    function _request(uint256 id, uint256 amount) internal returns (uint256 requestId) {
        vm.prank(supplier);
        requestId = pool.requestFinancing(id, amount);
    }

    function _quote(address who, uint256 requestId, uint16 bps) internal returns (uint256 quoteId) {
        vm.prank(who);
        quoteId = pool.submitQuote(requestId, bps);
    }
}
