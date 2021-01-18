// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/utils/Address.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

import "./libraries/CloneFactory.sol";
import "./libraries/UniERC20.sol";
import "./libraries/openzeppelin/ERC20UpgradeSafe.sol";
import "./OptionMarket.sol";
import "./OptionSymbol.sol";

contract OptionFactory is CloneFactory, OptionSymbol, ReentrancyGuard {
    using Address for address;
    using SafeERC20 for IERC20;
    using UniERC20 for IERC20;
    using SafeMath for uint256;

    address public optionMarketLibrary;
    address public optionTokenLibary;
    address[] public markets;

    // avoid stack too deep error
    uint256[] private strikePrices;
    uint256 private expiryTime;
    bool private isPut;
    IERC20 private underlyingToken;
    uint8 private baseDecimals;

    constructor(address _optionMarketLibrary, address _optionTokenLibrary) public {
        require(_optionMarketLibrary != address(0), "optionMarketLibrary should not be address 0");
        require(_optionTokenLibrary != address(0), "optionTokenLibary should not be address 0");
        optionMarketLibrary = _optionMarketLibrary;
        optionTokenLibary = _optionTokenLibrary;
    }

    function createMarket(
        address _baseAsset,
        address _quoteAsset,
        address _oracle,
        uint256[] memory _strikePrices,
        uint256 _expiryTime,
        bool _isPut,
        uint256 _tradingFee,
        uint256 _balanceCap,
        uint256 _disputePeriod
    ) external nonReentrant returns (address) {
        // set member variables to avoid stack too deep error
        // TODO: cleaner way to do this?
        strikePrices = _strikePrices;
        expiryTime = _expiryTime;
        isPut = _isPut;
        underlyingToken = IERC20(_baseAsset);

        address baseToken = isPut ? _quoteAsset : _baseAsset;
        baseDecimals = IERC20(baseToken).isETH() ? 18 : ERC20UpgradeSafe(baseToken).decimals();

        address marketAddress = createClone(optionMarketLibrary);
        OptionMarket market = OptionMarket(marketAddress);
        markets.push(marketAddress);

        market.initialize(
            baseToken,
            _oracle,
            _createOptionTokens(marketAddress, true),
            _createOptionTokens(marketAddress, false),
            _strikePrices,
            _expiryTime,
            _isPut,
            _tradingFee,
            _balanceCap,
            _disputePeriod,
            getMarketSymbol(underlyingToken.uniSymbol(), expiryTime, isPut)
        );

        // transfer ownership to sender
        market.transferOwnership(msg.sender);
        return marketAddress;
    }

    function _createOptionTokens(address marketAddress, bool isLong) private returns (address[] memory optionTokens) {
        optionTokens = new address[](strikePrices.length);
        for (uint256 i = 0; i < strikePrices.length; i++) {
            optionTokens[i] = createClone(optionTokenLibary);
            string memory symbol = getOptionSymbol(
                underlyingToken.uniSymbol(),
                strikePrices[i],
                expiryTime,
                isPut,
                isLong
            );
            OptionToken(optionTokens[i]).initialize(marketAddress, symbol, symbol, baseDecimals);
        }
    }

    function numMarkets() external view returns (uint256) {
        return markets.length;
    }
}
