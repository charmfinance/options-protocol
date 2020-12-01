import arrow
from math import log
import time

from brownie import (
    accounts,
    Contract,
    OptionFactory,
    OptionMarket,
    OptionToken,
)


# deployment parameters
ACCOUNT = "deployer"
BASE_TOKEN = "ETH"
EXPIRY_DATE = "11 Dec 2020"
STRIKE_PRICES = [400, 500, 600]
LIQUIDITY_PARAM = 0.20
NETWORK = "rinkeby"


# constants
SCALE = 10 ** 18
EXPIRY_TIME = "16:00"
QUOTE_TOKEN = "USDC"
TRADING_FEE = 0.01
BALANCE_CAP = 100
SUPPLY_CAP = 10000


DEPLOYED_ORACLES = {
    "mainnet": {
        "BTC/USDC": "0xe3F5abfC874b6B5A3416b0A01c3913eE11B8A02C",
        "ETH/USDC": "0x4DA31B35fc13298A473aDF620844033B9F9342AD",
    },
    "rinkeby": {
        "ETH/USDC": "0xD014CDc41f9AF7A6456c920aD17fFf14F136640F",
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
    },
}

FACTORY = {
    "mainnet": "",
    # "rinkeby": "0xA8d6D6623fc492eA9acbE39EE929E7205fE66687",  # v1. remove
    "rinkeby": "0x7d8d7Db940B39ef2B13ea53cF1081f62412e4df2",
}


def create_market(deployer, is_put):
    n = len(STRIKE_PRICES)
    alpha_wei = int(SCALE * LIQUIDITY_PARAM / log(n) / n)
    strike_prices_wei = [int(SCALE * px + 1e-9) for px in STRIKE_PRICES]

    expiry = arrow.get(EXPIRY_DATE + " " + EXPIRY_TIME, "DD MMM YYYY HH:mm")
    if expiry < arrow.now():
        raise ValueError("Already expired")

    humanized = expiry.humanize(arrow.utcnow())
    print(f"Expiry: {expiry.isoformat()} ({humanized})")

    oracle = DEPLOYED_ORACLES[NETWORK][BASE_TOKEN + "/" + QUOTE_TOKEN]

    # brownie doesn't let us use OptionFactory.at
    factory = Contract.from_explorer(FACTORY[NETWORK])
    factory.createMarket(
        TOKEN_ADDRESSES[NETWORK][BASE_TOKEN],
        TOKEN_ADDRESSES[NETWORK][QUOTE_TOKEN],
        oracle,
        strike_prices_wei,
        expiry.timestamp,
        alpha_wei,
        is_put,
        int(TRADING_FEE * SCALE + 1e-9),
        BALANCE_CAP * SCALE,
        SUPPLY_CAP * SCALE,
        {"from": deployer},
    )

    # brownie doesn't let us see the transaction return value
    time.sleep(1)
    address = factory.markets(factory.numMarkets() - 1)
    print(f"Deployed at: {address}")
    return OptionMarket.at(address)


def main():
    deployer = accounts.load(ACCOUNT)
    balance = deployer.balance()

    markets = []
    for is_put in [False, True]:
        market = create_market(deployer, is_put)
        markets.append(market)

    print(f"Gas used in deployment: {(balance - deployer.balance()) / 1e18:.4f} ETH")
    # print()

    # for i in range(len(STRIKE_PRICES)):
    #     for market in markets:
    #         for address in [market.longTokens(i), market.shortTokens(i)]:
    #             option = OptionToken.at(address)
    #             symbol = option.symbol()
    #             print(f"{symbol}:\t{address}")
