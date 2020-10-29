import arrow
from math import log

from brownie import (
    accounts,
    ChainlinkOracle,
)


# deployment parameters
ACCOUNT = "charm"
PAIR = "BTC/USD"


CHAINLINK_PAIRS = {
    "KOVAN_ETH/USD": (
        "0x9326BFA02ADD2366b30bacB125260Af641031331",
        "0x0000000000000000000000000000000000000000",
    ),
    "BTC/USD": (
        "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c",
        "0x0000000000000000000000000000000000000000",
    ),
    "ETH/USD": (
        "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",
        "0x0000000000000000000000000000000000000000",
    ),
}


def main():
    deployer = accounts.load("charm")
    balance = deployer.balance()

    price_feed1, price_feed2 = CHAINLINK_PAIRS[PAIR]
    oracle = ChainlinkOracle.deploy(price_feed1, price_feed2, {"from": deployer})

    print(f"Current price: {oracle.getPrice() / 1e18:.4f}")
    print(f"Gas used in deployment: {(balance - deployer.balance()) / 1e18:.4f} ETH")
    print()
