// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/utils/Address.sol";

import "./libraries/CloneFactory.sol";
import "./libraries/UniERC20.sol";
import "./libraries/openzeppelin/ERC20UpgradeSafe.sol";
import "./OptionMarket.sol";
import "./OptionSymbol.sol";

contract OptionFactory is CloneFactory, OptionSymbol {
    using Address for address;
    using SafeERC20 for IERC20;
    using UniERC20 for IERC20;
    using SafeMath for uint256;

    address public optionMarketLibrary;
    address public optionTokenLibary;
    address[] public markets;

    // used by `createMarket` to avoid stack too deep error
    address private oracle;
    uint256[] private strikePrices;
    uint256 private alpha;
    uint256 private expiryTime;
    bool private isPut;
    uint256 private tradingFee;
    uint256 private balanceCap;
    uint256 private totalSupplyCap;

    constructor(address _optionMarketLibrary, address _optionTokenLibrary) public {
        require(_optionMarketLibrary != address(0), "optionMarketLibrary should not be address 0");
        require(_optionTokenLibrary != address(0), "optionTokenLibary should not be address 0");
        optionMarketLibrary = _optionMarketLibrary;
        optionTokenLibary = _optionTokenLibrary;
    }

    function createMarket(
        address _baseToken,
        address _quoteToken,
        address _oracle,
        uint256[] memory _strikePrices,
        uint256 _expiryTime,
        uint256 _alpha,
        bool _isPut,
        uint256 _tradingFee,
        uint256 _balanceCap,
        uint256 _totalSupplyCap
    ) external returns (address market) {
        // set member variables to avoid stack too deep error
        // TODO: cleaner way to do this?
        oracle = _oracle;
        strikePrices = _strikePrices;
        expiryTime = _expiryTime;
        alpha = _alpha;
        isPut = _isPut;
        tradingFee = _tradingFee;
        balanceCap = _balanceCap;
        totalSupplyCap = _totalSupplyCap;

        market = createClone(optionMarketLibrary);
        address baseToken = isPut ? _quoteToken : _baseToken;
        uint8 decimals = IERC20(baseToken).isETH() ? 18 : ERC20UpgradeSafe(baseToken).decimals();
        string memory underlyingSymbol = IERC20(_baseToken).isETH() ? "ETH" : ERC20UpgradeSafe(_baseToken).symbol();

        string memory symbol;
        address[] memory longTokens = new address[](strikePrices.length);
        address[] memory shortTokens = new address[](strikePrices.length);
        for (uint256 i = 0; i < strikePrices.length; i++) {
            longTokens[i] = createClone(optionTokenLibary);
            shortTokens[i] = createClone(optionTokenLibary);
            symbol = getSymbol(underlyingSymbol, strikePrices[i], expiryTime, isPut, true);
            OptionToken(longTokens[i]).initialize(market, symbol, symbol, decimals);
            symbol = getSymbol(underlyingSymbol, strikePrices[i], expiryTime, isPut, false);
            OptionToken(shortTokens[i]).initialize(market, symbol, symbol, decimals);
        }

        OptionMarket(market).initialize(
            baseToken,
            oracle,
            longTokens,
            shortTokens,
            strikePrices,
            expiryTime,
            alpha,
            isPut,
            tradingFee,
            balanceCap,
            totalSupplyCap
        );
        OptionMarket(market).transferOwnership(msg.sender);
        markets.push(market);
    }

    function numMarkets() external view returns (uint256) {
        return markets.length;
    }
}
