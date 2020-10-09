import datetime
import json

from brownie import (
    accounts,
    Contract,
    OptionsMarketMaker,
    OptionsToken,
)


TOKEN_SYMBOLS = {
    "0x0000000000000000000000000000000000000000": "ETH",
    "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48": "USDC",
    "0xED6bfBd086ad6AdaB4A709071f9ae3863796F74A": "MOCK",  # ropsten
}


def main():
    options = []
    for market in OptionsMarketMaker:
        baseAddress = str(market.baseToken())
        baseSymbol = TOKEN_SYMBOLS.get(baseAddress, "?")

        addresses = [market.longToken(), market.shortToken()]
        for i in range(2):
            address = addresses[i]
            option = OptionsToken.at(address)
            symbol = option.symbol()
            options.append(
                {
                    "address": address,
                    "symbol": symbol,
                    "oppositeAddress": addresses[1 - i],
                    "marketAddress": market.address,
                    "oracle": market.oracle(),
                    "isPutMarket": market.isPutMarket(),
                    "alpha": market.alpha(),
                    "expiryTime": market.expiryTime(),
                    "strikePrice": market.strikePrice(),
                    "baseAddress": baseAddress,
                    "baseSymbol": baseSymbol,
                    "isLong": i == 0,
                }
            )

    print(json.dumps(options, indent=4, sort_keys=True))
