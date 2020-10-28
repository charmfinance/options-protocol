// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;

import "@openzeppelin/contracts/math/Math.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/utils/Address.sol";

import "../interfaces/AggregatorV3Interface.sol";
import "../interfaces/IOracle.sol";

contract ChainlinkOracle is IOracle {
    using Address for address;
    using SafeERC20 for IERC20;
    using SafeMath for uint256;

    uint256 public constant DECIMALS = 18;

    AggregatorV3Interface public priceFeed;

    constructor(address _priceFeed) public {
        priceFeed = AggregatorV3Interface(_priceFeed);
    }

    function getPrice() external override view returns (uint256 price) {
        uint256 decimals = uint256(priceFeed.decimals());
        (, int256 px, , uint256 timestamp, ) = priceFeed.latestRoundData();
        require(timestamp > 0, "Round not complete");
        require(px > 0, "Price is not > 0");

        price = uint256(px);
        if (decimals > DECIMALS) {
            price = price.div(10**decimals.sub(DECIMALS));
        } else if (decimals < DECIMALS) {
            price = price.mul(10**DECIMALS.sub(decimals));
        }
    }
}
