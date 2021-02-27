import datetime
import json
import sys
import yaml

from brownie import (
    accounts,
    network,
    Contract,
    OptionVault,
    ZERO_ADDRESS,
)


PATH = {
    "mainnet": "vaults.yaml",
    "rinkeby": "vaults-rinkeby.yaml",
}


def main():
    with open(PATH[network.show_active()], "r") as f:
        markets = yaml.safe_load(f)

    res = []
    for address in markets:
        vault = OptionVault.at(address)
        baseAddress = str(vault.baseToken())
        if baseAddress == ZERO_ADDRESS:
            baseSymbol = "ETH"
        else:
            baseToken = Contract.from_explorer(baseAddress)
            baseSymbol = baseToken.symbol()

        assert vault.symbol().startswith("Charm LP Vault")
        underlyingSymbol = vault.symbol().split()[3]

        totalSupplyCap = vault.totalSupplyCap()

        markets = vault.allMarkets()

        res.append(
            {
                "address": address,
                "baseAddress": baseAddress,
                "baseSymbol": baseSymbol,
                "decimals": vault.decimals(),
                "underlyingSymbol": underlyingSymbol,
                "totalSupplyCap": totalSupplyCap,
                "symbol": vault.symbol(),
            }
        )

    print(json.dumps(res, indent=4, sort_keys=True))
