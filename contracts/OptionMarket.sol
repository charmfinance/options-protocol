// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;

import "@openzeppelin/contracts/math/SafeMath.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/utils/Address.sol";

import "./libraries/UniERC20.sol";
import "./libraries/openzeppelin/ERC20UpgradeSafe.sol";
import "./libraries/openzeppelin/OwnableUpgradeSafe.sol";
import "./libraries/openzeppelin/ReentrancyGuardUpgradeSafe.sol";
import "../interfaces/IOracle.sol";
import "./OptionMath.sol";
import "./OptionToken.sol";

/**
 * Automated market maker that lets users buy and sell options from it
 */
contract OptionMarket is ERC20UpgradeSafe, ReentrancyGuardUpgradeSafe, OwnableUpgradeSafe {
    using Address for address;
    using SafeERC20 for IERC20;
    using UniERC20 for IERC20;
    using SafeMath for uint256;

    event Buy(
        address indexed account,
        bool isLongToken,
        uint256 strikeIndex,
        uint256 optionsOut,
        uint256 amountIn,
        uint256 newSupply
    );

    event Sell(
        address indexed account,
        bool isLongToken,
        uint256 strikeIndex,
        uint256 optionsIn,
        uint256 amountOut,
        uint256 newSupply
    );

    event Deposit(address indexed account, uint256 sharesOut, uint256 amountIn, uint256 newB);
    event Withdraw(address indexed account, uint256 sharesIn, uint256 amountOut, uint256 newB);
    event Settle(uint256 expiryPrice);
    event Redeem(address indexed account, bool isLongToken, uint256 strikeIndex, uint256 amount);

    uint256 public constant SCALE = 1e18;
    uint256 public constant SCALE_SCALE = 1e36;

    IERC20 public baseToken;
    IOracle public oracle;
    OptionToken[] public longTokens;
    OptionToken[] public shortTokens;
    uint256[] public strikePrices;
    uint256 public expiryTime;
    bool public isPut;
    uint256 public tradingFee;
    uint256 public balanceCap;
    uint256 public disputePeriod;
    uint256 public numStrikes;

    bool public isPaused;
    bool public isSettled;
    uint256 public expiryPrice;

    // cache getCurrentCost and getCurrentPayoff between trades to save gas
    uint256 public lastCost;
    uint256 public lastPayoff;

    // total value of fees owed to LPs
    uint256 public poolValue;

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
        uint256 _disputePeriod,
        string memory _symbol
    ) public payable initializer {
        __ERC20_init(_symbol, _symbol);
        __ReentrancyGuard_init();
        __Ownable_init();

        // use same decimals as `baseToken`
        uint8 decimals = IERC20(_baseToken).isETH() ? 18 : ERC20UpgradeSafe(_baseToken).decimals();
        _setupDecimals(decimals);

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

        for (uint256 i = 0; i < _strikePrices.length; i++) {
            longTokens.push(OptionToken(_longTokens[i]));
            shortTokens.push(OptionToken(_shortTokens[i]));
        }

        require(!isExpired(), "Already expired");
    }

    /**
     * Buy options
     */
    function buy(
        bool isLongToken,
        uint256 strikeIndex,
        uint256 optionsOut,
        uint256 maxAmountIn
    ) external payable nonReentrant returns (uint256 amountIn) {
        require(totalSupply() > 0, "No liquidity");
        require(!isExpired(), "Already expired");
        require(msg.sender == owner() || !isPaused, "Paused");
        require(strikeIndex < strikePrices.length, "Index too large");
        require(optionsOut > 0, "optionsOut must be > 0");

        // mint the options
        OptionToken option = isLongToken ? longTokens[strikeIndex] : shortTokens[strikeIndex];
        option.mint(msg.sender, optionsOut);

        // calculate trading fee
        uint256 fee = optionsOut.mul(tradingFee);
        fee = isPut ? fee.mul(strikePrices[strikeIndex]).div(SCALE_SCALE) : fee.div(SCALE);
        poolValue = poolValue.add(fee);

        // calculate amount that needs to be sent in from lmsr cost
        uint256 costAfter = getCurrentCost();
        amountIn = costAfter.sub(lastCost).add(fee); // do sub first as a check since should be positive
        lastCost = costAfter;
        require(amountIn > 0, "Amount in must be > 0");
        require(amountIn <= maxAmountIn, "Max slippage exceeded");

        // transfer in amount from user
        _transferIn(amountIn);
        emit Buy(msg.sender, isLongToken, strikeIndex, optionsOut, amountIn, option.totalSupply());
    }

    /**
     * Sell options
     */
    function sell(
        bool isLongToken,
        uint256 strikeIndex,
        uint256 optionsIn,
        uint256 minAmountOut
    ) external nonReentrant returns (uint256 amountOut) {
        require(totalSupply() > 0, "No liquidity");
        require(!isExpired() || isSettled, "Must be called before expiry or after settlement");
        require(!isDisputePeriod(), "Dispute period");
        require(msg.sender == owner() || !isPaused, "Paused");
        require(strikeIndex < strikePrices.length, "Index too large");
        require(optionsIn > 0, "optionsIn must be > 0");

        // burn user's options
        OptionToken option = isLongToken ? longTokens[strikeIndex] : shortTokens[strikeIndex];
        option.burn(msg.sender, optionsIn);

        if (isSettled) {
            // after settlement, amount returned is option payoff
            uint256 payoffAfter = getCurrentPayoff();
            amountOut = lastPayoff.sub(payoffAfter);
            lastPayoff = payoffAfter;
        } else {
            // before expiry, amount returned is calculated from lmsr cost
            uint256 costAfter = getCurrentCost();
            amountOut = lastCost.sub(costAfter);
            lastCost = costAfter;
        }
        require(amountOut > 0, "Amount out must be > 0");
        require(amountOut >= minAmountOut, "Max slippage exceeded");

        // return amount to user
        baseToken.uniTransfer(msg.sender, amountOut);
        if (isSettled) {
            emit Redeem(msg.sender, isLongToken, strikeIndex, amountOut);
        } else {
            emit Sell(msg.sender, isLongToken, strikeIndex, optionsIn, amountOut, option.totalSupply());
        }
    }

    function deposit(uint256 sharesOut, uint256 maxAmountIn) external payable nonReentrant returns (uint256 amountIn) {
        require(!isExpired(), "Already expired");
        require(msg.sender == owner() || !isPaused, "Paused");
        require(sharesOut > 0, "sharesOut must be > 0");

        // calculate extra amount user needs to contribute to pool
        uint256 poolAmountIn;
        if (totalSupply() > 0) {
            poolAmountIn = poolValue.mul(sharesOut).div(totalSupply());
            poolValue = poolValue.add(poolAmountIn);
        }
        _mint(msg.sender, sharesOut);

        // calculate amount that needs to be sent in from lmsr cost
        uint256 costAfter = getCurrentCost();
        amountIn = costAfter.sub(lastCost).add(poolAmountIn); // do sub first as a check since should be positive
        lastCost = costAfter;
        require(amountIn > 0, "Amount in must be > 0");
        require(amountIn <= maxAmountIn, "Max slippage exceeded");

        // transfer in amount from user
        _transferIn(amountIn);
        emit Deposit(msg.sender, sharesOut, amountIn, totalSupply());
    }

    function withdraw(uint256 sharesIn, uint256 minAmountOut) external nonReentrant returns (uint256 amountOut) {
        require(!isExpired() || isSettled, "Must be called before expiry or after settlement");
        require(!isDisputePeriod(), "Dispute period");
        require(msg.sender == owner() || !isPaused, "Paused");
        require(sharesIn > 0, "sharesIn must be > 0");

        // calculate extra amount that needs to be returned to user
        uint256 poolAmountOut = poolValue.mul(sharesIn).div(totalSupply());
        poolValue = poolValue.sub(poolAmountOut);
        _burn(msg.sender, sharesIn);

        if (isSettled) {
            // after settlement, amount returned is the user's share in pool
            amountOut = poolAmountOut;
        } else {
            // before expiry, amount returned is calculated from lmsr cost
            uint256 costAfter = getCurrentCost();
            amountOut = lastCost.sub(costAfter).add(poolAmountOut); // do sub first as a check since should be positive
            lastCost = costAfter;
        }
        require(amountOut > 0, "Amount out must be > 0");
        require(amountOut >= minAmountOut, "Max slippage exceeded");

        // return amount to user
        baseToken.uniTransfer(msg.sender, amountOut);
        emit Withdraw(msg.sender, sharesIn, amountOut, totalSupply());
    }

    /**
     * At expiration, retrieve and store the underlying price from the oracle
     *
     * This method can be called by anyone but cannot be called more than once.
     */
    function settle() external nonReentrant {
        require(isExpired(), "Cannot be called before expiry");
        require(!isSettled, "Already settled");

        // fetch expiry price from oracle
        isSettled = true;
        expiryPrice = oracle.getPrice();
        require(expiryPrice > 0, "Price from oracle must be > 0");

        // update cached cost and pool value
        lastPayoff = getCurrentPayoff();
        poolValue = baseToken.uniBalanceOf(address(this)).sub(lastPayoff);
        emit Settle(expiryPrice);
    }

    /**
     * Calculates LMSR cost
     *
     * Represents the net amount deposited into the LMSR. This method is used
     * to calculate the cost of trades.
     */
    function getCurrentCost() public view returns (uint256) {
        uint256[] memory longSupplies = getTotalSupplies(longTokens);
        uint256[] memory shortSupplies = getTotalSupplies(shortTokens);
        uint256[] memory quantities = OptionMath.calcQuantities(strikePrices, isPut, longSupplies, shortSupplies);
        return OptionMath.calcLmsrCost(quantities, totalSupply());
    }

    /**
     * Calculates option payoff
     *
     * Represents total payoff to option holders
     */
    function getCurrentPayoff() public view returns (uint256) {
        uint256[] memory longSupplies = getTotalSupplies(longTokens);
        uint256[] memory shortSupplies = getTotalSupplies(shortTokens);
        return OptionMath.calcPayoff(strikePrices, expiryPrice, isPut, longSupplies, shortSupplies);
    }

    /**
     * Convenience method that returns arrays containing total supplies of all option tokens
     */
    function getTotalSupplies(OptionToken[] memory optionTokens) public view returns (uint256[] memory totalSupplies) {
        totalSupplies = new uint256[](optionTokens.length);
        for (uint256 i = 0; i < optionTokens.length; i++) {
            totalSupplies[i] = optionTokens[i].totalSupply();
        }
    }

    function isExpired() public view returns (bool) {
        return block.timestamp >= expiryTime;
    }

    function isDisputePeriod() public view returns (bool) {
        return block.timestamp >= expiryTime && block.timestamp < expiryTime + disputePeriod;
    }

    /**
     * Transfer amount from sender and do additional checks
     */
    function _transferIn(uint256 amountIn) private {
        uint256 balanceBefore = baseToken.uniBalanceOf(address(this));
        baseToken.uniTransferFromSenderToThis(amountIn);
        uint256 balanceAfter = baseToken.uniBalanceOf(address(this));
        require(baseToken.isETH() || balanceAfter.sub(balanceBefore) == amountIn, "Deflationary tokens not supported");
        require(balanceCap == 0 || baseToken.uniBalanceOf(address(this)) <= balanceCap, "Balance cap exceeded");
    }

    // used for guarded launch. to be removed in future versions
    function setBalanceCap(uint256 _balanceCap) external onlyOwner {
        balanceCap = _balanceCap;
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

        // set initial cached value of getCurrentCost()
        lastCost = getCurrentCost();
        poolValue = baseToken.uniBalanceOf(address(this)).sub(lastCost);
        emit Settle(expiryPrice);
    }
}
