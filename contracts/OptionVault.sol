// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/utils/Address.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

import "./libraries/UniERC20.sol";
import "./OptionMarket.sol";
import "./OptionToken.sol";
import "./OptionViews.sol";

contract OptionVault is Ownable, ReentrancyGuard, ERC20 {
    using Address for address;
    using SafeERC20 for IERC20;
    using UniERC20 for IERC20;
    using SafeMath for uint256;

    address public strategy;
    IERC20 public baseToken;
    OptionViews public optionViews;

    mapping(OptionMarket => bool) public marketAdded;
    OptionMarket[] public markets;

    bool public isPaused;
    uint256 public totalSupplyCap;

    constructor(
        address _baseToken,
        address _optionViews,
        string memory name,
        string memory symbol
    ) public ERC20(name, symbol) {
        strategy = msg.sender;
        baseToken = IERC20(_baseToken);
        optionViews = OptionViews(_optionViews);

        // use same decimals as base token
        uint8 decimals = IERC20(_baseToken).isETH() ? 18 : ERC20UpgradeSafe(_baseToken).decimals();
        _setupDecimals(decimals);
    }

    function deposit(uint256 sharesOut, uint256 maxAmountIn) external payable nonReentrant returns (uint256 amountIn) {
        require(sharesOut > 0, "Shares out must be > 0");
        require(!isPaused, "Paused");

        // can't use `_calcOptionsAndLpAmounts` since need to subtract msg.value
        uint256 _totalSupply = totalSupply();
        if (_totalSupply == 0) {
            amountIn = sharesOut;
        } else {
            uint256 balance = baseToken.uniBalanceOf(address(this));
            if (baseToken.isETH()) {
                balance = balance.sub(msg.value);
            }
            amountIn = balance.mul(sharesOut).div(_totalSupply).add(1);
        }

        baseToken.uniTransferFromSenderToThis(maxAmountIn);

        for (uint256 i = 0; i < markets.length; i++) {
            (uint256[] memory longAmounts, uint256[] memory shortAmounts, uint256 lpShares) = _calcOptionsAndLpAmounts(
                markets[i],
                sharesOut
            );
            require(amountIn <= maxAmountIn, "Max slippage exceeded");
            uint256 remaining = maxAmountIn.sub(amountIn);
            uint256 spent = _buyInternal(markets[i], longAmounts, shortAmounts, lpShares, remaining);
            amountIn = amountIn.add(spent);
        }

        _mint(msg.sender, sharesOut);
        require(totalSupplyCap == 0 || totalSupply() <= totalSupplyCap, "Total supply cap exceeded");

        require(amountIn <= maxAmountIn, "Max slippage exceeded");
        baseToken.uniTransfer(msg.sender, maxAmountIn.sub(amountIn));
    }

    function withdraw(uint256 sharesIn, uint256 minAmountOut) external nonReentrant returns (uint256 amountOut) {
        require(sharesIn > 0, "Shares in must be > 0");
        require(!isPaused, "Paused");

        amountOut = _calcAmountFromShares(baseToken, sharesIn);

        for (uint256 i = 0; i < markets.length; i++) {
            (uint256[] memory longAmounts, uint256[] memory shortAmounts, uint256 lpShares) = _calcOptionsAndLpAmounts(
                markets[i],
                sharesIn
            );
            uint256 received = _sellInternal(markets[i], longAmounts, shortAmounts, lpShares, 0);
            amountOut = amountOut.add(received);
        }

        require(amountOut >= minAmountOut, "Max slippage exceeded");

        // burn after so total supply is correct in calculating amounts
        _burn(msg.sender, sharesIn);
        baseToken.uniTransfer(msg.sender, amountOut);
    }

    function buy(
        OptionMarket market,
        uint256[] memory longOptionsIn,
        uint256[] memory shortOptionsIn,
        uint256 lpSharesOut,
        uint256 maxAmountIn
    ) external nonReentrant returns (uint256) {
        require(msg.sender == strategy, "!strategy");
        return _buyInternal(market, longOptionsIn, shortOptionsIn, lpSharesOut, maxAmountIn);
    }

    function _buyInternal(
        OptionMarket market,
        uint256[] memory longOptionsIn,
        uint256[] memory shortOptionsIn,
        uint256 lpSharesOut,
        uint256 maxAmountIn
    ) internal returns (uint256 amountIn) {
        require(marketAdded[market], "Market not found");
        require(maxAmountIn <= baseToken.uniBalanceOf(address(this)), "Not enough funds");

        uint256 n = market.numStrikes();
        require(longOptionsIn.length == n, "Lengths don't match");
        require(shortOptionsIn.length == n, "Lengths don't match");

        if (lpSharesOut > 0) {
            uint256 value = baseToken.isETH() ? maxAmountIn : 0;
            amountIn = market.deposit{value: value}(lpSharesOut, maxAmountIn);
        }

        for (uint256 k = 0; k < n; k++) {
            require(amountIn <= maxAmountIn, "Max slippage exceeded");
            if (longOptionsIn[k] > 0) {
                uint256 remaining = maxAmountIn.sub(amountIn);
                uint256 value = baseToken.isETH() ? remaining : 0;
                uint256 spent = market.buy{value: value}(true, k, longOptionsIn[k], remaining);
                amountIn = amountIn.add(spent);
            }
            if (shortOptionsIn[k] > 0) {
                uint256 remaining = maxAmountIn.sub(amountIn);
                uint256 value = baseToken.isETH() ? remaining : 0;
                uint256 spent = market.buy{value: value}(false, k, shortOptionsIn[k], remaining);
                amountIn = amountIn.add(spent);
            }
        }

        require(amountIn <= maxAmountIn, "Max slippage exceeded");
    }

    function sell(
        OptionMarket market,
        uint256[] memory longOptionsOut,
        uint256[] memory shortOptionsOut,
        uint256 lpSharesIn,
        uint256 minAmountOut
    ) public nonReentrant returns (uint256) {
        require(msg.sender == strategy, "!strategy");
        return _sellInternal(market, longOptionsOut, shortOptionsOut, lpSharesIn, minAmountOut);
    }

    function _sellInternal(
        OptionMarket market,
        uint256[] memory longOptionsOut,
        uint256[] memory shortOptionsOut,
        uint256 lpSharesIn,
        uint256 minAmountOut
    ) internal returns (uint256 amountOut) {
        require(marketAdded[market], "Market not found");

        uint256 n = market.numStrikes();
        require(longOptionsOut.length == n, "Lengths don't match");
        require(shortOptionsOut.length == n, "Lengths don't match");

        for (uint256 k = 0; k < n; k++) {
            if (longOptionsOut[k] > 0) {
                uint256 received = market.sell(true, k, longOptionsOut[k], 0);
                amountOut = amountOut.add(received);
            }
            if (shortOptionsOut[k] > 0) {
                uint256 received = market.sell(false, k, shortOptionsOut[k], 0);
                amountOut = amountOut.add(received);
            }
        }

        if (lpSharesIn > 0) {
            uint256 received = market.withdraw(lpSharesIn, 0);
            amountOut = amountOut.add(received);
        }

        require(amountOut >= minAmountOut, "Max slippage exceeded");
    }

    function _calcOptionsAndLpAmounts(OptionMarket market, uint256 sharesOut)
        internal
        returns (
            uint256[] memory longAmounts,
            uint256[] memory shortAmounts,
            uint256 lpShares
        )
    {
        uint256 n = market.numStrikes();
        longAmounts = new uint256[](n);
        shortAmounts = new uint256[](n);
        for (uint256 k = 0; k < market.numStrikes(); k++) {
            OptionToken longToken = market.longTokens(k);
            OptionToken shortToken = market.shortTokens(k);
            longAmounts[k] = _calcAmountFromShares(longToken, sharesOut);
            shortAmounts[k] = _calcAmountFromShares(shortToken, sharesOut);
        }
        lpShares = _calcAmountFromShares(market, sharesOut);
    }

    function _calcAmountFromShares(IERC20 token, uint256 shares) public view returns (uint256) {
        uint256 _totalSupply = totalSupply();
        if (_totalSupply == 0) {
            return token == baseToken ? shares : 0;
        }
        uint256 balance = token.uniBalanceOf(address(this));
        if (balance == 0) {
            return 0;
        }
        return balance.mul(shares).div(_totalSupply);
    }

    function totalAssets() external view returns (uint256 assets) {
        assets = baseToken.uniBalanceOf(address(this));
        for (uint256 i = 0; i < markets.length; i++) {
            OptionMarket market = markets[i];
            uint256 n = market.numStrikes();
            uint256[] memory longOptionsIn = new uint256[](n);
            uint256[] memory shortOptionsIn = new uint256[](n);
            for (uint256 k = 0; k < n; k++) {
                longOptionsIn[k] = market.longTokens(k).balanceOf(address(this));
                shortOptionsIn[k] = market.shortTokens(k).balanceOf(address(this));
            }
            uint256 lpSharesIn = market.balanceOf(address(this));
            assets = assets.add(optionViews.getSellCost(market, longOptionsIn, shortOptionsIn, lpSharesIn));
        }
    }

    function addMarket(OptionMarket market) external {
        require(msg.sender == strategy, "!strategy");
        require(!marketAdded[market], "Already added");
        require(market.baseToken() == baseToken, "Base tokens don't match");
        if (!baseToken.isETH()) {
            baseToken.approve(address(market), uint256(-1));
        }
        markets.push(market);
        marketAdded[market] = true;
    }

    function removeMarket(OptionMarket market) external {
        require(msg.sender == strategy, "!strategy");
        require(marketAdded[market], "Market not found");

        // preserves array order, so inefficient in terms of gas use
        // but only called infrequently by strategy so it's ok
        uint256 n = markets.length;
        uint256 offset;
        for (uint256 i = 0; i < n; i++) {
            if (markets[i] == market) {
                offset += 1;
            }
            if (offset > 0 && i + offset < n) {
                markets[i] = markets[i + offset];
            }
        }
        assert(offset > 0);
        for (uint256 i = 0; i < offset; i++) {
            markets.pop();
        }
        marketAdded[market] = false;
    }

    function numMarkets() external view returns (uint256) {
        return markets.length;
    }

    function allMarkets() external view returns (OptionMarket[] memory _markets) {
        _markets = new OptionMarket[](markets.length);
        for (uint256 i = 0; i < markets.length; i++) {
            _markets[i] = markets[i];
        }
    }

    function setStrategy(address _strategy) external onlyOwner {
        strategy = _strategy;
    }

    // used for guarded launch
    function setTotalSupplyCap(uint256 _totalSupplyCap) external onlyOwner {
        totalSupplyCap = _totalSupplyCap;
    }

    // emergency use only. to be removed in future versions
    function pause() external onlyOwner {
        isPaused = true;
    }

    // emergency use only. to be removed in future versions
    function unpause() external onlyOwner {
        isPaused = false;
    }

    // emergency use only. to be removed in future versions
    function emergencyWithdraw(IERC20 token) external onlyOwner {
        token.uniTransfer(msg.sender, token.uniBalanceOf(address(this)));
    }

    fallback() external payable {}

    receive() external payable {}
}
