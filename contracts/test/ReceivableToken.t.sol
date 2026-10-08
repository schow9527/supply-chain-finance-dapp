// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC1155Errors} from "@openzeppelin/contracts/interfaces/draft-IERC6093.sol";
import {BaseTest} from "./Base.t.sol";
import {ReceivableToken} from "../contracts/ReceivableToken.sol";
import {RoleGuarded} from "../contracts/utils/RoleGuarded.sol";

contract ReceivableTokenTest is BaseTest {
    uint256 id;

    function setUp() public override {
        super.setUp();
        id = _submitAndConfirm();
    }

    function test_SplitTransferToSupplier() public {
        vm.prank(supplier);
        token.transferReceivable(supplier2, id, 3_000e6);
        assertEq(token.balanceOf(supplier, id), FACE - 3_000e6);
        assertEq(token.balanceOf(supplier2, id), 3_000e6);
    }

    function test_RevertWhen_TransferExceedsBalance() public {
        vm.prank(supplier);
        vm.expectRevert(
            abi.encodeWithSelector(IERC1155Errors.ERC1155InsufficientBalance.selector, supplier, FACE, FACE + 1, id)
        );
        token.transferReceivable(supplier2, id, FACE + 1);
    }

    function test_RevertWhen_TransferToNonSupplier() public {
        vm.startPrank(supplier);
        vm.expectRevert(abi.encodeWithSelector(ReceivableToken.InvalidRecipient.selector, stranger));
        token.transferReceivable(stranger, id, 1);
        vm.expectRevert(abi.encodeWithSelector(ReceivableToken.InvalidRecipient.selector, funder));
        token.transferReceivable(funder, id, 1);
        vm.stopPrank();
    }

    function test_RevertWhen_RawSafeTransferBypassesRules() public {
        vm.prank(supplier);
        vm.expectRevert(abi.encodeWithSelector(ReceivableToken.InvalidRecipient.selector, stranger));
        token.safeTransferFrom(supplier, stranger, id, 1, "");
    }

    function test_RevertWhen_TransferAfterMaturity() public {
        vm.warp(dueDate);
        vm.prank(supplier);
        vm.expectRevert(abi.encodeWithSelector(ReceivableToken.ReceivableMatured.selector, id, dueDate));
        token.transferReceivable(supplier2, id, 1);
    }

    function test_FreezeBlocksTransferUntilUnfrozen() public {
        vm.prank(auditor);
        token.freeze(id, "suspected fake invoice");
        assertTrue(token.getReceivable(id).frozen);

        vm.prank(supplier);
        vm.expectRevert(abi.encodeWithSelector(ReceivableToken.ReceivableIsFrozen.selector, id));
        token.transferReceivable(supplier2, id, 1);

        vm.prank(auditor);
        token.unfreeze(id, "verified with buyer");
        vm.prank(supplier);
        token.transferReceivable(supplier2, id, 1);
    }

    function test_RevertWhen_NonAuditorFreezes() public {
        bytes32 auditorRole = roles.AUDITOR();
        vm.prank(admin);
        vm.expectRevert(abi.encodeWithSelector(RoleGuarded.Unauthorized.selector, admin, auditorRole));
        token.freeze(id, "x");
    }

    function test_RevertWhen_FreezeWithoutReasonOrUnknownId() public {
        vm.startPrank(auditor);
        vm.expectRevert(ReceivableToken.ReasonRequired.selector);
        token.freeze(id, "");
        vm.expectRevert(abi.encodeWithSelector(ReceivableToken.ReceivableNotFound.selector, 999));
        token.freeze(999, "x");
        vm.stopPrank();
    }

    function test_RevertWhen_TransferWhilePaused() public {
        vm.prank(admin);
        roles.pause();
        vm.prank(supplier);
        vm.expectRevert(RoleGuarded.SystemPaused.selector);
        token.transferReceivable(supplier2, id, 1);
    }

    function test_RevertWhen_SystemContractsSetTwice() public {
        vm.prank(admin);
        vm.expectRevert(ReceivableToken.SystemContractsAlreadySet.selector);
        token.setSystemContracts(address(1), address(2));
    }

    function test_RevertWhen_BurnOrSetStatusCalledDirectly() public {
        vm.startPrank(supplier);
        vm.expectRevert(ReceivableToken.OnlyFinancingPool.selector);
        token.burn(supplier, id, 1);
        vm.expectRevert(ReceivableToken.OnlyFinancingPool.selector);
        token.setStatus(id, ReceivableToken.Status.Repaid);
        vm.stopPrank();
    }
}
