from brownie import (
    accounts,
    OptionsFactory,
    OptionsMarketMaker,
    OptionsToken,
    SeedRewards,
)


def main():
    deployer = accounts.load("deployer")
    balance = deployer.balance()

    market = deployer.deploy(OptionsMarketMaker)
    optionsToken = deployer.deploy(OptionsToken)
    factory = deployer.deploy(OptionsFactory, market, optionsToken)

    print(f"Factory address: {factory.address}")
    print(f"Gas used in deployment: {(balance - deployer.balance()) / 1e18:.4f} ETH")
