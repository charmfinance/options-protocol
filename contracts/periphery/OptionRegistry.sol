// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;
pragma experimental ABIEncoderV2;

import "@openzeppelin/contracts/math/SafeMath.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/utils/Address.sol";

import "../OptionFactory.sol";
import "../OptionMarket.sol";
import "../OptionToken.sol";


contract OptionRegistry {
    using Address for address;
    using SafeERC20 for IERC20;
    using SafeMath for uint256;

    struct OptionDetails {
        bool isLongToken;
        uint256 strikeIndex;
        uint256 strikePrice;
    }

    OptionFactory public constant factory = OptionFactory(0xCDFE169dF3D64E2e43D88794A21048A52C742F2B);

    mapping(IERC20 => mapping(uint256 => mapping(bool => OptionMarket))) public markets; // baseToken => expiry => isPut => market
    mapping(OptionMarket => mapping(uint256 => mapping(bool => OptionToken))) public options; // market => strikePrice => isLongToken
    mapping(OptionToken => OptionDetails) public optionDetails;

    uint256 public lastIndex;

    /**
     * @dev Fetch option market
     * @param baseToken Address of base token. Same as underlying for calls and
     * strike currency for puts. Equal to 0x0 for ETH
     * @param expiry Expiry time as timestamp
     * @param isPut True if put, false if call
     */
    function getMarket(IERC20 baseToken, uint256 expiry, bool isPut) external view returns (OptionMarket) {
        return markets[baseToken][expiry][isPut];
    }

    /**
     * @dev Fetch option token
     * @param market Parent market
     * @param strikePrice Strike price in USDC multiplied by 1e18
     * @param isLongToken True if long position, false if short position
     */
    function getOption(OptionMarket market, uint256 strikePrice, bool isLongToken) external view returns (OptionToken) {
        return options[market][strikePrice][isLongToken];
    }

    /**
     * @dev Fetch option details
     * @param optionToken Option token
     */
    function getOptionDetails(OptionToken optionToken) external view returns (OptionDetails memory) {
        return optionDetails[optionToken];
    }

    /**
     * @dev Add mappings for any new markets that have been added to factory
     * since the last time this method was called
     */
    function populateMarkets() external {
        uint256 numMarkets = factory.numMarkets();
        while (lastIndex < numMarkets) {
            OptionMarket market = OptionMarket(factory.markets(lastIndex));
            _populateMarket(market);
            lastIndex = lastIndex.add(1);
        }
    }

    function _populateMarket(OptionMarket market) internal {
        markets[market.baseToken()][market.expiryTime()][market.isPut()] = market;

        uint256 numStrikes = market.numStrikes();
        for (uint256 i = 0; i < numStrikes; i = i.add(1)) {
            OptionToken longToken = market.longTokens(i);
            OptionToken shortToken = market.shortTokens(i);
            uint256 strikePrice = market.strikePrices(i);

            options[market][strikePrice][true] = longToken;
            options[market][strikePrice][false] = shortToken;
            optionDetails[longToken] = OptionDetails(true, i, strikePrice);
            optionDetails[shortToken] = OptionDetails(false, i, strikePrice);
        }
    }
}
