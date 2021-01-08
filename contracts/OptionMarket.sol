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

    event UpdatedB(uint256 b, uint256 cost);

    event Settled(uint256 expiryPrice);

    event Redeemed(address indexed account, bool isLongToken, uint256 strikeIndex, uint256 amount);

    uint256 public constant SCALE = 1e18;
    uint256 public constant SCALE_SCALE = 1e36;

    IERC20 public baseToken;
    IOracle public oracle;
    OptionToken[] public longTokens;
    OptionToken[] public shortTokens;
    uint256[] public strikePrices;
    uint256 public expiryTime;
    uint256 public b;
    bool public isPut;
    uint256 public tradingFee;
    uint256 public balanceCap;
    uint256 public disputePeriod;

    uint256 public numStrikes;
    bool public isPaused;
    bool public isSettled;
    uint256 public expiryPrice;

    // cache currentCumulativeCost and currentCumulativePayoff between trades/redeems to save gas
    // initial cost is 0, and initial payoff is set in settle()
    uint256 public lastCost;
    uint256 public lastPayoff;

    /**
     * @param _baseToken        Underlying ERC20 token. Represents ETH if equal to 0x0
     * @param _oracle           Oracle from which the settlement price is obtained
     * @param _longTokens       Options tokens representing long calls/puts
     * @param _shortTokens      Options tokens representing short calls/puts
     * @param _strikePrices     Strike prices expressed in wei. Must be in ascending order
     * @param _expiryTime       Expiration time as a unix timestamp
     * @param _isPut            Whether options are calls or puts
     * @param _tradingFee       Trading fee as fraction of notional expressed in wei
     * @param _balanceCap       Cap on total value locked in contract. Used for guarded launch. Set to 0 means no cap
     * @param _disputePeriod    How long after expiry the oracle price can be disputed by deployer
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
        uint256 _balanceCap,
        uint256 _disputePeriod
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
        balanceCap = _balanceCap;
        disputePeriod = _disputePeriod;

        numStrikes = _strikePrices.length;
        for (uint256 i = 0; i < numStrikes; i++) {
            longTokens.push(OptionToken(_longTokens[i]));
            shortTokens.push(OptionToken(_shortTokens[i]));
        }

        require(!isExpired(), "Already expired");
    }

    /**
     * Buy `optionsOut` quantity of options
     */
    function buy(
        bool isLongToken,
        uint256 strikeIndex,
        uint256 optionsOut,
        uint256 maxAmountIn
    ) external payable nonReentrant returns (uint256 amountIn) {
        require(b > 0, "Cannot be called before b is set");
        require(!isExpired(), "Already expired");
        require(msg.sender == owner() || !isPaused, "This method has been paused");
        require(strikeIndex < numStrikes, "Index too large");
        require(optionsOut > 0, "optionsOut must be > 0");

        // mint options for sender
        uint256 costBefore = lastCost;
        OptionToken option = isLongToken ? longTokens[strikeIndex] : shortTokens[strikeIndex];
        option.mint(msg.sender, optionsOut);

        // calculate amount to be paid
        lastCost = currentCumulativeCost();
        amountIn = lastCost.sub(costBefore);
        require(amountIn > 0, "Amount in must be > 0");

        // calculate trading fee
        uint256 fee = optionsOut.mul(tradingFee);
        fee = isPut ? fee.mul(strikePrices[strikeIndex]).div(SCALE_SCALE) : fee.div(SCALE);
        amountIn = amountIn.add(fee);
        require(amountIn <= maxAmountIn, "Max slippage exceeded");

        // transfer base tokens from sender
        uint256 balanceBefore = baseToken.uniBalanceOf(address(this));
        baseToken.uniTransferFromSenderToThis(amountIn);
        uint256 balanceAfter = baseToken.uniBalanceOf(address(this));
        require(baseToken.isETH() || balanceAfter.sub(balanceBefore) == amountIn, "Deflationary tokens not supported");
        require(balanceCap == 0 || baseToken.uniBalanceOf(address(this)) <= balanceCap, "Balance cap exceeded");
        emit Trade(msg.sender, true, isLongToken, strikeIndex, optionsOut, amountIn, option.totalSupply());
    }

    /**
     * Sell `optionsIn` quantity of options
     */
    function sell(
        bool isLongToken,
        uint256 strikeIndex,
        uint256 optionsIn,
        uint256 minAmountOut
    ) external nonReentrant returns (uint256 amountOut) {
        require(b > 0, "Cannot be called before b is set");
        require(!isExpired(), "Already expired");
        require(msg.sender == owner() || !isPaused, "This method has been paused");
        require(strikeIndex < numStrikes, "Index too large");
        require(optionsIn > 0, "optionsIn must be > 0");

        // burn sender's options
        uint256 costBefore = lastCost;
        OptionToken option = isLongToken ? longTokens[strikeIndex] : shortTokens[strikeIndex];
        option.burn(msg.sender, optionsIn);

        // calculate amount to be returned to sender
        lastCost = currentCumulativeCost();
        amountOut = costBefore.sub(lastCost);
        require(amountOut > 0, "Amount out must be > 0");
        require(amountOut >= minAmountOut, "Max slippage exceeded");

        // transfer base tokens to sender
        baseToken.uniTransfer(msg.sender, amountOut);
        emit Trade(msg.sender, false, isLongToken, strikeIndex, optionsIn, amountOut, option.totalSupply());
    }

    /**
     * At expiration, retrieve and store the underlying price from the oracle
     *
     * This method can be called by anyone but cannot be called more than once.
     */
    function settle() public nonReentrant {
        require(isExpired(), "Cannot be called before expiry");
        require(!isSettled, "Already settled");

        isSettled = true;
        expiryPrice = oracle.getPrice();
        require(expiryPrice > 0, "Price from oracle must be > 0");

        // set initial cached value of currentCumulativePayoff()
        lastPayoff = currentCumulativePayoff();
        emit Settled(expiryPrice);
    }

    /**
     * After expiration, exercise options by burning them and redeeming them for base tokens
     */
    function redeem(bool isLongToken, uint256 strikeIndex) external nonReentrant returns (uint256 amount) {
        require(isExpired(), "Cannot be called before expiry");
        require(isSettled, "Cannot be called before settlement");
        require(!isDisputePeriod(), "Cannot be called during dispute period");
        require(msg.sender == owner() || !isPaused, "This method has been paused");
        require(strikeIndex < numStrikes, "Index too large");

        // get sender's options balance
        OptionToken option = isLongToken ? longTokens[strikeIndex] : shortTokens[strikeIndex];
        uint256 balance = option.balanceOf(msg.sender);
        require(balance > 0, "Balance must be > 0");

        // burn sender's options
        uint256 payoffBefore = lastPayoff;
        option.burn(msg.sender, balance);

        // calculate amount to be returned to sender
        lastPayoff = currentCumulativePayoff();
        amount = payoffBefore.sub(lastPayoff);

        // transfer base tokens to sender
        baseToken.uniTransfer(msg.sender, amount);
        emit Redeemed(msg.sender, isLongToken, strikeIndex, amount);
    }

    function calcFeesAccrued() public view returns (uint256) {
        if (!isSettled) {
            return 0;
        }
        uint256 balance = baseToken.uniBalanceOf(address(this));
        return balance.sub(currentCumulativePayoff());
    }

    function isExpired() public view returns (bool) {
        return block.timestamp >= expiryTime;
    }

    function isDisputePeriod() public view returns (bool) {
        return block.timestamp >= expiryTime && block.timestamp < expiryTime + disputePeriod;
    }

    function currentCumulativeCost() public view returns (uint256) {
        return calcCumulativeCost(calcQuantities(getLongSupplies(), getShortSupplies()));
    }

    function currentCumulativePayoff() public view returns (uint256) {
        return calcCumulativePayoff(getLongSupplies(), getShortSupplies());
    }

    function getLongSupplies() public view returns (uint256[] memory totalSupplies) {
        totalSupplies = new uint256[](numStrikes);
        for (uint256 i = 0; i < numStrikes; i++) {
            totalSupplies[i] = longTokens[i].totalSupply();
        }
    }

    function getShortSupplies() public view returns (uint256[] memory totalSupplies) {
        totalSupplies = new uint256[](numStrikes);
        for (uint256 i = 0; i < numStrikes; i++) {
            totalSupplies[i] = shortTokens[i].totalSupply();
        }
    }

    function calcQuantities(uint256[] memory longSupplies, uint256[] memory shortSupplies)
        public
        view
        returns (uint256[] memory quantities)
    {
        // initally set runningSum to total supply of shortSupplies
        uint256 runningSum;
        for (uint256 i = 0; i < numStrikes; i++) {
            if (isPut) {
                runningSum = runningSum.add(longSupplies[i].mul(strikePrices[i]).div(SCALE));
            } else {
                runningSum = runningSum.add(shortSupplies[i]);
            }
        }

        quantities = new uint256[](numStrikes + 1);
        quantities[0] = runningSum;

        // set quantities[i] to be total supply of longSupplies[:i] and shortSupplies[i:]
        for (uint256 i = 0; i < numStrikes; i++) {
            if (isPut) {
                runningSum = runningSum.add(shortSupplies[i].mul(strikePrices[i]).div(SCALE));
                runningSum = runningSum.sub(longSupplies[i].mul(strikePrices[i]).div(SCALE));
            } else {
                runningSum = runningSum.add(longSupplies[i]);
                runningSum = runningSum.sub(shortSupplies[i]);
            }
            quantities[i + 1] = runningSum;
        }
        return quantities;
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
     */
    function calcCumulativeCost(uint256[] memory quantities) public view returns (uint256) {
        require(quantities.length == numStrikes + 1, "Lengths do not match");

        if (b == 0) {
            return 0;
        }

        uint256 maxQuantity = quantities[0];
        for (uint256 i = 1; i < quantities.length; i++) {
            maxQuantity = Math.max(maxQuantity, quantities[i]);
        }

        int128 sumExp;
        for (uint256 i = 0; i < quantities.length; i++) {
            // max(q) - q_i
            uint256 diff = maxQuantity.sub(quantities[i]);

            // (max(q) - q_i) / b
            int128 div = ABDKMath64x64.divu(diff, b);

            // exp((q_i - max(q)) / b)
            int128 exp = ABDKMath64x64.exp(ABDKMath64x64.neg(div));
            sumExp = ABDKMath64x64.add(sumExp, exp);
        }

        // log(sumExp)
        int128 log = ABDKMath64x64.ln(sumExp);

        // b * log(sumExp) + max(q)
        return ABDKMath64x64.mulu(log, b).add(maxQuantity);
    }

    /**
     * Calculates amount of base tokens that needs to be paid out to all users
     */
    function calcCumulativePayoff(uint256[] memory longSupplies, uint256[] memory shortSupplies)
        public
        view
        returns (uint256 payoff)
    {
        require(longSupplies.length == numStrikes, "Lengths do not match");
        require(shortSupplies.length == numStrikes, "Lengths do not match");

        if (expiryPrice == 0) {
            return 0;
        }

        for (uint256 i = 0; i < numStrikes; i++) {
            uint256 strikePrice = strikePrices[i];

            if (isPut && expiryPrice < strikePrice) {
                // put payoff = max(K - S, 0)
                payoff = payoff.add(longSupplies[i].mul(strikePrice.sub(expiryPrice)));
            } else if (!isPut && expiryPrice > strikePrice) {
                // call payoff = max(S - K, 0)
                payoff = payoff.add(longSupplies[i].mul(expiryPrice.sub(strikePrice)));
            }

            // short payoff = min(S, K)
            payoff = payoff.add(shortSupplies[i].mul(Math.min(expiryPrice, strikePrice)));
        }

        payoff = payoff.div(isPut ? SCALE : expiryPrice);
    }

    /**
     * Called by owner to increase the LMSR parameter `b` by depositing base tokens.
     *
     * `b` uses same decimals as baseToken
     */
    function increaseB(uint256 _b) external payable onlyOwner nonReentrant returns (uint256 amountIn) {
        require(_b > b, "New b must be higher");

        // increase b and calculate amount to be paid by owner
        uint256 costBefore = lastCost;
        b = _b;
        lastCost = currentCumulativeCost();
        amountIn = lastCost.sub(costBefore);
        require(amountIn > 0, "Amount in must be > 0");

        // transfer amount from owner
        uint256 balanceBefore = baseToken.uniBalanceOf(address(this));
        baseToken.uniTransferFromSenderToThis(amountIn);
        uint256 balanceAfter = baseToken.uniBalanceOf(address(this));
        require(baseToken.isETH() || balanceAfter.sub(balanceBefore) == amountIn, "Deflationary tokens not supported");
        require(balanceCap == 0 || baseToken.uniBalanceOf(address(this)) <= balanceCap, "Balance cap exceeded");
        emit UpdatedB(b, lastCost.sub(costBefore));
    }

    /**
     * Called by owner to withdraw accrued trading fees
     */
    function collectFees() external onlyOwner nonReentrant returns (uint256 amount) {
        require(isSettled, "Cannot be called before settlement");
        amount = calcFeesAccrued();
        if (amount > 0) {
            baseToken.uniTransfer(msg.sender, amount);
        }
    }

    function setBalanceCap(uint256 _balanceCap) external onlyOwner {
        balanceCap = _balanceCap;
    }

    /**
     * Convenience method to calculate cost of a buy trade
     */
    function calcBuyAmountAndFee(
        bool isLongToken,
        uint256 strikeIndex,
        uint256 optionsOut
    ) public view returns (uint256 cost, uint256 fee) {
        uint256[] memory longSupplies = getLongSupplies();
        uint256[] memory shortSupplies = getShortSupplies();
        uint256[] memory supplies = isLongToken ? longSupplies : shortSupplies;
        supplies[strikeIndex] = supplies[strikeIndex].add(optionsOut);
        cost = calcCumulativeCost(calcQuantities(longSupplies, shortSupplies)).sub(lastCost);

        fee = optionsOut.mul(tradingFee);
        fee = isPut ? fee.mul(strikePrices[strikeIndex]).div(SCALE_SCALE) : fee.div(SCALE);
    }

    /**
     * Convenience method to calculate amount returned from a sell trade
     *
     * Sell fee is 0, but still return it in case it's set in the future
     */
    function calcSellAmountAndFee(
        bool isLongToken,
        uint256 strikeIndex,
        uint256 optionsIn
    ) external view returns (uint256 cost, uint256) {
        uint256[] memory longSupplies = getLongSupplies();
        uint256[] memory shortSupplies = getShortSupplies();
        uint256[] memory supplies = isLongToken ? longSupplies : shortSupplies;
        supplies[strikeIndex] = supplies[strikeIndex].sub(optionsIn);
        cost = lastCost.sub(calcCumulativeCost(calcQuantities(longSupplies, shortSupplies)));
    }

    /**
     * Convenience method to calculate amount returned from redeeming options after settlement
     *
     * Settlement fee is 0, but still return it in case it's set in the future
     */
    function calcRedeemAmountAndFee(bool isLongToken, uint256 strikeIndex)
        external
        view
        returns (uint256 cost, uint256)
    {
        uint256[] memory longSupplies = getLongSupplies();
        uint256[] memory shortSupplies = getShortSupplies();
        uint256[] memory supplies = isLongToken ? longSupplies : shortSupplies;

        OptionToken option = isLongToken ? longTokens[strikeIndex] : shortTokens[strikeIndex];
        uint256 balance = option.balanceOf(msg.sender);

        supplies[strikeIndex] = supplies[strikeIndex].sub(balance);
        cost = lastPayoff.sub(calcCumulativePayoff(longSupplies, shortSupplies));
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
    function setDisputePeriod(uint256 _disputePeriod) external onlyOwner {
        disputePeriod = _disputePeriod;
    }

    // emergency use only. to be removed in future versions
    function disputeExpiryPrice(uint256 _expiryPrice) external onlyOwner {
        require(isDisputePeriod(), "Not dispute period");
        require(isSettled, "Cannot be called before settlement");
        expiryPrice = _expiryPrice;
    }
}
