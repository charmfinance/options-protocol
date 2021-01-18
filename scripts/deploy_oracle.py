import arrow
from math import log

from brownie import (
    accounts,
    ChainlinkOracle,
)


# deployment parameters
ACCOUNT = "deployer"
PAIR = "BTC/USD"


# addresses can be found here: https://docs.chain.link/docs/ethereum-addresses
CHAINLINK_PAIRS = {
    "BTC/USD": (
        "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c",
        "0x0000000000000000000000000000000000000000",
    ),
    "ETH/USD": (
        "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",
        "0x0000000000000000000000000000000000000000",
    ),
    "RINKEBY_ETH/USD": (
        "0x8A753747A1Fa494EC906cE90E9f37563A8AF630e",
        "0x0000000000000000000000000000000000000000",
    ),
}


def main():
    deployer = accounts.load(ACCOUNT)
    balance = deployer.balance()

    price_feed1, price_feed2 = CHAINLINK_PAIRS[PAIR]
    oracle = deployer.deploy(
        ChainlinkOracle, price_feed1, price_feed2, publish_source=True
    )

    print(f"Current price: {oracle.getPrice() / 1e18:.4f}")
    print(f"Gas used in deployment: {(balance - deployer.balance()) / 1e18:.4f} ETH")
    print()
