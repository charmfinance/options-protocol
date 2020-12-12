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
        uint256 indexed strikeIndex,
        bool isBuy,
        bool isLongToken,
        uint256 size,
        uint256 cost,
        uint256 newSupply
    );

    event Settled(uint256 settlementPrice);

    event Redeemed(address indexed account, uint256 amount);

    uint256 public constant SCALE = 1e18;
    uint256 public constant SCALE_SCALE = 1e36;

    IERC20 public baseToken;
    IOracle public oracle;
    OptionToken[] public longTokens;
    OptionToken[] public shortTokens;
    uint256[] public strikePrices;
    uint256 public expiryTime;
    uint256 public alpha;
    bool public isPut;
    uint256 public tradingFee;

    uint256 public maxStrikePrice;
    uint256 public numStrikes;
    bool public isPaused;
    bool public isSettled;
    uint256 public settlementPrice;
    uint256 public costAtSettlement;
    uint256 public payoffAtSettlement;

    // cache calcCost and calcPayoff to save gas
    uint256 public cost;
    uint256 public payoff;

    /**
     * @param _baseToken        Underlying ERC20 token. Represents ETH if equal to 0x0
     * @param _oracle           Oracle from which the settlement price is obtained
     * @param _longTokens       Long options
     * @param _shortTokens      Short options
     * @param _strikePrices     Strike prices expressed in wei
     * @param _alpha            Liquidity parameter for cost function expressed in wei
     * @param _expiryTime       Expiration time as a unix timestamp
     * @param _isPut            Whether long token represents a call or a put
     * @param _tradingFee       Trading fee expressed in wei
     */
    function initialize(
        address _baseToken,
        address _oracle,
        address[] memory _longTokens,
        address[] memory _shortTokens,
        uint256[] memory _strikePrices,
        uint256 _expiryTime,
        uint256 _alpha,
        bool _isPut,
        uint256 _tradingFee
    ) public initializer {
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

        require(_alpha > 0, "Alpha must be > 0");
        require(_alpha < SCALE, "Alpha must be < 1");
        require(_tradingFee < SCALE, "Trading fee must be < 1");

        baseToken = IERC20(_baseToken);
        oracle = IOracle(_oracle);
        strikePrices = _strikePrices;
        expiryTime = _expiryTime;
        alpha = _alpha;
        isPut = _isPut;
        tradingFee = _tradingFee;

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
        require(!isExpired(), "Already expired");
        require(!isPaused, "This method has been paused");
        require(strikeIndex < numStrikes, "Index too large");
        require(optionsOut > 0, "optionsOut must be > 0");

        uint256 costBefore = cost;
        OptionToken option = isLongToken ? longTokens[strikeIndex] : shortTokens[strikeIndex];
        option.mint(msg.sender, optionsOut);

        cost = calcCost();
        amountIn = cost.sub(costBefore);
        amountIn = amountIn.add(calcFee(optionsOut, strikeIndex));
        require(amountIn > 0, "Amount in must be > 0");
        require(amountIn <= maxAmountIn, "Max slippage exceeded");

        uint256 balanceBefore = baseToken.uniBalanceOf(address(this));
        baseToken.uniTransferFromSenderToThis(amountIn);
        uint256 balanceAfter = baseToken.uniBalanceOf(address(this));
        require(baseToken.isETH() || balanceAfter.sub(balanceBefore) == amountIn, "Deflationary tokens not supported");

        emit Trade(msg.sender, strikeIndex, true, isLongToken, optionsOut, amountIn, option.totalSupply());
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
        require(!isExpired(), "Already expired");
        require(!isPaused, "This method has been paused");
        require(strikeIndex < numStrikes, "Index too large");
        require(optionsIn > 0, "optionsIn must be > 0");

        uint256 costBefore = cost;
        OptionToken option = isLongToken ? longTokens[strikeIndex] : shortTokens[strikeIndex];
        option.burn(msg.sender, optionsIn);

        cost = calcCost();
        amountOut = costBefore.sub(cost);
        uint256 fee = calcFee(optionsIn, strikeIndex);
        require(amountOut > fee, "Amount out must be > 0");

        amountOut = amountOut.sub(fee);
        require(amountOut >= minAmountOut, "Max slippage exceeded");

        baseToken.uniTransfer(msg.sender, amountOut);

        emit Trade(msg.sender, strikeIndex, false, isLongToken, optionsIn, amountOut, option.totalSupply());
    }

    /**
     * Retrieves and stores the settlement price from the oracle
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
        settlementPrice = oracle.getPrice();
        require(settlementPrice > 0, "Price from oracle must be > 0");

        costAtSettlement = calcCost();
        payoffAtSettlement = calcPayoff();
        payoff = payoffAtSettlement;
        emit Settled(settlementPrice);
    }

    /**
     * Called by a user to redeem all their options and receive payout
     *
     * This method can only be called after `settle` has been called and the
     * settlement price has been set
     */
    function redeem() external nonReentrant returns (uint256 amount) {
        require(isExpired(), "Cannot be called before expiry");
        require(isSettled, "Cannot be called before settlement");
        require(!isPaused, "This method has been paused");

        uint256 payoffBefore = payoff;
        for (uint256 i = 0; i < numStrikes; i++) {
            uint256 longBalance = longTokens[i].balanceOf(msg.sender);
            uint256 shortBalance = shortTokens[i].balanceOf(msg.sender);
            if (longBalance > 0) {
                longTokens[i].burn(msg.sender, longBalance);
            }
            if (shortBalance > 0) {
                shortTokens[i].burn(msg.sender, shortBalance);
            }
        }

        // loses accuracy but otherwise might overflow
        payoff = calcPayoff();
        amount = payoffBefore.sub(payoff);
        amount = amount.mul(costAtSettlement).div(payoffAtSettlement);
        baseToken.uniTransfer(msg.sender, amount);
        emit Redeemed(msg.sender, amount);
    }

    /**
     * Calculates the LS-LMSR cost function (Othman et al., 2013)
     *
     *   C(q_1, ..., q_n) = b * log(exp(q_1 / b) + ... + exp(q_n / b))
     *
     * where
     *
     *   q_i = total supply of ith spread
     *   b = alpha * (q_1 + ... + q_n)
     *   alpha = LS-LMSR constant that determines liquidity sensitivity
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
        uint256 sum = s;

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
            sum = sum.add(s);
        }

        // if no options bought yet
        if (sum == 0) {
            return 0;
        }

        uint256 b = sum.mul(alpha);
        int128 sumExp;
        for (uint256 i = 0; i < q.length; i++) {
            // max(q) - q_i
            uint256 diff = max.sub(q[i]);

            // (max(q) - q_i) / b
            int128 div = ABDKMath64x64.divu(diff.mul(SCALE), b);

            // exp((q_i - max(q)) / b)
            int128 exp = ABDKMath64x64.exp(ABDKMath64x64.neg(div));
            sumExp = ABDKMath64x64.add(sumExp, exp);
        }

        // log(sumExp)
        int128 log = ABDKMath64x64.ln(sumExp);

        // b * log(sumExp) + max(q)
        uint256 cost = ABDKMath64x64.mulu(log, b).add(max.mul(SCALE));
        return isPut ? cost.mul(maxStrikePrice).div(SCALE_SCALE) : cost.div(SCALE);
    }

    /**
     * Calculates amount of `baseToken` that needs to be paid out to all users
     */
    function calcPayoff() public view returns (uint256 payoff) {
        for (uint256 i = 0; i < numStrikes; i++) {
            uint256 strikePrice = strikePrices[i];
            uint256 longSupply = longTokens[i].totalSupply();
            uint256 shortSupply = shortTokens[i].totalSupply();

            uint256 diff;
            if (isPut && settlementPrice < strikePrice) {
                // put payoff = max(K - S, 0)
                diff = strikePrice.sub(settlementPrice);
            } else if (!isPut && settlementPrice > strikePrice) {
                // call payoff = max(S - K, 0)
                diff = settlementPrice.sub(strikePrice);
            }
            payoff = payoff.add(longSupply.mul(diff));

            // short payoff = min(S, K)
            payoff = payoff.add(shortSupply.mul(Math.min(settlementPrice, strikePrice)));
        }

        // loses accuracy but otherwise might overflow in redeem()
        payoff = payoff.div(SCALE);
    }

    function calcFee(uint256 amount, uint256 strikeIndex) public view returns (uint256) {
        uint256 fee = amount.mul(tradingFee);
        return isPut ? fee.mul(strikePrices[strikeIndex]).div(SCALE_SCALE) : fee.div(SCALE);
    }

    function isExpired() public view returns (bool) {
        return block.timestamp >= expiryTime;
    }

    function skim() public nonReentrant onlyOwner returns (uint256 amount) {
        uint256 balanceBefore = baseToken.uniBalanceOf(address(this));
        uint256 balanceAfter = isSettled ? calcPayoff() : calcCost();
        amount = balanceBefore.sub(balanceAfter);
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
    function forceSettle() external onlyOwner {
        isSettled = false;
        settle();
    }
}
