// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC1155Errors} from "@openzeppelin/contracts/interfaces/draft-IERC6093.sol";
import {BaseTest} from "./Base.t.sol";
import {FinancingPool} from "../contracts/FinancingPool.sol";
import {ReceivableToken} from "../contracts/ReceivableToken.sol";

contract FinancingPoolTest is BaseTest {
    uint256 id;

    function setUp() public override {
        super.setUp();
        id = _submitAndConfirm();
    }

    /// Main demo line: submit -> confirm -> request -> quote -> accept -> repay -> redeem.
    function test_FullLifecycle() public {
        uint256 requestId = _request(id, FACE);
        assertEq(token.balanceOf(address(pool), id), FACE);

        uint256 q1 = _quote(funder, requestId, 300); // 3%
        uint256 q2 = _quote(funder2, requestId, 250); // 2.5%
        uint256 payout = pool.previewPayout(FACE, 250);
        assertEq(payout, 9_750e6);

        uint256 supplierBefore = usd.balanceOf(supplier);
        vm.prank(supplier);
        pool.acceptQuote(requestId, q2);

        assertEq(usd.balanceOf(supplier) - supplierBefore, payout);
        assertEq(token.balanceOf(funder2, id), FACE);
        assertEq(token.balanceOf(address(pool), id), 0);
        assertEq(uint8(pool.getRequest(requestId).status), uint8(FinancingPool.RequestStatus.Funded));

        // losing funder gets escrow back
        uint256 funderBefore = usd.balanceOf(funder);
        vm.prank(funder);
        pool.withdrawQuote(q1);
        assertEq(usd.balanceOf(funder) - funderBefore, pool.previewPayout(FACE, 300));

        vm.warp(dueDate);
        vm.prank(core);
        pool.repay(id);
        assertEq(uint8(token.getReceivable(id).status), uint8(ReceivableToken.Status.Repaid));

        uint256 funder2Before = usd.balanceOf(funder2);
        vm.prank(funder2);
        pool.redeem(id);
        assertEq(usd.balanceOf(funder2) - funder2Before, FACE);
        assertEq(token.balanceOf(funder2, id), 0);
        assertEq(usd.balanceOf(address(pool)), 0);
    }

    function test_SplitHoldersRedeemProRata() public {
        vm.prank(supplier);
        token.transferReceivable(supplier2, id, 4_000e6);

        uint256 requestId = _request(id, 6_000e6);
        uint256 q = _quote(funder, requestId, 200);
        vm.prank(supplier);
        pool.acceptQuote(requestId, q);

        vm.prank(core);
        pool.repay(id);

        uint256 s2Before = usd.balanceOf(supplier2);
        vm.prank(supplier2);
        pool.redeem(id);
        assertEq(usd.balanceOf(supplier2) - s2Before, 4_000e6);

        vm.prank(funder);
        pool.redeem(id);
        assertEq(usd.balanceOf(address(pool)), 0);
    }

    function test_RevertWhen_DoubleFinancingSameAmount() public {
        _request(id, FACE);
        vm.prank(supplier);
        vm.expectRevert(abi.encodeWithSelector(IERC1155Errors.ERC1155InsufficientBalance.selector, supplier, 0, 1, id));
        pool.requestFinancing(id, 1);
    }

    function test_CancelReturnsVoucherAndBlocksAccept() public {
        uint256 requestId = _request(id, FACE);
        uint256 q = _quote(funder, requestId, 300);

        vm.prank(supplier);
        pool.cancelRequest(requestId);
        assertEq(token.balanceOf(supplier, id), FACE);

        vm.prank(supplier);
        vm.expectRevert(
            abi.encodeWithSelector(
                FinancingPool.RequestNotOpen.selector, requestId, FinancingPool.RequestStatus.Cancelled
            )
        );
        pool.acceptQuote(requestId, q);

        vm.prank(funder);
        pool.withdrawQuote(q);
    }

    function test_RevertWhen_AcceptByNonOwnerOrMismatchedQuote() public {
        uint256 r1 = _request(id, 5_000e6);
        uint256 r2 = _request(id, 5_000e6);
        uint256 q1 = _quote(funder, r1, 300);

        vm.prank(supplier2);
        vm.expectRevert(abi.encodeWithSelector(FinancingPool.NotRequestOwner.selector, r1, supplier2));
        pool.acceptQuote(r1, q1);

        vm.prank(supplier);
        vm.expectRevert(abi.encodeWithSelector(FinancingPool.QuoteRequestMismatch.selector, q1, r2));
        pool.acceptQuote(r2, q1);
    }

    function test_RevertWhen_AcceptWithdrawnQuote() public {
        uint256 requestId = _request(id, FACE);
        uint256 q = _quote(funder, requestId, 300);
        vm.prank(funder);
        pool.withdrawQuote(q);

        vm.prank(supplier);
        vm.expectRevert(
            abi.encodeWithSelector(FinancingPool.QuoteNotActive.selector, q, FinancingPool.QuoteStatus.Withdrawn)
        );
        pool.acceptQuote(requestId, q);
    }

    function test_RevertWhen_InvalidDiscount() public {
        uint256 requestId = _request(id, FACE);
        vm.prank(funder);
        vm.expectRevert(abi.encodeWithSelector(FinancingPool.InvalidDiscount.selector, uint16(10_000)));
        pool.submitQuote(requestId, 10_000);
    }

    function test_RevertWhen_FrozenVoucherFinancedOrRedeemed() public {
        uint256 requestId = _request(id, FACE);
        uint256 q = _quote(funder, requestId, 300);

        vm.prank(auditor);
        token.freeze(id, "under investigation");

        vm.prank(supplier);
        vm.expectRevert(abi.encodeWithSelector(FinancingPool.ReceivableIsFrozen.selector, id));
        pool.acceptQuote(requestId, q);

        vm.prank(auditor);
        token.unfreeze(id, "cleared");
        vm.prank(supplier);
        pool.acceptQuote(requestId, q);

        vm.prank(core);
        pool.repay(id);
        vm.prank(auditor);
        token.freeze(id, "dispute");
        vm.prank(funder);
        vm.expectRevert(abi.encodeWithSelector(FinancingPool.ReceivableIsFrozen.selector, id));
        pool.redeem(id);
    }

    function test_RevertWhen_NonBuyerRepaysOrRepayTwice() public {
        vm.prank(funder);
        vm.expectRevert(abi.encodeWithSelector(FinancingPool.NotReceivableBuyer.selector, id, funder));
        pool.repay(id);

        vm.prank(core);
        pool.repay(id);
        vm.prank(core);
        vm.expectRevert(
            abi.encodeWithSelector(FinancingPool.NotRepayable.selector, id, ReceivableToken.Status.Repaid)
        );
        pool.repay(id);
    }

    function test_RevertWhen_RedeemBeforeRepayment() public {
        vm.prank(supplier);
        vm.expectRevert(
            abi.encodeWithSelector(FinancingPool.NotRedeemable.selector, id, ReceivableToken.Status.Active)
        );
        pool.redeem(id);
    }

    function test_OverdueThenLateRepayment() public {
        uint256 requestId = _request(id, FACE);
        uint256 q = _quote(funder, requestId, 300);
        vm.prank(supplier);
        pool.acceptQuote(requestId, q);

        vm.prank(funder);
        vm.expectRevert(abi.encodeWithSelector(FinancingPool.NotOverdueYet.selector, id, dueDate));
        pool.markOverdue(id);

        vm.warp(dueDate + 1);
        vm.prank(funder);
        pool.markOverdue(id);
        assertEq(uint8(token.getReceivable(id).status), uint8(ReceivableToken.Status.Overdue));
        assertEq(pool.overdueCount(core), 1);

        vm.prank(core);
        pool.repay(id);
        vm.prank(funder);
        pool.redeem(id);
        assertEq(token.balanceOf(funder, id), 0);
    }

    function test_RevertWhen_NonHolderMarksOverdue() public {
        vm.warp(dueDate + 1);
        vm.prank(funder);
        vm.expectRevert(abi.encodeWithSelector(FinancingPool.NotReceivableHolder.selector, id, funder));
        pool.markOverdue(id);
    }

    function test_RevertWhen_FinancingAfterMaturity() public {
        vm.warp(dueDate);
        vm.prank(supplier);
        vm.expectRevert(abi.encodeWithSelector(FinancingPool.ReceivableNotFinanceable.selector, id));
        pool.requestFinancing(id, FACE);
    }

    function test_RevertWhen_FunderTransfersVoucherDirectly() public {
        uint256 requestId = _request(id, FACE);
        uint256 q = _quote(funder, requestId, 300);
        vm.prank(supplier);
        pool.acceptQuote(requestId, q);

        vm.prank(funder);
        vm.expectRevert(); // funder is not a SUPPLIER, so raw transfers are rejected
        token.safeTransferFrom(funder, supplier2, id, 1, "");
    }

    /// Pool always holds exactly: active quote escrow + repaid-but-unredeemed face value.
    function testFuzz_PoolSolvency(uint16 bps, uint96 amount) public {
        bps = uint16(bound(bps, 0, 9_999));
        uint256 amt = bound(amount, 1, FACE);

        uint256 requestId = _request(id, amt);
        uint256 q = _quote(funder, requestId, bps);
        vm.prank(supplier);
        pool.acceptQuote(requestId, q);
        assertEq(usd.balanceOf(address(pool)), 0);

        vm.prank(core);
        pool.repay(id);
        assertEq(usd.balanceOf(address(pool)), FACE);

        vm.prank(funder);
        pool.redeem(id);
        if (amt < FACE) {
            vm.prank(supplier);
            pool.redeem(id);
        }
        assertEq(usd.balanceOf(address(pool)), 0);
    }
}
