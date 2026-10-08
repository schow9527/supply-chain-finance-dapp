// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {BaseTest} from "./Base.t.sol";

/// @notice Records the gas of every business transaction once, in a fixed scenario, so that
///         optimisations can be compared before/after. Run with:
///         forge test --match-contract GasBenchmark --isolate
///         Results are written to snapshots/GasBenchmark.json.
contract GasBenchmark is BaseTest {
    string constant GROUP = "GasBenchmark";

    function test_GasMainFlow() public {
        vm.prank(supplier);
        uint256 id = registry.submitInvoice("INV-001", core, FACE, dueDate, FILE_HASH);
        vm.snapshotGasLastCall(GROUP, "submitInvoice");

        vm.prank(core);
        registry.confirmInvoice(id);
        vm.snapshotGasLastCall(GROUP, "confirmInvoice");

        vm.prank(supplier);
        token.transferReceivable(supplier2, id, 2_000e6);
        vm.snapshotGasLastCall(GROUP, "transferReceivable");

        vm.prank(supplier);
        uint256 requestId = pool.requestFinancing(id, 8_000e6);
        vm.snapshotGasLastCall(GROUP, "requestFinancing");

        vm.prank(funder);
        uint256 q1 = pool.submitQuote(requestId, 300);
        vm.snapshotGasLastCall(GROUP, "submitQuote");

        vm.prank(funder2);
        uint256 q2 = pool.submitQuote(requestId, 250);

        vm.prank(supplier);
        pool.acceptQuote(requestId, q2);
        vm.snapshotGasLastCall(GROUP, "acceptQuote");

        vm.prank(funder);
        pool.withdrawQuote(q1);
        vm.snapshotGasLastCall(GROUP, "withdrawQuote");

        vm.prank(core);
        pool.repay(id);
        vm.snapshotGasLastCall(GROUP, "repay");

        vm.prank(funder2);
        pool.redeem(id);
        vm.snapshotGasLastCall(GROUP, "redeem");
    }

    function test_GasSideFlows() public {
        vm.prank(supplier);
        uint256 rejected = registry.submitInvoice("INV-R", core, FACE, dueDate, FILE_HASH);
        vm.prank(core);
        registry.rejectInvoice(rejected, "wrong amount");
        vm.snapshotGasLastCall(GROUP, "rejectInvoice");

        uint256 id = _submitAndConfirm();

        vm.prank(auditor);
        token.freeze(id, "suspicious");
        vm.snapshotGasLastCall(GROUP, "freeze");

        vm.prank(auditor);
        token.unfreeze(id, "cleared");
        vm.snapshotGasLastCall(GROUP, "unfreeze");

        uint256 requestId = _request(id, FACE);
        vm.prank(supplier);
        pool.cancelRequest(requestId);
        vm.snapshotGasLastCall(GROUP, "cancelRequest");

        requestId = _request(id, FACE);
        uint256 q = _quote(funder, requestId, 300);
        vm.prank(supplier);
        pool.acceptQuote(requestId, q);

        vm.warp(dueDate + 1);
        vm.prank(funder);
        pool.markOverdue(id);
        vm.snapshotGasLastCall(GROUP, "markOverdue");
    }

    function test_GasAdmin() public {
        address newcomer = makeAddr("newcomer");
        bytes32 supplierRole = roles.SUPPLIER();

        vm.prank(admin);
        roles.grantRole(supplierRole, newcomer);
        vm.snapshotGasLastCall(GROUP, "grantRole");

        vm.prank(admin);
        roles.revokeRole(supplierRole, newcomer);
        vm.snapshotGasLastCall(GROUP, "revokeRole");

        vm.prank(admin);
        roles.pause();
        vm.snapshotGasLastCall(GROUP, "pause");

        vm.prank(newcomer);
        usd.faucet();
        vm.snapshotGasLastCall(GROUP, "faucet");
    }
}
