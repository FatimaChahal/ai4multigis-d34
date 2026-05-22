const hre = require("hardhat");

async function main() {
  console.log("Deploying GISIndexRegistry to Besu QBFT...");

  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying with account:", deployer.address);
  console.log("Account balance:",
    (await hre.ethers.provider.getBalance(deployer.address)).toString());

  const GISIndexRegistry = await hre.ethers.getContractFactory("GISIndexRegistry");
  const registry = await GISIndexRegistry.deploy({ gasPrice: 0 });
  await registry.waitForDeployment();

  const address = await registry.getAddress();
  const deployTx = registry.deploymentTransaction();
  console.log("GISIndexRegistry deployed to:", address);
  console.log("Transaction hash:", deployTx.hash);
  console.log("Block number:", deployTx.blockNumber);

  const fs = require("fs");
  const config = {
    contractAddress: address,
    deployerAddress: deployer.address,
    transactionHash: deployTx.hash,
    blockNumber: deployTx.blockNumber,
    network: hre.network.name,
    chainId: 1337,
    deployedAt: new Date().toISOString()
  };

  const configDir = "../config";
  if (!fs.existsSync(configDir)) fs.mkdirSync(configDir, { recursive: true });
  fs.writeFileSync(configDir + "/contract_config.json", JSON.stringify(config, null, 2));
  console.log("Contract config saved to config/contract_config.json");
  console.log(JSON.stringify(config, null, 2));
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
