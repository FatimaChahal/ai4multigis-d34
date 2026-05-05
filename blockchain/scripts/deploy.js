const hre = require("hardhat");

async function main() {
  console.log("Deploying GISIndexRegistry...");

  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying with account:", deployer.address);
  console.log("Account balance:",
    (await hre.ethers.provider.getBalance(deployer.address)).toString());

  const GISIndexRegistry = await hre.ethers.getContractFactory("GISIndexRegistry");
  const registry = await GISIndexRegistry.deploy();
  await registry.waitForDeployment();

  const address = await registry.getAddress();
  console.log("GISIndexRegistry deployed to:", address);

  const fs = require("fs");
  const config = {
    contractAddress: address,
    deployerAddress: deployer.address,
    network: hre.network.name,
    deployedAt: new Date().toISOString()
  };
  fs.writeFileSync(
    "../config/contract_config.json",
    JSON.stringify(config, null, 2)
  );
  console.log("Contract config saved to config/contract_config.json");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
