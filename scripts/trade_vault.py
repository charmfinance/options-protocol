from brownie import (
    accounts,
    network,
    Contract,
    OptionMarket,
    OptionVault,
)


VAULT = "0xa3A476403e576b6Fe6D0119009c3f7e86ccaf677"
MARKET = "0x6726003fc1fc17d85e20f727b3680b0454fd8b9e"
MARKET = "0xeb418f2dd85c16e541fe5e259988be32e8eb91f9"

VAULT = "0x55E4a8C56Adcd038B6115580C86c126cA63e60b6"
MARKET = "0xF3917c023958EcD8C82a19b1B5C757913780eFb3"

LP_SHARES = 0.1
LP_SHARES = 20

SHORT_ITM_MULT = 2.5
LONG_OTM_MULT = 0
MAX_AMOUNT_MULT = 10

EPS = 1e-9


def main():
    _network = network.show_active()
    print(f"Network: {_network}")

    deployer = accounts.load("deployer")
    balance = deployer.balance()

    vault = OptionVault.at(VAULT)
    market = OptionMarket.at(MARKET)

    decimals = vault.decimals()
    scale = 10 ** decimals

    n = market.numStrikes()
    longQuantities = [0] * n
    shortQuantities = [0] * n

    if market.isPut():
        strike1 = market.strikePrices(0) / 1e18
        strike2 = market.strikePrices(n - 1) / 1e18
        longQuantities[0] = int(LONG_OTM_MULT * LP_SHARES / strike1 * scale + EPS)
        shortQuantities[-1] = int(SHORT_ITM_MULT * LP_SHARES / strike2 * scale + EPS)
    else:
        longQuantities[-1] = int(LONG_OTM_MULT * LP_SHARES * scale * EPS)
        shortQuantities[0] = int(SHORT_ITM_MULT * LP_SHARES * scale * EPS)

    lpShares = int(LP_SHARES * scale + EPS)
    maxAmount = int(MAX_AMOUNT_MULT * LP_SHARES * scale + EPS)

    print(f"Long quantities:   {longQuantities}")
    print(f"Short quantities:  {shortQuantities}")
    print(f"LP shares:         {lpShares}")
    print(f"Max amount:        {maxAmount}")

    vault.buy(
        MARKET,
        longQuantities,
        shortQuantities,
        lpShares,
        maxAmount,
        {"from": deployer},
    )

    print(f"Gas used in deployment: {(balance - deployer.balance()) / 1e18:.4f} ETH")
