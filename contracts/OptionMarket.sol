// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;

import "@openzeppelin/contracts/math/Math.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/utils/Address.sol";

import "./libraries/ABDKMath64x64.sol";
import "./libraries/UniERC20.sol";
import "./libraries/openzeppelin/OwnableUpgradeSafe.sol";
import "./libraries/openzeppelin/ReentrancyGuardUpgradeSafe.sol";
import "../interfaces/IOracle.sol";
import "./OptionToken.sol";

/**
 * Automated market maker that lets users buy and sell options from it
 */
contract OptionMarket is ReentrancyGuardUpgradeSafe, OwnableUpgradeSafe {
    using Address for address;
    using SafeERC20 for IERC20;
    using UniERC20 for IERC20;
    using SafeMath for uint256;

    event Trade(
        address indexed account,
        bool isBuy,
        bool isLongToken,
        uint256 strikeIndex,
        uint256 size,
        uint256 cost,
        uint256 newSupply
    );

    event Settled(uint256 expiryPrice);

    event Redeemed(address indexed account, bool isLongToken, uint256 strikeIndex, uint256 amount);

    uint256 public constant SCALE = 1e18;
    uint256 public constant SCALE_SCALE = 1e36;
    uint256 public constant DISPUTE_PERIOD = 1 hours;

    IERC20 public baseToken;
    IOracle public oracle;
    OptionToken[] public longTokens;
    OptionToken[] public shortTokens;
    uint256[] public strikePrices;
    uint256 public expiryTime;
    uint256 public b;
    bool public isPut;
    uint256 public tradingFee;
    uint256 public balanceLimit;

    uint256 public maxStrikePrice;
    uint256 public numStrikes;
    bool public isPaused;
    bool public isSettled;
    uint256 public expiryPrice;

    // cache calcCost and calcPayoff to save gas
    uint256 public lastCost;
    uint256 public lastPayoff;

    /**
     * @param _baseToken        Underlying ERC20 token. Represents ETH if equal to 0x0
     * @param _oracle           Oracle from which the settlement price is obtained
     * @param _longTokens       Options tokens representing long calls/puts
     * @param _shortTokens      Options tokens representing short calls/puts
     * @param _strikePrices     Strike prices expressed in wei
     * @param _expiryTime       Expiration time as a unix timestamp
     * @param _isPut            Whether options are calls or puts
     * @param _tradingFee       Trading fee expressed in wei
     * @param _balanceLimit     Limit on balance in contract. Used for guarded launch. Set to 0 means no limit
     */
    function initialize(
        address _baseToken,
        address _oracle,
        address[] memory _longTokens,
        address[] memory _shortTokens,
        uint256[] memory _strikePrices,
        uint256 _expiryTime,
        bool _isPut,
        uint256 _tradingFee,
        uint256 _balanceLimit
    ) public payable initializer {
        __ReentrancyGuard_init();
        __Ownable_init();

        require(_longTokens.length == _strikePrices.length, "Lengths do not match");
        require(_shortTokens.length == _strikePrices.length, "Lengths do not match");

        require(_strikePrices.length > 0, "Strike prices must not be empty");
        require(_strikePrices[0] > 0, "Strike prices must be > 0");

        // check strike prices are in increasing order
        for (uint256 i = 0; i < _strikePrices.length - 1; i++) {
            require(_strikePrices[i] < _strikePrices[i + 1], "Strike prices must be increasing");
        }

        require(_tradingFee < SCALE, "Trading fee must be < 1");

        baseToken = IERC20(_baseToken);
        oracle = IOracle(_oracle);
        strikePrices = _strikePrices;
        expiryTime = _expiryTime;
        isPut = _isPut;
        tradingFee = _tradingFee;
        balanceLimit = _balanceLimit;

        for (uint256 i = 0; i < _longTokens.length; i++) {
            longTokens.push(OptionToken(_longTokens[i]));
        }

        for (uint256 i = 0; i < _shortTokens.length; i++) {
            shortTokens.push(OptionToken(_shortTokens[i]));
        }

        maxStrikePrice = _strikePrices[_strikePrices.length - 1];
        numStrikes = _strikePrices.length;

        require(!isExpired(), "Already expired");
    }

    /**
     * Buy `optionsOut` quantity of options
     *
     * Revert if the resulting cost would be greater than `maxAmountIn`
     *
     * This method cannot be called after expiration
     */
    function buy(
        bool isLongToken,
        uint256 strikeIndex,
        uint256 optionsOut,
        uint256 maxAmountIn
    ) external payable nonReentrant returns (uint256 amountIn) {
        require(b > 0, "Cannot be called before b is set");
        require(!isExpired(), "Already expired");
        require(!isPaused, "This method has been paused");
        require(strikeIndex < numStrikes, "Index too large");
        require(optionsOut > 0, "optionsOut must be > 0");

        uint256 costBefore = lastCost;
        OptionToken option = isLongToken ? longTokens[strikeIndex] : shortTokens[strikeIndex];
        option.mint(msg.sender, optionsOut);

        lastCost = calcCost();
        amountIn = lastCost.sub(costBefore);
        require(amountIn > 0, "Amount in must be > 0");

        uint256 fee = optionsOut.mul(tradingFee);
        fee = isPut ? fee.mul(strikePrices[strikeIndex]).div(SCALE_SCALE) : fee.div(SCALE);
        amountIn = amountIn.add(fee);
        require(amountIn <= maxAmountIn, "Max slippage exceeded");

        uint256 balanceBefore = baseToken.uniBalanceOf(address(this));
        baseToken.uniTransferFromSenderToThis(amountIn);
        uint256 balanceAfter = baseToken.uniBalanceOf(address(this));
        require(baseToken.isETH() || balanceAfter.sub(balanceBefore) == amountIn, "Deflationary tokens not supported");

        if (balanceLimit > 0) {
            require(baseToken.uniBalanceOf(address(this)) <= balanceLimit, "Balance limit exceeded");
        }

        emit Trade(msg.sender, true, isLongToken, strikeIndex, optionsOut, amountIn, option.totalSupply());
    }

    /**
     * Sell `optionsIn` quantity of options
     *
     * Revert if the resulting cost would be greater than `minAmountOut`
     *
     * This method cannot be called after expiration
     */
    function sell(
        bool isLongToken,
        uint256 strikeIndex,
        uint256 optionsIn,
        uint256 minAmountOut
    ) external nonReentrant returns (uint256 amountOut) {
        require(b > 0, "Cannot be called before b is set");
        require(!isExpired(), "Already expired");
        require(!isPaused, "This method has been paused");
        require(strikeIndex < numStrikes, "Index too large");
        require(optionsIn > 0, "optionsIn must be > 0");

        uint256 costBefore = lastCost;
        OptionToken option = isLongToken ? longTokens[strikeIndex] : shortTokens[strikeIndex];
        option.burn(msg.sender, optionsIn);

        lastCost = calcCost();
        amountOut = costBefore.sub(lastCost);
        require(amountOut > 0, "Amount out must be > 0");
        require(amountOut >= minAmountOut, "Max slippage exceeded");

        baseToken.uniTransfer(msg.sender, amountOut);
        emit Trade(msg.sender, false, isLongToken, strikeIndex, optionsIn, amountOut, option.totalSupply());
    }

    /**
     * Retrieves and stores the unerlying price from the oracle
     *
     * This method can be called by anyone after expiration and cannot be called
     * more than once.
     *
     * After this method has been called, `redeem` can be called by users to
     * trade in their options and receive their payouts
     */
    function settle() public nonReentrant {
        require(isExpired(), "Cannot be called before expiry");
        require(!isSettled, "Already settled");

        isSettled = true;
        expiryPrice = oracle.getPrice();
        require(expiryPrice > 0, "Price from oracle must be > 0");

        lastPayoff = calcPayoff();
        emit Settled(expiryPrice);
    }

    /**
     * Called by a user to redeem all their options and receive payout
     *
     * This method can only be called after `settle` has been called and the
     * settlement price has been set
     */
    function redeem(bool isLongToken, uint256 strikeIndex) external nonReentrant returns (uint256 amount) {
        require(isExpired(), "Cannot be called before expiry");
        require(isSettled, "Cannot be called before settlement");
        require(!isDisputePeriod(), "Cannot be called during dispute period");
        require(!isPaused, "This method has been paused");
        require(strikeIndex < numStrikes, "Index too large");

        OptionToken option = isLongToken ? longTokens[strikeIndex] : shortTokens[strikeIndex];
        uint256 balance = option.balanceOf(msg.sender);
        require(balance > 0, "Balance must be > 0");

        uint256 payoffBefore = lastPayoff;
        option.burn(msg.sender, balance);
        lastPayoff = calcPayoff();
        amount = payoffBefore.sub(lastPayoff);

        baseToken.uniTransfer(msg.sender, amount);
        emit Redeemed(msg.sender, isLongToken, strikeIndex, amount);
    }

    /**
     * Calculates the LMSR cost function
     *
     *   C(q_1, ..., q_n) = b * log(exp(q_1 / b) + ... + exp(q_n / b))
     *
     * where
     *
     *   q_i = total supply of ith spread
     *   b = liquidity parameter
     *
     * An equivalent expression for C is used to avoid overflow when
     * calculating exponentials
     *
     *   C(q_1, ..., q_n) = m + b * log(exp((q_1 - m) / b) + ... + exp((q_n - m) / b))
     *
     * where
     *
     *   m = max(q_1, ..., q_n)
     *
     * Answer is multiplied by strike price for puts
     */
    function calcCost() public view returns (uint256) {
        if (b == 0) {
            return 0;
        }

        // initally set s to total supply of shortTokens
        uint256 s;
        for (uint256 i = 0; i < numStrikes; i++) {
            if (isPut) {
                s = s.add(longTokens[i].totalSupply());
            } else {
                s = s.add(shortTokens[i].totalSupply());
            }
        }

        uint256[] memory q = new uint256[](numStrikes + 1);
        q[0] = s;
        uint256 max = s;

        // set q[i] to be total supply of longTokens[:i] and shortTokens[i:]
        for (uint256 i = 0; i < numStrikes; i++) {
            if (isPut) {
                s = s.add(shortTokens[i].totalSupply());
                s = s.sub(longTokens[i].totalSupply());
            } else {
                s = s.add(longTokens[i].totalSupply());
                s = s.sub(shortTokens[i].totalSupply());
            }
            q[i + 1] = s;
            max = Math.max(max, s);
        }

        int128 sumExp;
        for (uint256 i = 0; i < q.length; i++) {
            // max(q) - q_i
            uint256 diff = max.sub(q[i]);

            // (max(q) - q_i) / b
            int128 div = ABDKMath64x64.divu(diff, b);

            // exp((q_i - max(q)) / b)
            int128 exp = ABDKMath64x64.exp(ABDKMath64x64.neg(div));
            sumExp = ABDKMath64x64.add(sumExp, exp);
        }

        // log(sumExp)
        int128 log = ABDKMath64x64.ln(sumExp);

        // b * log(sumExp) + max(q)
        uint256 cost = ABDKMath64x64.mulu(log, b).add(max);
        return isPut ? cost.mul(maxStrikePrice).div(SCALE) : cost;
    }

    /**
     * Calculates amount of `baseToken` that needs to be paid out to all users
     */
    function calcPayoff() public view returns (uint256 payoff) {
        if (expiryPrice == 0) {
            return 0;
        }
        for (uint256 i = 0; i < numStrikes; i++) {
            uint256 strikePrice = strikePrices[i];
            uint256 longSupply = longTokens[i].totalSupply();
            uint256 shortSupply = shortTokens[i].totalSupply();

            uint256 diff;
            if (isPut && expiryPrice < strikePrice) {
                // put payoff = max(K - S, 0)
                diff = strikePrice.sub(expiryPrice);
            } else if (!isPut && expiryPrice > strikePrice) {
                // call payoff = max(S - K, 0)
                diff = expiryPrice.sub(strikePrice);
            }
            payoff = payoff.add(longSupply.mul(diff));

            // short payoff = min(S, K)
            payoff = payoff.add(shortSupply.mul(Math.min(expiryPrice, strikePrice)));
        }

        if (isPut) {
            payoff = payoff.div(SCALE);
        } else {
            payoff = payoff.div(expiryPrice);
        }
    }

    function calcSkimAmount() public view returns (uint256) {
        if (!isSettled) {
            return 0;
        }
        uint256 balance = baseToken.uniBalanceOf(address(this));
        return balance.sub(calcPayoff());
    }

    function isExpired() public view returns (bool) {
        return block.timestamp >= expiryTime;
    }

    function isDisputePeriod() public view returns (bool) {
        return block.timestamp >= expiryTime && block.timestamp < expiryTime + DISPUTE_PERIOD;
    }

    function increaseBAndBuy(
        uint256 _b,
        uint256[] memory longOptionsOut,
        uint256[] memory shortOptionsOut,
        uint256 maxAmountIn
    ) external payable onlyOwner returns (uint256 amountIn) {
        require(_b > b, "New b must be higher");
        require(longOptionsOut.length == strikePrices.length, "Lengths do not match");
        require(shortOptionsOut.length == strikePrices.length, "Lengths do not match");

        uint256 costBefore = lastCost;
        b = _b;
        for (uint256 i = 0; i < strikePrices.length; i++) {
            if (longOptionsOut[i] > 0) {
                longTokens[i].mint(msg.sender, longOptionsOut[i]);
            }
            if (shortOptionsOut[i] > 0) {
                shortTokens[i].mint(msg.sender, shortOptionsOut[i]);
            }
        }
        lastCost = calcCost();
        amountIn = lastCost.sub(costBefore);
        require(amountIn > 0, "Amount in must be > 0");
        require(amountIn <= maxAmountIn, "Max slippage exceeded");

        uint256 balanceBefore = baseToken.uniBalanceOf(address(this));
        baseToken.uniTransferFromSenderToThis(amountIn);
        uint256 balanceAfter = baseToken.uniBalanceOf(address(this));
        require(baseToken.isETH() || balanceAfter.sub(balanceBefore) == amountIn, "Deflationary tokens not supported");

        if (balanceLimit > 0) {
            require(baseToken.uniBalanceOf(address(this)) <= balanceLimit, "Balance limit exceeded");
        }
    }

    function skim() external onlyOwner returns (uint256 amount) {
        require(isSettled, "Cannot be called before settlement");
        amount = calcSkimAmount();
        if (amount > 0) {
            baseToken.uniTransfer(msg.sender, amount);
        }
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
    function setOracle(IOracle _oracle) external onlyOwner {
        oracle = _oracle;
    }

    // emergency use only. to be removed in future versions
    function setExpiryTime(uint256 _expiryTime) external onlyOwner {
        expiryTime = _expiryTime;
    }

    // emergency use only. to be removed in future versions
    function disputeExpiryPrice(uint256 _expiryPrice) external onlyOwner {
        require(isDisputePeriod(), "Not dispute period");
        require(isSettled, "Cannot be called before settlement");
        expiryPrice = _expiryPrice;
    }
}
