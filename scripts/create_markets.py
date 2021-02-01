import arrow
from math import log
import time

from brownie import (
    accounts,
    network,
    Contract,
    OptionFactory,
    OptionMarket,
    OptionToken,
)


# deployment parameters
ACCOUNT = "deployer"
BASE_TOKEN = "ETH"
# BASE_TOKEN = "WBTC"
EXPIRY_DATE = "05 Feb 2021"
STRIKE_PRICES = [800, 960, 1120, 1280, 1440, 1600, 1920, 2240]


# constants
SCALE = 10 ** 18
SCALE6 = 10 ** 6

EXPIRY_TIME = "16:00"
QUOTE_TOKEN = "USDC"
TRADING_FEE = 0.01
DISPUTE_PERIOD = 3600  # 1 hour
TVL_CAPS = {
    "ETH": 150 * SCALE,
    "USDC": 150_000 * SCALE6,
}
LP_CAPS = {
    "ETH": 50 * SCALE,
    "USDC": 50_000 * SCALE6,
}


DEPLOYED_ORACLES = {
    "mainnet": {
        "ETH/USDC": "0x3D52e452a284969b4110C04506cF22C18d7e7fF3",
        "WBTC/USDC": "0xB2a98Bd623038930d5d158EA6b20890ef4965A5a",
    },
    "rinkeby": {
        "ETH/USDC": "0xD014CDc41f9AF7A6456c920aD17fFf14F136640F",
        "WBTC/USDC": "0x8C74d6a122e6951C769914b0c52879000B1129a8",
    },
}

TOKEN_ADDRESSES = {
    "mainnet": {
        "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "ETH": "0x0000000000000000000000000000000000000000",
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    },
    "rinkeby": {
        "ETH": "0x0000000000000000000000000000000000000000",
        "USDC": "0xE7d541c18D6aDb863F4C570065c57b75a53a64d3",
        "WBTC": "0xfFf8641a3E2AA350624db17BDb0eb3998E314926",
    },
}

FACTORY = {
    "mainnet": "0xCDFE169dF3D64E2e43D88794A21048A52C742F2B",
    "rinkeby": "",
}


def create_market(deployer, is_put):
    _network = network.show_active()
    print(f"Network: {_network}")

    n = len(STRIKE_PRICES) + 1
    strike_prices_wei = [int(SCALE * px + 1e-9) for px in STRIKE_PRICES]

    expiry = arrow.get(EXPIRY_DATE + " " + EXPIRY_TIME, "DD MMM YYYY HH:mm")
    if expiry < arrow.now():
        raise ValueError("Already expired")

    humanized = expiry.humanize(arrow.utcnow())
    print(f"Expiry: {expiry.isoformat()} ({humanized})")

    oracle = DEPLOYED_ORACLES[_network][BASE_TOKEN + "/" + QUOTE_TOKEN]

    # brownie doesn't let us use OptionFactory.at
    factory = OptionFactory.at(FACTORY[_network])
    tx = factory.createMarket(
        TOKEN_ADDRESSES[_network][BASE_TOKEN],
        TOKEN_ADDRESSES[_network][QUOTE_TOKEN],
        oracle,
        strike_prices_wei,
        expiry.timestamp,
        is_put,
        int(TRADING_FEE * SCALE + 1e-9),
        {"from": deployer},
    )

    # can't get transaction return value from infura
    time.sleep(30)
    address = factory.markets(factory.numMarkets() - 1)

    market = OptionMarket.at(address)
    market.pause({"from": deployer})
    market.setBalanceCap(
        TVL_CAPS[QUOTE_TOKEN if is_put else BASE_TOKEN], {"from": deployer}
    )
    market.setTotalSupplyCap(
        LP_CAPS[QUOTE_TOKEN if is_put else BASE_TOKEN], {"from": deployer}
    )
    market.setDisputePeriod(DISPUTE_PERIOD, {"from": deployer})
    return market


def main():
    deployer = accounts.load(ACCOUNT)
    balance = deployer.balance()

    markets = []
    for is_put in [False, True]:
        market = create_market(deployer, is_put)
        markets.append(market)

    for market in markets:
        print(f"Deployed at: {market.address}")

    print(f"Gas used in deployment: {(balance - deployer.balance()) / 1e18:.4f} ETH")
