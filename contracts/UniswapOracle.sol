// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;

import "@openzeppelin/contracts/math/Math.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";

import "../interfaces/IUniswapV2Pair.sol";
import "../interfaces/IOracle.sol";

contract UniswapOracle is IOracle {
    using SafeMath for uint256;

    uint256 public constant SCALE = 1e18;
    uint256 public constant Q112 = 1 << 112;

    IUniswapV2Pair public pair;
    uint256 public twapWindowStartTime;
    uint256 public baseMultiplier;
    uint256 public quoteMultiplier;
    bool public isInverted;

    // data at the start of the TWAP window
    uint256 public snapshotSpotPrice;
    uint256 public snapshotCumulativePrice;
    uint256 public snapshotTimestamp;

    /**
     * Uniswap V2 TWAP Oracle
     *
     * To calculate the TWAP between time A and time B, call {takeSnapshot} just
     * before time A. Then at time B, call {getPrice} and it will return the
     * TWAP of this window
     *
     * @param _pair                     UniswapV2Pair address
     * @param _twapWindowStartTime      Start time of the TWAP window
     * @param decimals0                 Decimal places used by token0 in pair
     * @param decimals1                 Decimal places used by token1 in pair
     * @param _isInverted               If false, this oracle calculates token0/token1 price
     *                                  If true, token1/token0 price
     */
    constructor(
        address _pair,
        uint256 _twapWindowStartTime,
        uint256 decimals0,
        uint256 decimals1,
        bool _isInverted
    ) public {
        pair = IUniswapV2Pair(_pair);
        twapWindowStartTime = _twapWindowStartTime;

        require(decimals0 <= 18);
        require(decimals1 <= 18);

        isInverted = _isInverted;

        // set multipliers. divide by gcd to make overflows less likely
        uint256 min = Math.min(decimals0, decimals1);
        baseMultiplier = _isInverted ? 10**decimals1.sub(min) : 10**decimals0.sub(min);
        quoteMultiplier = _isInverted ? 10**decimals0.sub(min) : 10**decimals1.sub(min);

        // set initial data
        takeSnapshot();
    }

    /**
     * Fetches data from uniswap and updates {snapshotSpotPrice}, {snapshotCumulativePrice}
     * and {snapshotTimestamp}.
     *
     * When {getPrice} is called after this, it will return the TWAP during the
     * window starting from this takeSnapshot
     *
     * This method should be called just before the start of the TWAP window
     */
    function takeSnapshot() public {
        require(block.timestamp <= twapWindowStartTime, "TWAP window already started");
        (snapshotSpotPrice, snapshotCumulativePrice) = fetchSpotAndCumulativePrice();
        snapshotTimestamp = block.timestamp;
    }

    /**
     * Return TWAP since {takeSnapshot} was last called
     */
    function getPrice() external override view returns (uint256) {
        (uint256 newSpotPrice, uint256 newCumulativePrice) = fetchSpotAndCumulativePrice();

        // time since last takeSnapshot
        uint256 elapsed = block.timestamp.sub(snapshotTimestamp);

        // if not time has elapsed, just use the current spot price
        if (elapsed == 0) {
            return newSpotPrice;
        }

        // change in cumulative price since last fetch
        uint256 diff = newCumulativePrice.sub(snapshotCumulativePrice);
        return diff.mul(SCALE).mul(baseMultiplier).div(Q112).div(elapsed).div(SCALE).div(quoteMultiplier);
    }

    /**
     * Helper method called by {takeSnapshot} and {getPrice}. Returns spot price
     * and cumulative price from Uniswap
     */
    function fetchSpotAndCumulativePrice() public view returns (uint256 spotPrice, uint256 cumulativePrice) {
        (uint256 reserve0, uint256 reserve1, uint256 blockTimestampLast) = pair.getReserves();

        // check uniswap has liquidity
        require(reserve0 > 0 && reserve1 > 0, "No reserves");

        // cumulative price is returned in uq112x112 fixed point units
        uint256 last = isInverted ? pair.price1CumulativeLast() : pair.price0CumulativeLast();

        // add extra cumulative price since last fetch
        uint256 elapsed = block.timestamp.sub(blockTimestampLast);
        uint256 base = isInverted ? reserve0 : reserve1;
        uint256 quote = isInverted ? reserve1 : reserve0;

        // set spot price in case getPrice is called at the same time
        spotPrice = base.mul(SCALE).mul(baseMultiplier).div(quote).div(quoteMultiplier);

        // multiplication doesn't overflow as max value is 2^112 * 2^32 * 2^112
        uint256 sinceLast = elapsed.mul(Q112).mul(base).div(quote);
        cumulativePrice = last.add(sinceLast);
    }
}
