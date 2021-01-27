// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/utils/Address.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

import "./libraries/openzeppelin/ERC20UpgradeSafe.sol";
import "./libraries/CloneFactory.sol";
import "./libraries/UniERC20.sol";
import "./OptionMarket.sol";
import "./OptionSymbol.sol";

contract OptionFactory is CloneFactory, OptionSymbol, ReentrancyGuard {
    using Address for address;
    using SafeERC20 for IERC20;
    using UniERC20 for IERC20;
    using SafeMath for uint256;

    address public optionMarketLibrary;
    address public optionTokenLibrary;
    address[] public markets;

    uint256[] private _strikePrices;
    uint256 private _expiryTime;
    bool private _isPut;
    string private _underlyingSymbol;
    address private _baseToken;
    address private _marketAddress;

    constructor(address _optionMarketLibrary, address _optionTokenLibrary) public {
        require(_optionMarketLibrary != address(0), "optionMarketLibrary should not be address 0");
        require(_optionTokenLibrary != address(0), "optionTokenLibrary should not be address 0");
        optionMarketLibrary = _optionMarketLibrary;
        optionTokenLibrary = _optionTokenLibrary;
    }

    function createMarket(
        address baseAsset,
        address quoteAsset,
        address oracle,
        uint256[] memory strikePrices,
        uint256 expiryTime,
        bool isPut,
        uint256 tradingFee
    ) external nonReentrant returns (address) {
        // avoid stack too deep error
        _strikePrices = strikePrices;
        _expiryTime = expiryTime;
        _isPut = isPut;
        _underlyingSymbol = IERC20(baseAsset).uniSymbol();
        _baseToken = isPut ? quoteAsset : baseAsset;

        _marketAddress = createClone(optionMarketLibrary);
        markets.push(_marketAddress);

        OptionMarket(_marketAddress).initialize(
            _baseToken,
            oracle,
            _createOptionTokens(true),
            _createOptionTokens(false),
            strikePrices,
            expiryTime,
            isPut,
            tradingFee,
            getMarketSymbol(_underlyingSymbol, expiryTime, isPut)
        );

        // transfer ownership to sender
        OptionMarket(_marketAddress).transferOwnership(msg.sender);
        return _marketAddress;
    }

    function _createOptionTokens(bool isLong) private returns (address[] memory optionTokens) {
        uint8 decimals = IERC20(_baseToken).isETH() ? 18 : ERC20UpgradeSafe(_baseToken).decimals();

        optionTokens = new address[](_strikePrices.length);
        for (uint256 i = 0; i < _strikePrices.length; i++) {
            optionTokens[i] = createClone(optionTokenLibrary);
            string memory symbol = getOptionSymbol(_underlyingSymbol, _strikePrices[i], _expiryTime, _isPut, isLong);
            OptionToken(optionTokens[i]).initialize(_marketAddress, symbol, symbol, decimals);
        }
    }

    function numMarkets() external view returns (uint256) {
        return markets.length;
    }
}
