// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {RoleManager} from "../contracts/RoleManager.sol";
import {ReceivableToken} from "../contracts/ReceivableToken.sol";
import {InvoiceRegistry} from "../contracts/InvoiceRegistry.sol";
import {FinancingPool} from "../contracts/FinancingPool.sol";
import {MockStablecoin} from "../contracts/MockStablecoin.sol";

/// @notice Deploys and wires all contracts, then writes deployments/<chainId>.json.
///         The broadcasting account becomes the platform admin.
///
///         Optional env vars (comma-separated addresses) grant demo roles right away:
///         DEMO_SUPPLIERS, DEMO_CORES, DEMO_FUNDERS, DEMO_AUDITORS
contract Deploy is Script {
    function run() external {
        vm.startBroadcast();
        (, address admin,) = vm.readCallers();

        RoleManager roles = new RoleManager(admin);
        ReceivableToken token = new ReceivableToken(roles);
        MockStablecoin usd = new MockStablecoin();
        InvoiceRegistry registry = new InvoiceRegistry(roles, token);
        FinancingPool pool = new FinancingPool(roles, token, usd);
        token.setSystemContracts(address(registry), address(pool));

        _grantFromEnv(roles, "DEMO_SUPPLIERS", roles.SUPPLIER());
        _grantFromEnv(roles, "DEMO_CORES", roles.CORE_ENTERPRISE());
        _grantFromEnv(roles, "DEMO_FUNDERS", roles.FUNDER());
        _grantFromEnv(roles, "DEMO_AUDITORS", roles.AUDITOR());
        vm.stopBroadcast();

        string memory key = "deployment";
        vm.serializeUint(key, "chainId", block.chainid);
        vm.serializeUint(key, "startBlock", block.number);
        vm.serializeAddress(key, "admin", admin);
        vm.serializeAddress(key, "RoleManager", address(roles));
        vm.serializeAddress(key, "ReceivableToken", address(token));
        vm.serializeAddress(key, "MockStablecoin", address(usd));
        vm.serializeAddress(key, "InvoiceRegistry", address(registry));
        string memory json = vm.serializeAddress(key, "FinancingPool", address(pool));
        string memory path = string.concat(vm.projectRoot(), "/deployments/", vm.toString(block.chainid), ".json");
        vm.writeJson(json, path);

        console.log("RoleManager     ", address(roles));
        console.log("ReceivableToken ", address(token));
        console.log("MockStablecoin  ", address(usd));
        console.log("InvoiceRegistry ", address(registry));
        console.log("FinancingPool   ", address(pool));
        console.log("Written to", path);
    }

    function _grantFromEnv(RoleManager roles, string memory envKey, bytes32 role) private {
        address[] memory accounts = vm.envOr(envKey, ",", new address[](0));
        for (uint256 i; i < accounts.length; ++i) {
            roles.grantRole(role, accounts[i]);
        }
    }
}
