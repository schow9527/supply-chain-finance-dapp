// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IAccessControl} from "@openzeppelin/contracts/access/IAccessControl.sol";
import {BaseTest} from "./Base.t.sol";
import {RoleManager} from "../contracts/RoleManager.sol";
import {RoleGuarded} from "../contracts/utils/RoleGuarded.sol";

contract RoleManagerTest is BaseTest {
    function test_GrantSetsRoleAndRegistration() public view {
        assertTrue(roles.hasRole(roles.SUPPLIER(), supplier));
        assertTrue(roles.isRegistered(supplier));
        assertEq(roles.roleOf(supplier), roles.SUPPLIER());
        assertFalse(roles.isRegistered(stranger));
    }

    function test_RevertWhen_GrantingSecondRole() public {
        bytes32 funderRole = roles.FUNDER();
        bytes32 supplierRole = roles.SUPPLIER();
        vm.prank(admin);
        vm.expectRevert(abi.encodeWithSelector(RoleManager.AccountAlreadyHasRole.selector, supplier, supplierRole));
        roles.grantRole(funderRole, supplier);
    }

    function test_RevertWhen_GrantingUnknownRole() public {
        bytes32 bogus = keccak256("BOGUS");
        vm.prank(admin);
        vm.expectRevert(abi.encodeWithSelector(RoleManager.InvalidRole.selector, bogus));
        roles.grantRole(bogus, stranger);
    }

    function test_RevertWhen_NonAdminGrants() public {
        bytes32 supplierRole = roles.SUPPLIER();
        bytes32 adminRole = roles.DEFAULT_ADMIN_ROLE();
        vm.prank(stranger);
        vm.expectRevert(
            abi.encodeWithSelector(IAccessControl.AccessControlUnauthorizedAccount.selector, stranger, adminRole)
        );
        roles.grantRole(supplierRole, stranger);
    }

    function test_RevokeClearsRoleAndBlocksWrites() public {
        bytes32 supplierRole = roles.SUPPLIER();
        vm.prank(admin);
        roles.revokeRole(supplierRole, supplier);
        assertFalse(roles.isRegistered(supplier));

        vm.prank(supplier);
        vm.expectRevert(abi.encodeWithSelector(RoleGuarded.Unauthorized.selector, supplier, supplierRole));
        registry.submitInvoice("INV-X", core, FACE, dueDate, FILE_HASH);
    }

    function test_RevokedAccountCanTakeNewRole() public {
        bytes32 supplierRole = roles.SUPPLIER();
        bytes32 funderRole = roles.FUNDER();
        vm.startPrank(admin);
        roles.revokeRole(supplierRole, supplier);
        roles.grantRole(funderRole, supplier);
        vm.stopPrank();
        assertEq(roles.roleOf(supplier), funderRole);
    }

    function test_RevertWhen_Renouncing() public {
        bytes32 adminRole = roles.DEFAULT_ADMIN_ROLE();
        vm.prank(admin);
        vm.expectRevert(RoleManager.RenounceDisabled.selector);
        roles.renounceRole(adminRole, admin);
    }

    function test_PauseBlocksWritesButNotReads() public {
        uint256 id = _submit("INV-001");
        vm.prank(admin);
        roles.pause();

        vm.prank(core);
        vm.expectRevert(RoleGuarded.SystemPaused.selector);
        registry.confirmInvoice(id);

        assertEq(registry.getInvoice(id).amount, FACE); // reads still work

        vm.prank(admin);
        roles.unpause();
        vm.prank(core);
        registry.confirmInvoice(id);
    }

    function test_RevertWhen_NonAdminPauses() public {
        vm.prank(stranger);
        vm.expectRevert();
        roles.pause();
    }
}
