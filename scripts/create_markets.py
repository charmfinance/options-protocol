import arrow
from math import log

from brownie import (
    accounts,
    Contract,
    OptionsFactory,
    OptionsMarketMaker,
    OptionsToken,
    SeedRewards,
)


# deployment parameters
ACCOUNT = "deployer"
BASE_TOKEN = "ETH"
EXPIRY_DATE = "20 Nov 2020"
STRIKE_PRICES = [450]
LIQUIDITY_PARAM = 0.05
NETWORK = "rinkeby"


# constants
SCALE = 10 ** 18
EXPIRY_TIME = "16:00"
QUOTE_TOKEN = "USDC"


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
    "rinkeby": "0x869C636deeA101f11a0A37e1f179329C1a2bAFCa",
}


def create_market(deployer, strike_price, is_put):
    strike_wei = int(SCALE * strike_price)
    alpha_wei = int(SCALE * LIQUIDITY_PARAM // 2 / log(2))

    expiry = arrow.get(EXPIRY_DATE + " " + EXPIRY_TIME, "DD MMM YYYY HH:mm")
    if expiry < arrow.now():
        raise ValueError("Already expired")

    humanized = expiry.humanize(arrow.utcnow())
    print(f"Expiry: {expiry.isoformat()} ({humanized})")

    expiry_code = expiry.format("DDMMMYYYY").upper()
    if is_put:
        long_symbol = f"{BASE_TOKEN} {expiry_code} {strike_price} P"
        short_symbol = f"{BASE_TOKEN} {expiry_code} {strike_price} SP"
    else:
        long_symbol = f"{BASE_TOKEN} {expiry_code} {strike_price} C"
        short_symbol = f"{BASE_TOKEN} {expiry_code} {strike_price} CV"

    base_token = TOKEN_ADDRESSES[NETWORK][QUOTE_TOKEN if is_put else BASE_TOKEN]
    oracle = DEPLOYED_ORACLES[NETWORK][BASE_TOKEN + "/" + QUOTE_TOKEN]

    # brownie doesn't let us use OptionsFactory.at
    factory = Contract.from_explorer(FACTORY[NETWORK])
    factory.createMarket(
        base_token,
        oracle,
        is_put,
        strike_wei,
        alpha_wei,
        expiry.timestamp,
        long_symbol,
        long_symbol,
        short_symbol,
        short_symbol,
        {"from": deployer},
    )

    # brownie doesn't let us see the transaction return value
    address = factory.markets(factory.numMarkets() - 1)
    print(f"Deployed at: {address}")
    return OptionsMarketMaker.at(address)


def main():
    deployer = accounts.load(ACCOUNT)
    balance = deployer.balance()

    markets = []
    for strike_price in STRIKE_PRICES:
        for is_put in [False, True]:
            market = create_market(deployer, strike_price, is_put)
            markets.append(market)
            # deploy_seed_rewards(deployer, market)

    print(f"Gas used in deployment: {(balance - deployer.balance()) / 1e18:.4f} ETH")
    print()

    for market in markets:
        for address in [market.longToken(), market.shortToken()]:
            option = OptionsToken.at(address)
            symbol = option.symbol()
            print(f"{symbol}:\t{address}")
