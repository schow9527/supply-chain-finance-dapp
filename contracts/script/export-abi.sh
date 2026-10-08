#!/usr/bin/env bash
# Builds the contracts and writes plain ABI JSON files to abi/ for the backend (web3.py)
# and frontend (ethers.js).
set -euo pipefail
cd "$(dirname "$0")/.."

forge build --silent
mkdir -p abi
for name in RoleManager ReceivableToken InvoiceRegistry FinancingPool MockStablecoin; do
  forge inspect "$name" abi --json > "abi/$name.json"
  echo "abi/$name.json"
done

# Single flattened file for deploying from Remix
cat > contracts/AllContracts.sol <<'SOL'
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {RoleManager} from "./RoleManager.sol";
import {ReceivableToken} from "./ReceivableToken.sol";
import {MockStablecoin} from "./MockStablecoin.sol";
import {InvoiceRegistry} from "./InvoiceRegistry.sol";
import {FinancingPool} from "./FinancingPool.sol";
SOL
mkdir -p remix
forge flatten contracts/AllContracts.sol -o remix/SupplyChainFinance.sol > /dev/null
rm contracts/AllContracts.sol
echo "remix/SupplyChainFinance.sol"
