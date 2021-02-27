from brownie import (
    accounts,
    network,
    Contract,
    OptionVault,
)


TOKEN = "ETH"
OPTION_TYPE = "call"

VIEWS_LIB = {
    "mainnet": "0x4c4D29e73C651840A561e97b3D87E3d5F1afd64F",
    "rinkeby": "0xE216F6C196f51a2e774F8D21C9aBBbD9b0577fbB",
}


TOKEN_ADDRESSES = {
    "mainnet": {
        "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "ETH": "0x0000000000000000000000000000000000000000",
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    },
    "rinkeby": {
        "ETH": "0x0000000000000000000000000000000000000000",
        "USDC": "0xE7d541c18D6aDb863F4C570065c57b75a53a64d3",
        "WBTC": "0x4f21f715A0DF6c498560fB6EC387F74DdeB93560",
    },
}


def main():
    assert OPTION_TYPE in ["call", "put"]

    _network = network.show_active()
    print(f"Network: {_network}")

    deployer = accounts.load("deployer")
    balance = deployer.balance()

    if OPTION_TYPE == "call":
        baseAddress = TOKEN_ADDRESSES[_network][TOKEN]
    else:
        baseAddress = TOKEN_ADDRESSES[_network]["USDC"]

    symbol = f"Charm LP Vault {TOKEN} {OPTION_TYPE}"
    vault = deployer.deploy(
        OptionVault,
        baseAddress,
        VIEWS_LIB[_network],
        symbol,
        symbol,
        publish_source=True,
    )

    print(f"Vault address: {vault.address}")
    print(f"Gas used in deployment: {(balance - deployer.balance()) / 1e18:.4f} ETH")
