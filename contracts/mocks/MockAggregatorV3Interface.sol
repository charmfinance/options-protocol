// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;


import "../../interfaces/AggregatorV3Interface.sol";


contract MockAggregatorV3Interface is AggregatorV3Interface {
    uint8 public _decimals;
    int256 public price;
    uint256 public timestamp;

    function decimals() external view override returns (uint8) {
        return _decimals;
    }

    function setDecimals(uint8 d) external {
        _decimals = d;
    }

    function getRoundData(uint80 _roundId) external view override returns (
        uint80,
        int256,
        uint256,
        uint256,
        uint80
    ) {}


    function latestRoundData() external view override returns (
        uint80,
        int256,
        uint256,
        uint256,
        uint80
    ) {
        return (0, price, 0, timestamp, 0);
    }

    function setPrice(int256 _price) external {
        price = _price;
    }

    function setTimestamp(uint256 _timestamp) external {
        timestamp = _timestamp;
    }

    function description() external view override returns (string memory) {
        return "";
    }

    function version() external view override returns (uint256) {
        return 0;
    }
}
