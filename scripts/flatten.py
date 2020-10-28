import os


PATHS = [
    "~/.brownie/packages/OpenZeppelin/openzeppelin-contracts@3.2.0/contracts/GSN/Context.sol",
    "~/.brownie/packages/OpenZeppelin/openzeppelin-contracts@3.2.0/contracts/math/SafeMath.sol",
    "~/.brownie/packages/OpenZeppelin/openzeppelin-contracts@3.2.0/contracts/math/Math.sol",
    "~/.brownie/packages/OpenZeppelin/openzeppelin-contracts@3.2.0/contracts/token/ERC20/IERC20.sol",
    "~/.brownie/packages/OpenZeppelin/openzeppelin-contracts@3.2.0/contracts/token/ERC20/ERC20.sol",
    "~/.brownie/packages/OpenZeppelin/openzeppelin-contracts@3.2.0/contracts/token/ERC20/SafeERC20.sol",
    "~/.brownie/packages/OpenZeppelin/openzeppelin-contracts@3.2.0/contracts/utils/Address.sol",
    "contracts/mocks/MockToken.sol",
    "contracts/CharmToken.sol",
    "interfaces/IOracle.sol",
    "interfaces/IUniswapV2Pair.sol",
    "contracts/UniswapOracle.sol",
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
