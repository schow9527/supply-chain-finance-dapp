// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Role identifiers shared by RoleManager and the business contracts. Using compile-time
///         constants avoids an external call to RoleManager just to read a role id.
library Roles {
    bytes32 internal constant ADMIN = 0x00; // == AccessControl.DEFAULT_ADMIN_ROLE
    bytes32 internal constant SUPPLIER = keccak256("SUPPLIER");
    bytes32 internal constant CORE_ENTERPRISE = keccak256("CORE_ENTERPRISE");
    bytes32 internal constant FUNDER = keccak256("FUNDER");
    bytes32 internal constant AUDITOR = keccak256("AUDITOR");
}
