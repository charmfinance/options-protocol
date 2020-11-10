// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;

import "@openzeppelin/contracts/math/Math.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

import "./libraries/ABDKMath64x64.sol";
import "./libraries/UniERC20.sol";
import "./libraries/openzeppelin/ERC20UpgradeSafe.sol";
import "./libraries/openzeppelin/OwnableUpgradeSafe.sol";
import "./libraries/openzeppelin/ReentrancyGuardUpgradeSafe.sol";
import "../interfaces/IOracle.sol";
import "./OptionsToken.sol";

contract OptionsMarketMaker is ReentrancyGuardUpgradeSafe, OwnableUpgradeSafe {
    using Address for address;
    using SafeERC20 for IERC20;
    using UniERC20 for IERC20;
    using SafeMath for uint256;

    event Trade(
        address indexed account,
        bool isBuy,
        uint256 longShares,
        uint256 shortShares,
        uint256 cost,
        uint256 newLongSupply,
        uint256 newShortSupply
    );

    event Settled(uint256 settlementPrice);

    event Redeemed(address indexed account, uint256 longSharesIn, uint256 shortSharesIn, uint256 amountOut);

    uint256 public constant SCALE = 1e18;
    uint256 public constant SCALE_SQ = 1e36;

    OptionsToken public longToken;
    OptionsToken public shortToken;
    IERC20 public baseToken;
    IOracle public oracle;
    bool public isPutMarket;
    uint256 public strikePrice;
    uint256 public normalizedStrikePrice;
    uint256 public alpha;
    uint256 public expiryTime;

    bool public isPaused;
    bool public isSettled;
    uint256 public settlementPrice;
    uint256 public normalizedSettlementPrice;

    /**
     * Automated market maker that lets users buy and sell options from it
     *
     * Creates a long token representing a call/put option and a short token
     * representing a covered call option.
     *
     * This contract is used for for both call and put options since they are inverses
     * of each other. For example a ETH/USD call option with a strike of 100 is
     * equivalent to a USD/ETH put option with a strike of 0.01. So for put options
     * we use the reciprocals of the strike price and settlement price and also
     * multiply the cost by the strike price so that underlying is in terms of
     * ETH, not USD.
     *
     * In this first version, the owner is highly privileged and is able to pause
     * the contract and override some of the initial parameters. These permissions
     * will be removed in the future.
     *
     * @param _baseToken        Underlying ERC20 asset. Represents ETH if equal to 0x0
     * @param _oracle           Oracle from which the settlement price is obtained
     * @param _isPutMarket      Whether long token represents a call or a put
     * @param _strikePrice      Strike price expressed in wei
     * @param _alpha            Liquidity parameter for cost function expressed in wei
     * @param _expiryTime       Expiration time as a unix timestamp
     */
    function initialize(
        address _baseToken,
        address _oracle,
        bool _isPutMarket,
        uint256 _strikePrice,
        uint256 _alpha,
        uint256 _expiryTime,
        address _longToken,
        address _shortToken
    ) public initializer {
        __ReentrancyGuard_init();
        __Ownable_init();

        require(_strikePrice > 0, "Strike price must be > 0");
        require(_alpha > 0, "Alpha must be > 0");

        longToken = OptionsToken(_longToken);
        shortToken = OptionsToken(_shortToken);
        baseToken = IERC20(_baseToken);
        oracle = IOracle(_oracle);
        isPutMarket = _isPutMarket;
        strikePrice = _strikePrice;
        normalizedStrikePrice = invertIfPut(_strikePrice);
        alpha = _alpha;
        expiryTime = _expiryTime;

        require(!isExpired(), "Already expired");
    }

    /**
     * Buy `longSharesOut` quantity of calls/puts and `shortSharesOut` quantity
     * of covered calls
     *
     * Revert if the resulting cost would be greater than `maxAmountIn`
     *
     * This method cannot be called after expiration
     */
    function buy(
        uint256 longSharesOut,
        uint256 shortSharesOut,
        uint256 maxAmountIn
    ) external payable nonReentrant returns (uint256 amountIn) {
        require(!isExpired(), "Cannot be called after expiry");
        require(!isPaused, "This method has been paused");
        require(longSharesOut > 0 || shortSharesOut > 0, "Shares out must be > 0");

        uint256 cost1 = cost();
        if (longSharesOut > 0) {
            longToken.mint(msg.sender, longSharesOut);
        }
        if (shortSharesOut > 0) {
            shortToken.mint(msg.sender, shortSharesOut);
        }
        uint256 cost2 = cost();
        amountIn = cost2.sub(cost1);
        require(amountIn > 0, "Amount in must be > 0");
        require(amountIn <= maxAmountIn, "Max slippage exceeded");

        uint256 balance1 = baseToken.uniBalanceOf(address(this));
        baseToken.uniTransferFromSenderToThis(amountIn);
        uint256 balance2 = baseToken.uniBalanceOf(address(this));
        require(baseToken.isETH() || balance2.sub(balance1) == amountIn, "Deflationary tokens not supported");

        emit Trade(
            msg.sender,
            true,
            longSharesOut,
            shortSharesOut,
            amountIn,
            longToken.totalSupply(),
            shortToken.totalSupply()
        );
    }

    /**
     * Sell `longSharesIn` quantity of calls/puts and `shortSharesIn` quantity
     * of covered calls
     *
     * Revert if the tokens received would be less than `minAmountOut`
     *
     * This method cannot be called after expiration
     */
    function sell(
        uint256 longSharesIn,
        uint256 shortSharesIn,
        uint256 minAmountOut
    ) external nonReentrant returns (uint256 amountOut) {
        require(!isExpired(), "Cannot be called after expiry");
        require(!isPaused, "This method has been paused");
        require(longSharesIn > 0 || shortSharesIn > 0, "Shares must be > 0");

        uint256 cost1 = cost();
        if (longSharesIn > 0) {
            longToken.burn(msg.sender, longSharesIn);
        }
        if (shortSharesIn > 0) {
            shortToken.burn(msg.sender, shortSharesIn);
        }
        uint256 cost2 = cost();
        amountOut = cost1.sub(cost2);
        require(amountOut > 0, "Amount must be > 0");
        require(amountOut >= minAmountOut, "Max slippage exceeded");

        baseToken.uniTransfer(msg.sender, amountOut);

        emit Trade(
            msg.sender,
            false,
            longSharesIn,
            shortSharesIn,
            amountOut,
            longToken.totalSupply(),
            shortToken.totalSupply()
        );
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

        normalizedSettlementPrice = invertIfPut(settlementPrice);
        emit Settled(settlementPrice);
    }

    /**
     * Redeem all options and receive payout
     *
     * This method can only be called after `settle` has been called and the
     * settlement price has been set
     */
    function redeem() external nonReentrant returns (uint256 amountOut) {
        require(isExpired(), "Cannot be called before expiry");
        require(isSettled, "Cannot be called before settlement");
        require(!isPaused, "This method has been paused");

        uint256 longBalance = longToken.balanceOf(msg.sender);
        uint256 shortBalance = shortToken.balanceOf(msg.sender);
        require(longBalance > 0 || shortBalance > 0, "Balance must be > 0");

        // payoffs are rounded down so rounding errors would never cause this
        // contract to run out of tokens to pay out users
        amountOut = calcPayoff(longBalance, shortBalance);
        require(amountOut > 0, "Amount must be > 0");

        if (longBalance > 0) {
            longToken.burn(msg.sender, longBalance);
        }

        if (shortBalance > 0) {
            shortToken.burn(msg.sender, shortBalance);
        }

        baseToken.uniTransfer(msg.sender, amountOut);

        emit Redeemed(msg.sender, longBalance, shortBalance, amountOut);
    }

    function isExpired() public view returns (bool) {
        return block.timestamp >= expiryTime;
    }

    // invert the strike price and settlement price for put options
    function invertIfPut(uint256 x) public view returns (uint256) {
        return isPutMarket ? SCALE_SQ.div(x) : x;
    }

    /**
     * Calculate cost function
     *
     * This represents the amount of base tokens that should be held by this
     * contract based on the total supply of long and short tokens.
     */
    function cost() public view returns (uint256) {
        uint256 lsLmsrCost = calcLsLmsrCost(longToken.totalSupply(), shortToken.totalSupply(), alpha);

        // multiply by the strike price for puts
        return isPutMarket ? lsLmsrCost.mul(strikePrice).div(SCALE_SQ) : lsLmsrCost.div(SCALE);
    }

    /**
     * Calculates amount of base tokens paid out to a user who redeems
     * `longShares` amount of calls/puts and `shortShares` amount of covered calls.
     *
     *   payoff = B * (`longShares` * p1 + `shortShares` * p2) / (q1 * p1 + q2 * p2)
     *
     * where
     *
     *   q1 = Long tokens outstanding
     *   q2 = Short tokens outstanding
     *   B = Underlying token balance held by this contract
     *   K = Strike price
     *   S = Settlement price
     *   p1 = max(S - K, 0)
     *   p2 = min(S, K)
     */
    function calcPayoff(uint256 longShares, uint256 shortShares) public view returns (uint256) {
        require(isSettled, "Cannot be called before settlement");

        // p1 = max(S - K, 0)
        uint256 payoffPerLong = normalizedSettlementPrice > normalizedStrikePrice
            ? normalizedSettlementPrice.sub(normalizedStrikePrice)
            : 0;

        // p2 = min(S, K)
        uint256 payoffPerShort = Math.min(normalizedSettlementPrice, normalizedStrikePrice);

        // `longShares` * p1
        uint256 longPayoff = longShares.mul(payoffPerLong);

        // `shortShares` * p2
        uint256 shortPayoff = shortShares.mul(payoffPerShort);

        // numer = B * (`longShares` * p1 + `shortShares` * p2)
        uint256 balance = baseToken.uniBalanceOf(address(this));
        uint256 numer = balance.mul(longPayoff.add(shortPayoff));

        // denom = q1 * p1 + q2 * p2
        uint256 totalLongPayoff = payoffPerLong.mul(longToken.totalSupply());
        uint256 totalShortPayoff = payoffPerShort.mul(shortToken.totalSupply());
        uint256 denom = totalLongPayoff.add(totalShortPayoff);

        // denom is proportional to total payoff of shares held by everyone
        // so if it's 0, payoff to any user must be 0
        if (denom == 0) {
            return 0;
        }

        return numer.div(denom);
    }

    /**
     * Calculates the LS-LMSR cost function (Othman et al., 2013)
     *
     *   C(q1, q2) = b * log(exp(q1 / b) + exp(q2 / b))
     *
     * where
     *
     *   q1 = long token supply
     *   q2 = short token supply
     *   _alpha = LS-LMSR constant that determines liquidity sensitivity
     *   b = _alpha * (q1 + q2)
     *
     * An equivalent expression for C(q1, q2) is used to avoid overflow when
     * calculating exponentials
     *
     *   C(q1, q2) = b * log(1 + exp(abs(q1 - q2) / b)) + max(q1, q2)
     *
     * Answer is multiplied by `SCALE`
     */
    function calcLsLmsrCost(
        uint256 q1,
        uint256 q2,
        uint256 _alpha
    ) public pure returns (uint256) {
        // b = _alpha * (q1 + q2)
        uint256 b = q1.add(q2).mul(_alpha);

        // if b is 0 then q1 and q2 must be 0 so the AMM is in its initial state
        if (b == 0) {
            return 0;
        }

        // max(q1, q2)
        uint256 max = Math.max(q1, q2);

        // abs(q1 - q2)
        uint256 diff = max.sub(Math.min(q1, q2));

        // abs(q1 - q2) / b
        int128 div = ABDKMath64x64.divu(diff.mul(SCALE), b);

        // exp(abs(q1 - q2) / b)
        int128 exp = ABDKMath64x64.exp(ABDKMath64x64.neg(div));

        // log(1 + exp(abs(q1 - q2) / b))
        int128 log = ABDKMath64x64.ln(ABDKMath64x64.add(exp, 1 << 64));

        // b * log(1 + exp(abs(q1 - q2) / b)) + max(q1, q2)
        return ABDKMath64x64.mulu(log, b).add(max.mul(SCALE));
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
