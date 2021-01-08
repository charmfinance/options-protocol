from brownie import (
    accounts,
    Contract,
    OptionMarket,
)


# TODO: have dict of b and max amount depending on base token

CONTRACT = "0x66Dcc47Ef1D016400a12eF638D8C1D8807Aca24f"

# calls
B = 1.06
MAX_AMOUNT = 4
LONG_OPTIONS = [
    0,
    0,
    0,
    0,
    0,
    0,
]
SHORT_OPTIONS = [
    2.6390573,
    0,
    0,
    0,
    0,
    0,
]

# puts
# MAX_AMOUNT = 10000
# LONG_OPTIONS = [
#     0,
#     0,
#     0,
#     0,
#     0,
#     0,
# ]
# SHORT_OPTIONS = [
#     0,
#     0,
#     0,
#     0,
#     0,
#     2.6390573,
# ]


# constants
ACCOUNT = "deployer"
ZERO = "0x0000000000000000000000000000000000000000"
EPS = 1e-9


def increase_b_and_buy(deployer):
    market = OptionMarket.at(CONTRACT)
    baseToken = market.baseToken()

    if baseToken == ZERO:
        symbol = "ETH"
        decimals = 18
        scale = 10 ** decimals
        getBalance = lambda: deployer.balance() / scale
    else:
        baseTokenContract = Contract.from_explorer(baseToken)
        symbol = baseTokenContract.symbol()
        decimals = baseTokenContract.decimals()
        scale = 10 ** decimals
        baseTokenContract.approve(market, 1 << 255, {"from": deployer})
        getBalance = lambda: baseToken.balanceOf(deployer) / scale

    maxAmount = int(MAX_AMOUNT * scale + EPS)
    valueDict = {"value": maxAmount} if baseToken == ZERO else {}

    print("Pausing")
    market.pause({"from": deployer})

    print(f"Increasing b to {B}")
    balance = getBalance()
    tx = market.increaseB(
        B * scale,
        {"from": deployer, **valueDict},
    )
    cost = balance - getBalance()
    print(f"{symbol} cost: {cost:.4f}")

    for isLong in [False, True]:
        for i, x in enumerate(LONG_OPTIONS if isLong else SHORT_OPTIONS):
            if x > EPS:
                print(f"Buying")
                balance = getBalance()
                tx = market.buy(
                    isLong,
                    i,
                    int(x * scale + EPS),
                    maxAmount,
                    {"from": deployer, **valueDict},
                )
                cost = balance - getBalance()
                print(f"{symbol} cost: {cost:.4f}")

    print("Unpausing")
    market.unpause({"from": deployer})

    print("Done")


def main():
    deployer = accounts.load(ACCOUNT)
    balance = deployer.balance()

    increase_b_and_buy(deployer)

    print(f"ETH cost: {(balance - deployer.balance()) / 1e18:.4f}")
