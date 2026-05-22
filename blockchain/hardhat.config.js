require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config({ path: "../config/.env" });

module.exports = {
  solidity: "0.8.28",
  networks: {
    besu: {
      url: "http://127.0.0.1:8545",
      chainId: 1337,
      accounts: [process.env.BESU_PRIVATE_KEY],
      gas: 10000000,
      gasPrice: 0
    }
  }
};
