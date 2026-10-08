// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/// @title RoleManager
/// @notice Single source of truth for user roles and the global emergency pause.
///         Each address may hold at most one role. Admin = DEFAULT_ADMIN_ROLE.
contract RoleManager is AccessControl, Pausable {
    bytes32 public constant SUPPLIER = keccak256("SUPPLIER");
    bytes32 public constant CORE_ENTERPRISE = keccak256("CORE_ENTERPRISE");
    bytes32 public constant FUNDER = keccak256("FUNDER");
    bytes32 public constant AUDITOR = keccak256("AUDITOR");

    /// @dev Tracks whether an address already holds a role (DEFAULT_ADMIN_ROLE is bytes32(0),
    ///      so a separate flag is needed).
    mapping(address => bool) public isRegistered;
    mapping(address => bytes32) private _roleOf;

    error InvalidRole(bytes32 role);
    error AccountAlreadyHasRole(address account, bytes32 currentRole);
    error RenounceDisabled();

    constructor(address admin) {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
    }

    /// @notice Returns the role held by `account`. Check `isRegistered` first,
    ///         since an unregistered address also returns bytes32(0).
    function roleOf(address account) external view returns (bytes32) {
        return _roleOf[account];
    }

    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }

    /// @dev Disabled so the platform can never lose its last admin by accident.
    function renounceRole(bytes32, address) public pure override {
        revert RenounceDisabled();
    }

    function _grantRole(bytes32 role, address account) internal override returns (bool) {
        if (
            role != DEFAULT_ADMIN_ROLE && role != SUPPLIER && role != CORE_ENTERPRISE && role != FUNDER
                && role != AUDITOR
        ) revert InvalidRole(role);
        if (hasRole(role, account)) return false;
        if (isRegistered[account]) revert AccountAlreadyHasRole(account, _roleOf[account]);

        isRegistered[account] = true;
        _roleOf[account] = role;
        return super._grantRole(role, account);
    }

    function _revokeRole(bytes32 role, address account) internal override returns (bool) {
        bool revoked = super._revokeRole(role, account);
        if (revoked) {
            delete isRegistered[account];
            delete _roleOf[account];
        }
        return revoked;
    }
}
