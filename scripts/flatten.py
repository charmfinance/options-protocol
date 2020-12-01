import os


PATHS = [
    "~/.brownie/packages/OpenZeppelin/openzeppelin-contracts@3.2.0/contracts/GSN/Context.sol",
    "~/.brownie/packages/OpenZeppelin/openzeppelin-contracts@3.2.0/contracts/access/Ownable.sol",
    "~/.brownie/packages/OpenZeppelin/openzeppelin-contracts@3.2.0/contracts/math/SafeMath.sol",
    "~/.brownie/packages/OpenZeppelin/openzeppelin-contracts@3.2.0/contracts/math/Math.sol",
    "~/.brownie/packages/OpenZeppelin/openzeppelin-contracts@3.2.0/contracts/token/ERC20/IERC20.sol",
    "~/.brownie/packages/OpenZeppelin/openzeppelin-contracts@3.2.0/contracts/token/ERC20/ERC20.sol",
    "~/.brownie/packages/OpenZeppelin/openzeppelin-contracts@3.2.0/contracts/token/ERC20/SafeERC20.sol",
    "~/.brownie/packages/OpenZeppelin/openzeppelin-contracts@3.2.0/contracts/utils/Address.sol",
    "~/.brownie/packages/OpenZeppelin/openzeppelin-contracts@3.2.0/contracts/utils/ReentrancyGuard.sol",
    "~/.brownie/packages/OpenZeppelin/openzeppelin-contracts@3.2.0/contracts/utils/Strings.sol",
    "contracts/libraries/openzeppelin/Initializable.sol",
    "contracts/libraries/openzeppelin/ContextUpgradeSafe.sol",
    "contracts/libraries/openzeppelin/OwnableUpgradeSafe.sol",
    "contracts/libraries/openzeppelin/ReentrancyGuardUpgradeSafe.sol",
    "contracts/libraries/openzeppelin/ERC20UpgradeSafe.sol",
    "interfaces/AggregatorV3Interface.sol",
    "interfaces/IOracle.sol",
    "contracts/libraries/ABDKMath64x64.sol",
    "contracts/libraries/BokkyPooBahsDateTimeLibrary.sol",
    "contracts/libraries/CloneFactory.sol",
    "contracts/libraries/UniERC20.sol",
    "contracts/ChainlinkOracle.sol",
    "contracts/OptionSymbol.sol",
    "contracts/OptionToken.sol",
    "contracts/OptionMarket.sol",
    "contracts/OptionFactory.sol",
    "contracts/OptionsToken.sol",
    "contracts/OptionsMarketMaker.sol",
    "contracts/OptionsFactory.sol",
]

PREFIX = """
// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;

"""

IGNORE = [
    "// SPDX-License-Identifier:",
    "import ",
    "pragma ",
]


def main():
    lines = []
    for path in PATHS:
        path = os.path.expanduser(path)
        with open(path, "r") as f:
            for line in f:
                if all(not line.strip().startswith(s) for s in IGNORE):
                    lines.append(line)
    print(PREFIX + "".join(lines))


if __name__ == "__main__":
    main()
