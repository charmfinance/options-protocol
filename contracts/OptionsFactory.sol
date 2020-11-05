// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/utils/Address.sol";

import "./libraries/CloneFactory.sol";
import "./OptionsMarketMaker.sol";

contract OptionsFactory is CloneFactory {
    using Address for address;
    using SafeERC20 for IERC20;
    using UniERC20 for IERC20;
    using SafeMath for uint256;

    address public marketLibrary;
    address public optionsTokenLibrary;
    address[] public markets;

    constructor(address _marketLibrary, address _optionsTokenLibrary) public {
        require(_marketLibrary != address(0), "marketLibrary should not be address 0");
        require(_optionsTokenLibrary != address(0), "optionsTokenLibrary should not be address 0");
        marketLibrary = _marketLibrary;
        optionsTokenLibrary = _optionsTokenLibrary;
    }

    function createMarket(
        address baseToken,
        address oracle,
        bool isPutMarket,
        uint256 strikePrice,
        uint256 alpha,
        uint256 expiryTime,
        string memory longName,
        string memory longSymbol,
        string memory shortName,
        string memory shortSymbol
    ) external returns (address market) {
        market = createClone(marketLibrary);
        address longToken = createClone(optionsTokenLibrary);
        address shortToken = createClone(optionsTokenLibrary);

        uint8 decimals = IERC20(baseToken).isETH() ? 18 : ERC20UpgradeSafe(baseToken).decimals();
        OptionsToken(longToken).initialize(market, longName, longSymbol, decimals);
        OptionsToken(shortToken).initialize(market, shortName, shortSymbol, decimals);

        OptionsMarketMaker(market).initialize(
            baseToken,
            oracle,
            isPutMarket,
            strikePrice,
            alpha,
            expiryTime,
            longToken,
            shortToken
        );
        OptionsMarketMaker(market).transferOwnership(msg.sender);
        markets.push(market);
    }

    function numMarkets() external view returns (uint256) {
        return markets.length;
    }
}
