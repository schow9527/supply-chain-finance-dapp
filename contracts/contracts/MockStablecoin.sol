// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/// @title MockStablecoin
/// @notice Test-only USD stablecoin (6 decimals) with a public faucet. Not for mainnet.
contract MockStablecoin is ERC20 {
    uint256 public constant FAUCET_AMOUNT = 100_000 * 1e6;

    constructor() ERC20("Mock USD", "mUSD") {}

    function decimals() public pure override returns (uint8) {
        return 6;
    }

    function faucet() external {
        _mint(msg.sender, FAUCET_AMOUNT);
    }
}
