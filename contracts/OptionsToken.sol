// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/utils/Address.sol";

/**
 * ERC20 Token that allows the owner to mint to and burn from any address.
 *
 * The intended owner is the OptionsMarketMaker and it mints/burns these tokens
 * when users buy/sell options.
 */
contract OptionsToken is ERC20, Ownable {
    using Address for address;
    using SafeERC20 for IERC20;
    using SafeMath for uint256;

    constructor(string memory name, string memory symbol) public ERC20(name, symbol) {}

    function mint(address account, uint256 amount) public onlyOwner {
        _mint(account, amount);
    }

    function burn(address account, uint256 amount) public onlyOwner {
        _burn(account, amount);
    }
}
