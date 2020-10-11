// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/utils/Address.sol";


contract MockToken is ERC20("Mock Token", "MOCK") {
    using Address for address;
    using SafeERC20 for IERC20;
    using SafeMath for uint256;

    function mint(address account, uint256 amount) public {
        _mint(account, amount);
    }
}

