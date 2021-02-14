import datetime
import json
import sys
import yaml

from brownie import (
    accounts,
    network,
    Contract,
    OptionMarket,
    OptionToken,
    ZERO_ADDRESS,
)


PATH = {
    "mainnet": "markets.yaml",
    "rinkeby": "markets-rinkeby.yaml",
}


def main():
    with open(PATH[network.show_active()], "r") as f:
        markets = yaml.safe_load(f)

    res = []
    for address in markets:
        market = OptionMarket.at(address)
        baseAddress = str(market.baseToken())
        if baseAddress == ZERO_ADDRESS:
            baseSymbol = "ETH"
        else:
            baseToken = Contract.from_explorer(baseAddress)
            baseSymbol = baseToken.symbol()

        n = market.numStrikes()
        longTokens = [OptionToken.at(market.longTokens(i)) for i in range(n)]
        shortTokens = [OptionToken.at(market.shortTokens(i)) for i in range(n)]

        assert market.symbol().startswith("Charm LP ") or market.symbol().startswith(
            "LP "
        )
        if market.symbol().startswith("Charm LP "):
            underlyingSymbol = market.symbol().split()[2]
        else:
            underlyingSymbol = market.symbol().split()[1]

        totalSupplyCap = 0
        try:
            totalSupplyCap = market.totalSupplyCap()
        except ValueError:
            pass

        res.append(
            {
                "address": address,
                "baseAddress": baseAddress,
                "baseSymbol": baseSymbol,
                "decimals": longTokens[0].decimals(),
                "underlyingSymbol": underlyingSymbol,
                "oracleAddress": market.oracle(),
                "expiryTime": market.expiryTime(),
                "balanceCap": market.balanceCap(),
                "totalSupplyCap": totalSupplyCap,
                "isPut": market.isPut(),
                "tradingFee": market.tradingFee(),
                "disputePeriod": market.disputePeriod(),
                "strikePrices": [market.strikePrices(i) for i in range(n)],
                "longAddresses": [token.address for token in longTokens],
                "longSymbols": [token.symbol() for token in longTokens],
                "shortAddresses": [token.address for token in shortTokens],
                "shortSymbols": [token.symbol() for token in shortTokens],
                "symbol": market.symbol(),
            }
        )

    print(json.dumps(res, indent=4, sort_keys=True))
