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
EXPIRY_DATE = "13 Nov 2020"
STRIKE_PRICES = [350]
LIQUIDITY_PARAM = 0.05


# constants
SCALE = 10 ** 18
EXPIRY_TIME = "16:00"
QUOTE_TOKEN = "USDC"


DEPLOYED_ORACLES = {
    "BTC/USDC": "0xe3F5abfC874b6B5A3416b0A01c3913eE11B8A02C",
    "ETH/USDC": "0x4DA31B35fc13298A473aDF620844033B9F9342AD",
    "KOVAN_ETH/USDC": "0xe3F5abfC874b6B5A3416b0A01c3913eE11B8A02C",
}

TOKEN_ADDRESSES = {
    "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
    "ETH": "0x0000000000000000000000000000000000000000",
    "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "KOVAN_ETH": "0x0000000000000000000000000000000000000000",
}

# kovan
FACTORY = "0x4Bf573458cE753D6626f2c4165E995D22193bc13"


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

    base_token = TOKEN_ADDRESSES[QUOTE_TOKEN if is_put else BASE_TOKEN]
    oracle = DEPLOYED_ORACLES[BASE_TOKEN + "/" + QUOTE_TOKEN]

    # brownie doesn't let us use OptionsFactory.at
    factory = Contract.from_explorer(FACTORY)
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
        # for is_put in [False, True]:
        for is_put in [False]:
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
