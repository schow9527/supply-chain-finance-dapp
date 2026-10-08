// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {SafeCast} from "@openzeppelin/contracts/utils/math/SafeCast.sol";
import {BaseTest} from "./Base.t.sol";
import {InvoiceRegistry} from "../contracts/InvoiceRegistry.sol";
import {ReceivableToken} from "../contracts/ReceivableToken.sol";
import {RoleGuarded} from "../contracts/utils/RoleGuarded.sol";

contract InvoiceRegistryTest is BaseTest {
    function test_SubmitStoresPendingInvoice() public {
        uint256 id = _submit("INV-001");
        InvoiceRegistry.Invoice memory inv = registry.getInvoice(id);
        assertEq(id, 1);
        assertEq(inv.supplier, supplier);
        assertEq(inv.buyer, core);
        assertEq(inv.amount, FACE);
        assertEq(inv.fileHash, FILE_HASH);
        assertEq(uint8(inv.status), uint8(InvoiceRegistry.InvoiceStatus.Pending));
    }

    function test_RevertWhen_DuplicateInvoice() public {
        uint256 id = _submit("INV-001");
        vm.prank(supplier);
        vm.expectRevert(abi.encodeWithSelector(InvoiceRegistry.InvoiceAlreadyExists.selector, id));
        registry.submitInvoice("INV-001", core, FACE, dueDate, keccak256("another.pdf"));
    }

    function test_DuplicateBlockedEvenAfterConfirmation() public {
        uint256 id = _submitAndConfirm();
        vm.prank(supplier);
        vm.expectRevert(abi.encodeWithSelector(InvoiceRegistry.InvoiceAlreadyExists.selector, id));
        registry.submitInvoice("INV-001", core, FACE, dueDate, FILE_HASH);
    }

    function test_RevertWhen_InvalidInputs() public {
        vm.startPrank(supplier);
        vm.expectRevert(InvoiceRegistry.InvalidAmount.selector);
        registry.submitInvoice("INV-1", core, 0, dueDate, FILE_HASH);

        vm.expectRevert(abi.encodeWithSelector(InvoiceRegistry.InvalidDueDate.selector, uint64(block.timestamp)));
        registry.submitInvoice("INV-1", core, FACE, uint64(block.timestamp), FILE_HASH);

        vm.expectRevert(abi.encodeWithSelector(InvoiceRegistry.InvalidBuyer.selector, funder));
        registry.submitInvoice("INV-1", funder, FACE, dueDate, FILE_HASH);

        vm.expectRevert(InvoiceRegistry.InvalidFileHash.selector);
        registry.submitInvoice("INV-1", core, FACE, dueDate, bytes32(0));

        vm.expectRevert(InvoiceRegistry.InvalidInvoiceNo.selector);
        registry.submitInvoice("", core, FACE, dueDate, FILE_HASH);
        vm.stopPrank();
    }

    function test_RevertWhen_AmountExceedsUint96() public {
        uint256 tooBig = uint256(type(uint96).max) + 1;
        vm.prank(supplier);
        vm.expectRevert(abi.encodeWithSelector(SafeCast.SafeCastOverflowedUintDowncast.selector, 96, tooBig));
        registry.submitInvoice("INV-BIG", core, tooBig, dueDate, FILE_HASH);
    }

    function test_InvoiceNoOnlyInEvent() public {
        vm.expectEmit(true, true, true, true, address(registry));
        emit InvoiceRegistry.InvoiceSubmitted(1, supplier, core, "INV-001", FACE, dueDate, FILE_HASH);
        uint256 id = _submit("INV-001");
        assertEq(
            registry.getInvoice(id).dedupKey, registry.computeDedupKey("INV-001", supplier, core, FACE)
        );
    }

    function test_RevertWhen_NonSupplierSubmits() public {
        bytes32 supplierRole = roles.SUPPLIER();
        vm.prank(funder);
        vm.expectRevert(abi.encodeWithSelector(RoleGuarded.Unauthorized.selector, funder, supplierRole));
        registry.submitInvoice("INV-1", core, FACE, dueDate, FILE_HASH);
    }

    function test_ConfirmMintsEqualVoucher() public {
        uint256 id = _submitAndConfirm();
        assertEq(uint8(registry.getInvoice(id).status), uint8(InvoiceRegistry.InvoiceStatus.Confirmed));
        assertEq(token.balanceOf(supplier, id), FACE);

        ReceivableToken.Receivable memory r = token.getReceivable(id);
        assertEq(r.buyer, core);
        assertEq(r.originalSupplier, supplier);
        assertEq(r.faceValue, FACE);
        assertEq(r.dueDate, dueDate);
        assertEq(uint8(r.status), uint8(ReceivableToken.Status.Active));
    }

    function test_RevertWhen_WrongBuyerConfirms() public {
        bytes32 coreRole = roles.CORE_ENTERPRISE();
        address otherCore = makeAddr("otherCore");
        vm.prank(admin);
        roles.grantRole(coreRole, otherCore);

        uint256 id = _submit("INV-001");
        vm.prank(otherCore);
        vm.expectRevert(abi.encodeWithSelector(InvoiceRegistry.NotInvoiceBuyer.selector, id, otherCore));
        registry.confirmInvoice(id);
    }

    function test_RevertWhen_ConfirmTwice() public {
        uint256 id = _submitAndConfirm();
        vm.prank(core);
        vm.expectRevert(
            abi.encodeWithSelector(
                InvoiceRegistry.InvoiceNotPending.selector, id, InvoiceRegistry.InvoiceStatus.Confirmed
            )
        );
        registry.confirmInvoice(id);
    }

    function test_RevertWhen_ConfirmAfterDueDate() public {
        uint256 id = _submit("INV-001");
        vm.warp(dueDate);
        vm.prank(core);
        vm.expectRevert(abi.encodeWithSelector(InvoiceRegistry.InvalidDueDate.selector, dueDate));
        registry.confirmInvoice(id);
    }

    function test_RejectReleasesDedupKey() public {
        uint256 id = _submit("INV-001");
        vm.prank(core);
        registry.rejectInvoice(id, "wrong amount");
        assertEq(uint8(registry.getInvoice(id).status), uint8(InvoiceRegistry.InvoiceStatus.Rejected));
        assertEq(token.balanceOf(supplier, id), 0);

        uint256 id2 = _submit("INV-001");
        assertEq(id2, 2);
    }

    function test_RevertWhen_RejectWithoutReason() public {
        uint256 id = _submit("INV-001");
        vm.prank(core);
        vm.expectRevert(InvoiceRegistry.ReasonRequired.selector);
        registry.rejectInvoice(id, "");
    }

    function test_RevertWhen_MintCalledDirectly() public {
        vm.prank(supplier);
        vm.expectRevert(ReceivableToken.OnlyInvoiceRegistry.selector);
        token.mint(supplier, 99, core, FACE, dueDate);
    }
}
