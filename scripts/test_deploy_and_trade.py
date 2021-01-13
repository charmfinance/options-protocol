from brownie import (
    accounts,
    OptionMarket,
    OptionToken,
    MockToken,
)


# deployer = accounts.load("deployer")
deployer = accounts[0]

ZERO = "0x0000000000000000000000000000000000000000"

IS_ETH = True
ORACLE = "0xD014CDc41f9AF7A6456c920aD17fFf14F136640F"  # ETH/USDC rinkeby chainlink
STRIKE_PRICES = [(100 * x + 100) * 1e18 for x in range(4)]
EXPIRY_TIME = 2e9
IS_PUT = True
TRADING_FEE = 1e16
BALANCE_CAP = 1000e18
DISPUTE_PERIOD = 3600
B = 10e15
DECIMALS = 18

IS_LONG_TOKEN = True
STRIKE_INDEX = 0
OPTIONS_OUT = 1e15


def main():
    balance = deployer.balance()

    longTokens = [deployer.deploy(OptionToken) for _ in STRIKE_PRICES]
    shortTokens = [deployer.deploy(OptionToken) for _ in STRIKE_PRICES]
    market = deployer.deploy(OptionMarket)

    if IS_ETH:
        baseToken = ZERO if IS_ETH else deployer.deploy(MockToken)
    else:
        baseToken = deployer.deploy(MockToken)
        baseToken.mint(deployer, 100e18, {"from": deployer})
        baseToken.approve(market, 100e18, {"from": deployer})

    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", DECIMALS)

    market.initialize(
        baseToken,
        ORACLE,
        longTokens,
        shortTokens,
        STRIKE_PRICES,
        EXPIRY_TIME,
        IS_PUT,
        TRADING_FEE,
        BALANCE_CAP,
        DISPUTE_PERIOD,
        "symbol",
    )

    valueDict = {"value": 50e18} if IS_ETH else {}
    market.deposit(B, 50e18, {"from": deployer, **valueDict})

    print("Buy")
    market.buy(
        IS_LONG_TOKEN,
        STRIKE_INDEX,
        OPTIONS_OUT,
        1 << 255,
        {"from": deployer, **valueDict},
    )

    print("Sell")
    market.sell(IS_LONG_TOKEN, STRIKE_INDEX, OPTIONS_OUT, 0, {"from": deployer})

    print(f"ETH spent: {(balance - deployer.balance()) * 1e-18}")
