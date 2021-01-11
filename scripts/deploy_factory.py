from brownie import (
    accounts,
    OptionFactory,
    OptionMarket,
    OptionToken,
)


def main():
    deployer = accounts.load("deployer")
    balance = deployer.balance()

    optionMarket = deployer.deploy(OptionMarket, publish_source=True)
    optionToken = deployer.deploy(OptionToken, publish_source=True)
    factory = deployer.deploy(
        OptionFactory, optionMarket, optionToken, publish_source=True
    )

    print(f"Factory address: {factory.address}")
    print(f"Gas used in deployment: {(balance - deployer.balance()) / 1e18:.4f} ETH")
