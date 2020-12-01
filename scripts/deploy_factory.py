from brownie import (
    accounts,
    OptionFactory,
    OptionMarket,
    OptionToken,
)


def main():
    deployer = accounts.load("deployer")
    balance = deployer.balance()

    optionMarket = deployer.deploy(OptionMarket)
    optionToken = deployer.deploy(OptionToken)
    factory = deployer.deploy(OptionFactory, optionMarket, optionToken)

    print(f"Factory address: {factory.address}")
    print(f"Gas used in deployment: {(balance - deployer.balance()) / 1e18:.4f} ETH")
