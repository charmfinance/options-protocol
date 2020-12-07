import datetime
import json
import sys

from brownie import (
    accounts,
    Contract,
    OptionMarket,
    OptionToken,
)


TOKEN_SYMBOLS = {
    "0x0000000000000000000000000000000000000000": "ETH",
    "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48": "USDC",
    "0xE7d541c18D6aDb863F4C570065c57b75a53a64d3": "USDC",  # rinkeby
    "0xfFf8641a3E2AA350624db17BDb0eb3998E314926": "WBTC",  # rinkeby
}


def main():
    with open("markets.json", "r") as f:
        markets = json.load(f)

    res = []
    for address in markets:
        market = OptionMarket.at(address)
        baseAddress = str(market.baseToken())
        baseSymbol = TOKEN_SYMBOLS.get(baseAddress, "")

        n = market.numStrikes()
        longTokens = [OptionToken.at(market.longTokens(i)) for i in range(n)]
        shortTokens = [OptionToken.at(market.shortTokens(i)) for i in range(n)]

        res.append(
            {
                "address": address,
                "baseAddress": baseAddress,
                "baseSymbol": baseSymbol,
                "decimals": longTokens[0].decimals(),
                "underlyingSymbol": longTokens[0].symbol().split()[0],
                "oracleAddress": market.oracle(),
                "expiryTime": market.expiryTime(),
                "alpha": market.alpha(),
                "isPut": market.isPut(),
                "tradingFee": market.tradingFee(),
                "balanceCap": market.balanceCap(),
                "totalSupplyCap": market.totalSupplyCap(),
                "strikePrices": [market.strikePrices(i) for i in range(n)],
                "longAddresses": [token.address for token in longTokens],
                "longSymbols": [token.symbol() for token in longTokens],
                "shortAddresses": [token.address for token in shortTokens],
                "shortSymbols": [token.symbol() for token in shortTokens],
            }
        )

    print(json.dumps(res, indent=4, sort_keys=True))
