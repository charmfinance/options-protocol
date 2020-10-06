// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/math/Math.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/utils/Address.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

import "../interfaces/IOracle.sol";
import "./libraries/ABDKMath64x64.sol";
import "./libraries/UniERC20.sol";
import "./OptionsToken.sol";
import "./Pausable.sol";

contract OptionsMarketMaker is ReentrancyGuard, Ownable, Pausable {
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

    IERC20 public baseToken;
    IOracle public oracle;
    OptionsToken public longToken;
    OptionsToken public shortToken;
    uint256 public strikePrice;
    uint256 public alpha;
    uint256 public expiryTime;
    uint256 public multiplier;

    bool public isSettled;
    uint256 public settlementPrice;

    /**
     * Automated market maker that lets users buy and sell options from it
     *
     * Creates {longToken} representing a call/put and {shortToken} representing
     * a covered call.
     *
     * @param _baseToken        Underlying ERC20 asset. Represents ETH if equal to 0x0
     * @param _oracle           {IOracle} with getPrice() method
     * @param _strikePrice      Strike price in wei
     * @param _alpha            Parameter for the LS-LMSR cost function in wei
     * @param _expiryTime       Expiration time as a unix timestamp
     * @param _multiplier       Index multiplier in wei
     * @param longName          Long token name
     * @param longSymbol        Long token symbol
     * @param shortName         Short token name
     * @param shortSymbol       Short token symbol
     */
    constructor(
        address _baseToken,
        address _oracle,
        uint256 _strikePrice,
        uint256 _alpha,
        uint256 _expiryTime,
        uint256 _multiplier,
        string memory longName,
        string memory longSymbol,
        string memory shortName,
        string memory shortSymbol
    ) public {
        require(_strikePrice > 0, "Strike price must be > 0");
        require(_alpha > 0, "Alpha must be > 0");
        require(_multiplier > 0, "Multiplier must be > 0");

        longToken = new OptionsToken(longName, longSymbol);
        shortToken = new OptionsToken(shortName, shortSymbol);

        baseToken = IERC20(_baseToken);
        oracle = IOracle(_oracle);
        strikePrice = _strikePrice;
        alpha = _alpha;
        expiryTime = _expiryTime;
        multiplier = _multiplier;

        require(!isExpired(), "Already expired");
    }

    /**
     * Buy `longSharesOut` quantity of {longToken} and `shortSharesOut` quantity
     * of {shortToken}
     *
     * Revert if the resulting cost would be greater than `maxAmountIn`
     *
     * `optionsToken` must be equal to {longToken} or {shortToken} and this
     * method can only be called before expiration
     */
    function buy(
        uint256 longSharesOut,
        uint256 shortSharesOut,
        uint256 maxAmountIn
    ) external payable nonReentrant notPaused returns (uint256 amountIn) {
        require(!isExpired(), "Cannot be called after expiry");
        require(longSharesOut > 0 || shortSharesOut > 0, "Shares out must be > 0");

        uint256 cost1 = cost();
        longToken.mint(msg.sender, longSharesOut);
        shortToken.mint(msg.sender, shortSharesOut);
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
     * Sell `longSharesIn` quantity of {longToken} and `shortSharesIn` quantity
     * of {shortToken}
     *
     * Revert if the tokens received would be less than `minAmountOut`
     *
     * `optionsToken` must be equal to {longToken} or {shortToken} and this
     * method can only be called before expiration
     */
    function sell(
        uint256 longSharesIn,
        uint256 shortSharesIn,
        uint256 minAmountOut
    ) external nonReentrant returns (uint256 amountOut) {
        require(!isExpired(), "Cannot be called after expiry");
        require(longSharesIn > 0 || shortSharesIn > 0, "Shares must be > 0");

        uint256 cost1 = cost();
        longToken.burn(msg.sender, longSharesIn);
        shortToken.burn(msg.sender, shortSharesIn);
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
     * After this method has been called, {redeem} can be called by users to
     * trade in their options and receive their payouts in {baseToken}
     */
    function settle() external nonReentrant {
        require(isExpired(), "Cannot be called before expiry");
        require(!isSettled, "Already settled");

        isSettled = true;
        settlementPrice = oracle.getPrice();
        require(settlementPrice > 0, "Price from oracle must be > 0");

        emit Settled(settlementPrice);
    }

    /**
     * Users can call this method to redeem all their long and short tokens and
     * receive their payout in {baseToken}
     *
     * This method can only be called after {settle} has been called and the
     * settlement price has been set
     */
    function redeem() external nonReentrant returns (uint256 amountOut) {
        require(isExpired(), "Cannot be called before expiry");
        require(isSettled, "Cannot be called before settlement");

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

    // emergency use only
    function setOracle(IOracle _oracle) external onlyOwner {
        oracle = _oracle;
    }

    function isExpired() public view returns (bool) {
        return block.timestamp >= expiryTime;
    }

    // calculate LS-LMSR cost taking into account the index multiplier
    function cost() public view returns (uint256) {
        return
            calcLsLmsrCost(
                longToken.totalSupply().mul(multiplier).div(SCALE),
                shortToken.totalSupply().mul(multiplier).div(SCALE),
                alpha
            );
    }

    /**
     * Calculates amount of {baseToken} paid out to a user who redeems
     * `longShares` amount of long tokens and `shortShares` amount of short tokens.
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
        uint256 payoffPerLong = settlementPrice > strikePrice ? settlementPrice.sub(strikePrice) : 0;

        // p2 = min(S, K)
        uint256 payoffPerShort = Math.min(settlementPrice, strikePrice);

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
     *   _alpha = LS-LMSR parameter that determines liquidity-sensitivity
     *   b = _alpha * (q1 + q2)
     *
     * An equivalent expression for C(q1, q2) is used to avoid overflow when
     * calculating exponentials
     *
     *   C(q1, q2) = b * log(1 + exp(abs(q1 - q2) / b)) + max(q1, q2)
     */
    function calcLsLmsrCost(
        uint256 q1,
        uint256 q2,
        uint256 _alpha
    ) public pure returns (uint256) {
        // b = _alpha * (q1 + q2)
        uint256 b = q1.add(q2).mul(_alpha);
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
        return ABDKMath64x64.mulu(log, b).div(SCALE).add(max);
    }
}
