// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/utils/Address.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

import "../libraries/UniERC20.sol";
import "../OptionMarket.sol";
import "../OptionToken.sol";
import "./OptionViews.sol";

contract OptionVault is Ownable, ReentrancyGuard, ERC20 {
    using Address for address;
    using SafeERC20 for IERC20;
    using UniERC20 for IERC20;
    using SafeMath for uint256;

    address public strategy;
    IERC20 public baseToken;
    OptionViews public optionViewsLibrary;

    mapping(OptionMarket => bool) public marketAdded;
    OptionMarket[] public markets;

    bool public isPaused;
    uint256 public totalSupplyCap;

    constructor(
        address _baseToken,
        address _optionViewsLibrary,
        string memory name,
        string memory symbol
    ) public ERC20(name, symbol) {
        strategy = msg.sender;
        baseToken = IERC20(_baseToken);
        optionViewsLibrary = OptionViews(_optionViewsLibrary);

        // use same decimals as base token
        uint8 decimals = IERC20(_baseToken).isETH() ? 18 : ERC20UpgradeSafe(_baseToken).decimals();
        _setupDecimals(decimals);
    }

    /**
     * Deposit base tokens
     *
     * Vault uses deposit to buy options and lp tokens in proportion with pool share
     */
    function deposit(uint256 sharesOut, uint256 maxAmountIn) external payable nonReentrant returns (uint256 amountIn) {
        require(sharesOut > 0, "Shares out must be > 0");
        require(!isPaused, "Paused");

        baseToken.uniTransferFromSenderToThis(maxAmountIn);

        // calculate proportional base amount
        amountIn = _calcAmountFromShares(baseToken, sharesOut, maxAmountIn, true);

        // calculate cost of proportional options and lp shares
        uint256 balanceBefore = baseToken.uniBalanceOf(address(this));
        OptionMarket[] memory _markets = markets;
        for (uint256 i = 0; i < _markets.length; i++) {
            (
                uint256[] memory longOptionsOut,
                uint256[] memory shortOptionsOut,
                uint256 lpSharesOut
            ) = _calcOptionsAndLpAmounts(_markets[i], sharesOut, true);
            _buyInternal(_markets[i], longOptionsOut, shortOptionsOut, lpSharesOut);
        }

        uint256 balanceAfter = baseToken.uniBalanceOf(address(this));
        amountIn = amountIn.add(balanceBefore.sub(balanceAfter));
        require(amountIn <= maxAmountIn, "Max slippage exceeded");

        _mint(msg.sender, sharesOut);
        require(totalSupplyCap == 0 || totalSupply() <= totalSupplyCap, "Total supply cap exceeded");

        // refund unused amount back to sender
        baseToken.uniTransfer(msg.sender, maxAmountIn.sub(amountIn));
    }

    /**
     * Withdraw base tokens
     *
     * Vault sells options and lp tokens in proportion with pool share
     */
    function withdraw(uint256 sharesIn, uint256 minAmountOut) external nonReentrant returns (uint256 amountOut) {
        require(sharesIn > 0, "Shares in must be > 0");
        require(!isPaused, "Paused");

        // calculate proportional base amount
        amountOut = _calcAmountFromShares(baseToken, sharesIn, 0, false);
        uint256 balanceBefore = baseToken.uniBalanceOf(address(this));

        // calculate cost of proportional options and lp shares
        OptionMarket[] memory _markets = markets;
        for (uint256 i = 0; i < _markets.length; i++) {
            (
                uint256[] memory longOptionsIn,
                uint256[] memory shortOptionsIn,
                uint256 lpSharesIn
            ) = _calcOptionsAndLpAmounts(_markets[i], sharesIn, false);
            _sellInternal(_markets[i], longOptionsIn, shortOptionsIn, lpSharesIn);
        }

        uint256 balanceAfter = baseToken.uniBalanceOf(address(this));
        amountOut = amountOut.add(balanceAfter.sub(balanceBefore));
        require(amountOut >= minAmountOut, "Max slippage exceeded");

        _burn(msg.sender, sharesIn);
        baseToken.uniTransfer(msg.sender, amountOut);
    }

    /**
     * Convert vault's base tokens to options and lp tokens
     *
     * The total value of assets held by vault should stay the same. Can only be called by strategy
     */
    function buy(
        OptionMarket market,
        uint256[] memory longOptionsOut,
        uint256[] memory shortOptionsOut,
        uint256 lpSharesOut,
        uint256 maxAmountIn
    ) external nonReentrant returns (uint256 amountIn) {
        require(msg.sender == strategy, "!strategy");
        require(marketAdded[market], "Market not found");

        uint256 balanceBefore = baseToken.uniBalanceOf(address(this));
        _buyInternal(market, longOptionsOut, shortOptionsOut, lpSharesOut);

        uint256 balanceAfter = baseToken.uniBalanceOf(address(this));
        amountIn = balanceBefore.sub(balanceAfter);
        require(amountIn <= maxAmountIn, "Max slippage exceeded");
    }

    /**
     * Convert vault's options and lp tokens back to base tokens
     *
     * The total value of assets held by vault should stay the same. Can only be called by strategy
     */
    function sell(
        OptionMarket market,
        uint256[] memory longOptionsIn,
        uint256[] memory shortOptionsIn,
        uint256 lpSharesIn,
        uint256 minAmountOut
    ) public nonReentrant returns (uint256 amountOut) {
        require(msg.sender == strategy, "!strategy");
        require(marketAdded[market], "Market not found");

        uint256 balanceBefore = baseToken.uniBalanceOf(address(this));
        _sellInternal(market, longOptionsIn, shortOptionsIn, lpSharesIn);

        uint256 balanceAfter = baseToken.uniBalanceOf(address(this));
        amountOut = balanceAfter.sub(balanceBefore);
        require(amountOut >= minAmountOut, "Max slippage exceeded");
    }

    function sellAll(OptionMarket market, uint256 minAmountOut) external returns (uint256) {
        require(msg.sender == strategy, "!strategy");
        require(marketAdded[market], "Market not found");

        (
            uint256[] memory longOptionsIn,
            uint256[] memory shortOptionsIn,
            uint256 lpSharesIn
        ) = _calcOptionsAndLpAmounts(market, totalSupply(), false);
        return sell(market, longOptionsIn, shortOptionsIn, lpSharesIn, minAmountOut);
    }

    function _buyInternal(
        OptionMarket market,
        uint256[] memory longOptionsIn,
        uint256[] memory shortOptionsIn,
        uint256 lpSharesOut
    ) internal {
        uint256 n = market.numStrikes();
        require(longOptionsIn.length == n, "Lengths don't match");
        require(shortOptionsIn.length == n, "Lengths don't match");

        if (lpSharesOut > 0) {
            uint256 maxAmountIn = baseToken.uniBalanceOf(address(this));
            uint256 value = baseToken.isETH() ? maxAmountIn : 0;
            market.deposit{value: value}(lpSharesOut, maxAmountIn);
        }

        for (uint256 i = 0; i < n; i++) {
            if (longOptionsIn[i] > 0) {
                uint256 maxAmountIn = baseToken.uniBalanceOf(address(this));
                uint256 value = baseToken.isETH() ? maxAmountIn : 0;
                market.buy{value: value}(true, i, longOptionsIn[i], maxAmountIn);
            }
            if (shortOptionsIn[i] > 0) {
                uint256 maxAmountIn = baseToken.uniBalanceOf(address(this));
                uint256 value = baseToken.isETH() ? maxAmountIn : 0;
                market.buy{value: value}(false, i, shortOptionsIn[i], maxAmountIn);
            }
        }
    }

    function _sellInternal(
        OptionMarket market,
        uint256[] memory longOptionsOut,
        uint256[] memory shortOptionsOut,
        uint256 lpSharesIn
    ) internal {
        uint256 n = market.numStrikes();
        require(longOptionsOut.length == n, "Lengths don't match");
        require(shortOptionsOut.length == n, "Lengths don't match");

        for (uint256 i = 0; i < n; i++) {
            if (longOptionsOut[i] > 0) {
                market.sell(true, i, longOptionsOut[i], 0);
            }
            if (shortOptionsOut[i] > 0) {
                market.sell(false, i, shortOptionsOut[i], 0);
            }
        }

        if (lpSharesIn > 0) {
            market.withdraw(lpSharesIn, 0);
        }
    }

    function _calcOptionsAndLpAmounts(
        OptionMarket market,
        uint256 sharesOut,
        bool roundUp
    )
        internal
        view
        returns (
            uint256[] memory longOptions,
            uint256[] memory shortOptions,
            uint256 lpShares
        )
    {
        uint256 n = market.numStrikes();
        longOptions = new uint256[](n);
        shortOptions = new uint256[](n);
        for (uint256 i = 0; i < n; i++) {
            longOptions[i] = _calcAmountFromShares(market.longTokens(i), sharesOut, 0, roundUp);
            shortOptions[i] = _calcAmountFromShares(market.shortTokens(i), sharesOut, 0, roundUp);
        }
        lpShares = _calcAmountFromShares(market, sharesOut, 0, roundUp);
    }

    function _calcAmountFromShares(
        IERC20 token,
        uint256 shares,
        uint256 balanceOffset,
        bool roundUp
    ) internal view returns (uint256) {
        uint256 _totalSupply = totalSupply();

        // first deposit is only base tokens and no options
        if (_totalSupply == 0) {
            return token == baseToken ? shares : 0;
        }

        uint256 balance = token.uniBalanceOf(address(this));

        // balance is often 0 for options so return early
        if (balance == 0) {
            return 0;
        }

        // amount = balance * shares / total supply
        // balanceOffset is used to subtract msg.value from balance
        uint256 numer = (balance.sub(balanceOffset)).mul(shares);
        if (numer > 0 && roundUp) {
            return numer.sub(1).div(_totalSupply).add(1);
        }
        return numer.div(_totalSupply);
    }

    /**
     * Get value of vault holdings if all options and lp tokens were sold back
     * into base tokens
     */
    function totalAssets() external view returns (uint256 assets) {
        OptionMarket[] memory _markets = markets;

        assets = baseToken.uniBalanceOf(address(this));
        for (uint256 i = 0; i < _markets.length; i++) {
            (
                uint256[] memory longOptionsIn,
                uint256[] memory shortOptionsIn,
                uint256 lpSharesIn
            ) = _calcOptionsAndLpAmounts(_markets[i], totalSupply(), false);
            assets = assets.add(optionViewsLibrary.getSellCost(_markets[i], longOptionsIn, shortOptionsIn, lpSharesIn));
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

        // preserve array order
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

        // should be true because of marketAdded check
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

    function setOptionViewsLibrary(address _optionViewsLibrary) external onlyOwner {
        optionViewsLibrary = OptionViews(_optionViewsLibrary);
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
