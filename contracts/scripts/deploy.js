const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying contracts with account:", deployer.address);

  // 1. Deploy RoleManager
  const RoleManager = await hre.ethers.getContractFactory("RoleManager");
  const roleManager = await RoleManager.deploy();
  await roleManager.waitForDeployment();
  const roleManagerAddress = await roleManager.getAddress();
  console.log("RoleManager deployed to:", roleManagerAddress);

  // 2. Deploy ReceivableToken
  const ReceivableToken = await hre.ethers.getContractFactory("ReceivableToken");
  const receivableToken = await ReceivableToken.deploy(roleManagerAddress);
  await receivableToken.waitForDeployment();
  const receivableTokenAddress = await receivableToken.getAddress();
  console.log("ReceivableToken deployed to:", receivableTokenAddress);

  // 3. Deploy MockStablecoin
  const MockStablecoin = await hre.ethers.getContractFactory("MockStablecoin");
  const stablecoin = await MockStablecoin.deploy();
  await stablecoin.waitForDeployment();
  const stablecoinAddress = await stablecoin.getAddress();
  console.log("MockStablecoin deployed to:", stablecoinAddress);

  // 4. Deploy InvoiceRegistry
  const InvoiceRegistry = await hre.ethers.getContractFactory("InvoiceRegistry");
  const invoiceRegistry = await InvoiceRegistry.deploy(roleManagerAddress, receivableTokenAddress);
  await invoiceRegistry.waitForDeployment();
  const invoiceRegistryAddress = await invoiceRegistry.getAddress();
  console.log("InvoiceRegistry deployed to:", invoiceRegistryAddress);

  // 5. Deploy FinancingPool
  const FinancingPool = await hre.ethers.getContractFactory("FinancingPool");
  const financingPool = await FinancingPool.deploy(
    roleManagerAddress,
    receivableTokenAddress,
    invoiceRegistryAddress,
    stablecoinAddress
  );
  await financingPool.waitForDeployment();
  const financingPoolAddress = await financingPool.getAddress();
  console.log("FinancingPool deployed to:", financingPoolAddress);

  // 6. Set cross-contract permissions in ReceivableToken
  console.log("Configuring cross-contract permissions...");
  let tx = await receivableToken.setInvoiceRegistry(invoiceRegistryAddress);
  await tx.wait();
  tx = await receivableToken.setFinancingPool(financingPoolAddress);
  await tx.wait();
  console.log("Cross-contract setup completed!");

  // 7. Save deployed addresses to deployed_addresses.json
  const deploymentInfo = {
    network: hre.network.name,
    chainId: hre.network.config.chainId,
    deployer: deployer.address,
    timestamp: new Date().toISOString(),
    contracts: {
      RoleManager: roleManagerAddress,
      ReceivableToken: receivableTokenAddress,
      MockStablecoin: stablecoinAddress,
      InvoiceRegistry: invoiceRegistryAddress,
      FinancingPool: financingPoolAddress,
    },
  };

  const outputPath = path.join(__dirname, "../static/js/deployed_addresses.json");
  fs.writeFileSync(outputPath, JSON.stringify(deploymentInfo, null, 2));
  console.log("Deployment info written to:", outputPath);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
