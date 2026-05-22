require("dotenv").config({ path: "../../config/.env" });
const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const { ethers, network } = hre;
  const provider = ethers.provider;
  const wallet = new ethers.Wallet(process.env.BESU_PRIVATE_KEY, provider);

  console.log("Deploying contracts to Besu QBFT...");
  console.log("Deployer:", wallet.address);
  console.log("Balance :", (await provider.getBalance(wallet.address)).toString());

  const txOpts = { gasPrice: 0 };

  console.log("\n[1/2] Deploying AccessController...");
  const AC = await ethers.getContractFactory("AccessController", wallet);
  const ac = await AC.deploy(txOpts);
  await ac.waitForDeployment();
  const acAddress = await ac.getAddress();
  console.log("  Address :", acAddress);

  console.log("\n[2/2] Deploying ProvenanceLogger...");
  const PL = await ethers.getContractFactory("ProvenanceLogger", wallet);
  const pl = await PL.deploy(txOpts);
  await pl.waitForDeployment();
  const plAddress = await pl.getAddress();
  console.log("  Address :", plAddress);

  const configPath = path.join(__dirname, "../../config/contract_config.json");
  const config = JSON.parse(fs.readFileSync(configPath));
  config.accessControllerAddress = acAddress;
  config.provenanceLoggerAddress  = plAddress;
  config.updatedAt = new Date().toISOString();
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));

  console.log("\n=== All contracts deployed ===");
  console.log("GISIndexRegistry  :", config.contractAddress);
  console.log("AccessController  :", acAddress);
  console.log("ProvenanceLogger  :", plAddress);
}

main().then(() => process.exit(0)).catch(e => { console.error(e); process.exit(1); });
