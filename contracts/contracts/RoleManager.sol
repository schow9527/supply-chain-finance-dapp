// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title RoleManager
 * @dev Manages 5 roles (Admin, Supplier, CoreEnterprise, Financier, Auditor) and emergency pause.
 * Specification according to PRD section 5 & 6.
 */
contract RoleManager {
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    bytes32 public constant SUPPLIER_ROLE = keccak256("SUPPLIER_ROLE");
    bytes32 public constant CORE_ENTERPRISE_ROLE = keccak256("CORE_ENTERPRISE_ROLE");
    bytes32 public constant FINANCIER_ROLE = keccak256("FINANCIER_ROLE");
    bytes32 public constant AUDITOR_ROLE = keccak256("AUDITOR_ROLE");

    mapping(bytes32 => mapping(address => bool)) private _roles;
    mapping(address => bytes32) private _primaryRole;
    bool private _paused;

    event RoleGranted(bytes32 indexed role, address indexed account, address indexed operator);
    event RoleRevoked(bytes32 indexed role, address indexed account, address indexed operator);
    event Paused(address indexed account);
    event Unpaused(address indexed account);

    modifier onlyAdmin() {
        require(hasRole(ADMIN_ROLE, msg.sender), "RoleManager: Caller is not an admin");
        _;
    }

    modifier whenNotPaused() {
        require(!_paused, "RoleManager: System is paused");
        _;
    }

    constructor() {
        _grantRole(ADMIN_ROLE, msg.sender);
    }

    function hasRole(bytes32 role, address account) public view returns (bool) {
        return _roles[role][account];
    }

    function getPrimaryRole(address account) external view returns (bytes32) {
        return _primaryRole[account];
    }

    function isPaused() external view returns (bool) {
        return _paused;
    }

    function grantRole(bytes32 role, address account) external onlyAdmin whenNotPaused {
        require(account != address(0), "RoleManager: Invalid address");
        require(!_roles[role][account], "RoleManager: Account already has role");
        _grantRole(role, account);
    }

    function revokeRole(bytes32 role, address account) external onlyAdmin whenNotPaused {
        require(_roles[role][account], "RoleManager: Account does not have role");
        _roles[role][account] = false;
        if (_primaryRole[account] == role) {
            _primaryRole[account] = bytes32(0);
        }
        emit RoleRevoked(role, account, msg.sender);
    }

    function pause() external onlyAdmin {
        require(!_paused, "RoleManager: Already paused");
        _paused = true;
        emit Paused(msg.sender);
    }

    function unpause() external onlyAdmin {
        require(_paused, "RoleManager: Not paused");
        _paused = false;
        emit Unpaused(msg.sender);
    }

    function _grantRole(bytes32 role, address account) internal {
        _roles[role][account] = true;
        _primaryRole[account] = role;
        emit RoleGranted(role, account, msg.sender);
    }
}
