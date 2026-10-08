// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {RoleManager} from "../RoleManager.sol";

/// @notice Shared role / pause checks for business contracts, backed by RoleManager.
abstract contract RoleGuarded {
    RoleManager public immutable roleManager;

    error Unauthorized(address account, bytes32 requiredRole);
    error SystemPaused();

    constructor(RoleManager roleManager_) {
        roleManager = roleManager_;
    }

    modifier onlyRoleOf(bytes32 role) {
        _checkRole(role, msg.sender);
        _;
    }

    modifier whenActive() {
        _checkNotPaused();
        _;
    }

    function _checkRole(bytes32 role, address account) internal view {
        if (!roleManager.hasRole(role, account)) revert Unauthorized(account, role);
    }

    function _checkNotPaused() internal view {
        if (roleManager.paused()) revert SystemPaused();
    }
}
