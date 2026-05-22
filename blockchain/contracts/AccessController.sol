// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title AccessController
 * @dev Role-based access control for the AI4MultiGIS data governance system.
 *      Manages three roles: ADMINISTRATOR, DATA_PROVIDER, ANALYST.
 */
contract AccessController {

    address public administrator;

    enum Role { NONE, ANALYST, DATA_PROVIDER, ADMINISTRATOR }

    mapping(address => Role) private _roles;

    event RoleGranted(address indexed account, Role role, address indexed grantedBy);
    event RoleRevoked(address indexed account, Role role, address indexed revokedBy);

    modifier onlyAdministrator() {
        require(_roles[msg.sender] == Role.ADMINISTRATOR,
            "AccessController: caller is not administrator");
        _;
    }

    constructor() {
        administrator = msg.sender;
        _roles[msg.sender] = Role.ADMINISTRATOR;
        emit RoleGranted(msg.sender, Role.ADMINISTRATOR, msg.sender);
    }

    function grantRole(address account, Role role) external onlyAdministrator {
        require(account != address(0), "AccessController: zero address");
        require(role != Role.NONE, "AccessController: cannot grant NONE role");
        _roles[account] = role;
        emit RoleGranted(account, role, msg.sender);
    }

    function revokeRole(address account) external onlyAdministrator {
        require(account != administrator, "AccessController: cannot revoke administrator");
        Role previous = _roles[account];
        _roles[account] = Role.NONE;
        emit RoleRevoked(account, previous, msg.sender);
    }

    function getRole(address account) external view returns (Role) {
        return _roles[account];
    }

    function hasRole(address account, Role role) external view returns (bool) {
        return _roles[account] == role;
    }

    function isDataProvider(address account) external view returns (bool) {
        return _roles[account] == Role.DATA_PROVIDER ||
               _roles[account] == Role.ADMINISTRATOR;
    }

    function isAnalyst(address account) external view returns (bool) {
        return _roles[account] >= Role.ANALYST;
    }
}
