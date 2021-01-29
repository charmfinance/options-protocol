from brownie import (
    accounts,
    OptionFactory,
    OptionMarket,
    OptionToken,
    ZERO_ADDRESS,
)


def main():
    deployer = accounts.load("deployer")
    balance = deployer.balance()

    optionMarket = deployer.deploy(OptionMarket, publish_source=True)
    optionToken = deployer.deploy(OptionToken, publish_source=True)

    # initialize with dummy data so can't be initialized again
    optionToken.initialize(ZERO_ADDRESS, "", "", 18, {"from": deployer})
    optionMarket.initialize(
        ZERO_ADDRESS,
        ZERO_ADDRESS,
        [ZERO_ADDRESS],
        [ZERO_ADDRESS],
        [1],
        2000000000,
        False,
        0,
        "",
        {"from": deployer},
    )

    factory = deployer.deploy(
        OptionFactory, optionMarket, optionToken, publish_source=True
    )

    print(f"Factory address: {factory.address}")
    print(f"Gas used in deployment: {(balance - deployer.balance()) / 1e18:.4f} ETH")
