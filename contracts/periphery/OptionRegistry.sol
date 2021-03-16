// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/utils/Address.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

import "../OptionFactory.sol";
import "../OptionMarket.sol";

contract OptionRegistry is Ownable {
    using Address for address;
    using SafeERC20 for IERC20;
    using SafeMath for uint256;

    mapping(address => mapping(uint256 => mapping(bool => OptionMarket))) markets;
    mapping(OptionMarket => mapping(uint256 => mapping(bool => OptionToken))) options;

    /**
     * @dev Fetch option market from underlying, expiry and whether call/put.
     * @param underlying Address of underlying ERC20 token. Equal to 0x0 for ETH.
     * @param expiry Expiry time as timestamp
     * @param isPut Put if true, call if false
     */
    function getMarket(address underlying, uint256 expiry, bool isPut) external view returns (OptionMarket) {
        return markets[underlying][expiry][isPut];
    }

    /**
     * @dev Fetch option token from market, strike and whether long/short.
     * @param market Address of {OptionMarket} contract
     * @param strikePrice Strike price in USD multiplied by 1e18
     * @param isLong Long position if true, short position if false
     */

    function getOption(OptionMarket market, uint256 strikePrice, bool isLong) external view returns (OptionToken) {
        return options[market][strikePrice][isLong];
    }

    /**
     * @dev Called by owner to register a market and its options. Should be
     * called whenever a new market is deployed.
     */
    function registerMarket(OptionMarket market, address underlying) external onlyOwner {
        markets[underlying][market.expiryTime()][market.isPut()] = market;

        uint256 numStrikes = market.numStrikes();
        for (uint256 i = 0; i < numStrikes; i = i.add(1)) {
            uint256 strike = market.strikePrices(i);
            options[market][strike][true] = market.longTokens(i);
            options[market][strike][false] = market.shortTokens(i);
        }
    }
}
