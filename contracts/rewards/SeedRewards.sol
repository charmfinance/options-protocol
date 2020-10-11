// https://github.com/Synthetixio/synthetix
//
// MIT License
//
// Copyright (c) 2019 Synthetix
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.


// Changes made from original:
// - Set pragma version to 0.6.12
// - Let initial value of rewardsDuration be set
// - Added abstract, override and virtual keywords where needed
// - Removed `stake` and `withdraw` from interface as SeedRewards uses a different signature
// - `stake` and `withdraw` methods directly buy options from the market-maker
// - Added `receive` method to receive eth refund when buying options with eth

// This contract is very similar to StakingRewards. The difference is when a
// user stakes, it directly buys call/put options and covered call options from
// the market-maker in equal quantities. This improves the liquidity of the
// market-maker with a position that's hedged. This is implemented directly
// in this rewards contract so that users can stake/withdraw with a single
// transaction instead of three (buy, approve, stake)


pragma solidity ^0.6.12;

import "@openzeppelin/contracts/math/Math.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";


import "./StakingRewards.sol";
import "../libraries/UniERC20.sol";
import "../OptionsMarketMaker.sol";


// https://github.com/Synthetixio/synthetix/blob/develop/contracts/StakingRewards.sol
contract SeedRewards is IStakingRewards, RewardsDistributionRecipient, ReentrancyGuard, Pausable {
    using SafeMath for uint256;
    using SafeERC20 for IERC20;
    using UniERC20 for IERC20;

    uint256 public constant MARKET_MAKER_ALLOWANCE = 1 << 255;

    /* ========== STATE VARIABLES ========== */

    OptionsMarketMaker public marketMaker;
    IERC20 public baseToken;
    IERC20 public longToken;
    IERC20 public shortToken;

    IERC20 public rewardsToken;
    uint256 public periodFinish = 0;
    uint256 public rewardRate = 0;
    uint256 public rewardsDuration;
    uint256 public lastUpdateTime;
    uint256 public rewardPerTokenStored;

    mapping(address => uint256) public userRewardPerTokenPaid;
    mapping(address => uint256) public rewards;

    uint256 private _totalSupply;
    mapping(address => uint256) private _balances;

    /* ========== CONSTRUCTOR ========== */

    constructor(
        address _marketMaker,
        address _owner,
        address _rewardsDistribution,
        address _rewardsToken,
        uint256 _rewardsDuration
    ) public Owned(_owner) {
        marketMaker = OptionsMarketMaker(_marketMaker);
        rewardsToken = IERC20(_rewardsToken);
        rewardsDistribution = _rewardsDistribution;

        require(_rewardsDuration >= 1 days, "Rewards duration must be >= 1 days");
        rewardsDuration = _rewardsDuration;

        baseToken = marketMaker.baseToken();
        longToken = marketMaker.longToken();
        shortToken = marketMaker.shortToken();

        // Approve all future buys from the market-maker contract
        if (!baseToken.isETH()) {
            baseToken.approve(address(marketMaker), MARKET_MAKER_ALLOWANCE);
        }
    }

    /* ========== VIEWS ========== */

    function totalSupply() external override view returns (uint256) {
        return _totalSupply;
    }

    function balanceOf(address account) external override view returns (uint256) {
        return _balances[account];
    }

    function lastTimeRewardApplicable() public override view returns (uint256) {
        return Math.min(block.timestamp, periodFinish);
    }

    function rewardPerToken() public override view returns (uint256) {
        if (_totalSupply == 0) {
            return rewardPerTokenStored;
        }
        return
            rewardPerTokenStored.add(
                lastTimeRewardApplicable().sub(lastUpdateTime).mul(rewardRate).mul(1e18).div(_totalSupply)
            );
    }

    function earned(address account) public override view returns (uint256) {
        return _balances[account].mul(rewardPerToken().sub(userRewardPerTokenPaid[account])).div(1e18).add(rewards[account]);
    }

    function getRewardForDuration() external override view returns (uint256) {
        return rewardRate.mul(rewardsDuration);
    }

    /* ========== MUTATIVE FUNCTIONS ========== */

    function stake(uint256 shares, uint256 maxAmountIn) external payable nonReentrant notPaused updateReward(msg.sender) {
        require(shares > 0, "Cannot stake 0");

        // send `maxAmountIn` quantity of base tokens
        uint256 balance1 = baseToken.uniBalanceOf(address(this));
        baseToken.uniTransferFromSenderToThis(maxAmountIn);
        uint256 balance2 = baseToken.uniBalanceOf(address(this));
        require(baseToken.isETH() || balance2.sub(balance1) == maxAmountIn, "Deflationary tokens not supported");

        // Buy call/put and covered call options in equal amounts
        uint256 amountIn = marketMaker.buy{value: msg.value}(shares, shares, maxAmountIn);

        // Refund difference between `maxAmountIn` and actual cost
        // Cheaper in gas than calculating exact cost
        if (amountIn < maxAmountIn) {
            baseToken.uniTransfer(msg.sender, maxAmountIn.sub(amountIn));
        }

        _totalSupply = _totalSupply.add(shares);
        _balances[msg.sender] = _balances[msg.sender].add(shares);
        emit Staked(msg.sender, shares);
    }

    function withdraw(uint256 shares, uint256 minAmountOut) public nonReentrant updateReward(msg.sender) {
        require(shares > 0, "Cannot withdraw 0");
        _totalSupply = _totalSupply.sub(shares);
        _balances[msg.sender] = _balances[msg.sender].sub(shares);

        if (!marketMaker.isExpired()) {
            // Sell options and return cost to user
            uint256 amountOut = marketMaker.sell(shares, shares, minAmountOut);
            baseToken.uniTransfer(msg.sender, amountOut);
        } else {
            // If options have expired, they can no longer be sold, so instead
            // the options themselves are returned to the user. These can then
            // be redeemed for the same value in the market-maker contract
            longToken.safeTransfer(msg.sender, shares);
            shortToken.safeTransfer(msg.sender, shares);
        }

        emit Withdrawn(msg.sender, shares);
    }

    function getReward() public override nonReentrant updateReward(msg.sender) {
        uint256 reward = rewards[msg.sender];
        if (reward > 0) {
            rewards[msg.sender] = 0;
            rewardsToken.safeTransfer(msg.sender, reward);
            emit RewardPaid(msg.sender, reward);
        }
    }

    function exit() external override {
        withdraw(_balances[msg.sender], 0);
        getReward();
    }

    /* ========== RESTRICTED FUNCTIONS ========== */

    function notifyRewardAmount(uint256 reward) external override onlyRewardsDistribution updateReward(address(0)) {
        if (block.timestamp >= periodFinish) {
            rewardRate = reward.div(rewardsDuration);
        } else {
            uint256 remaining = periodFinish.sub(block.timestamp);
            uint256 leftover = remaining.mul(rewardRate);
            rewardRate = reward.add(leftover).div(rewardsDuration);
        }

        // Ensure the provided reward amount is not more than the balance in the contract.
        // This keeps the reward rate in the right range, preventing overflows due to
        // very high values of rewardRate in the earned and rewardsPerToken functions;
        // Reward + leftover must be less than 2^256 / 10^18 to avoid overflow.
        uint balance = rewardsToken.balanceOf(address(this));
        require(rewardRate <= balance.div(rewardsDuration), "Provided reward too high");

        lastUpdateTime = block.timestamp;
        periodFinish = block.timestamp.add(rewardsDuration);
        emit RewardAdded(reward);
    }

    // Added to support recovering LP Rewards from other systems to be distributed to holders
    function recoverERC20(address tokenAddress, uint256 tokenAmount) external onlyOwner {
        // If it's SNX we have to query the token symbol to ensure its not a proxy or underlying
        bool isSNX = (keccak256(bytes("SNX")) == keccak256(bytes(ERC20(tokenAddress).symbol())));
        // Cannot recover the staking token or the rewards token
        require(
            tokenAddress != address(baseToken) && tokenAddress != address(rewardsToken) && !isSNX,
            "Cannot withdraw the staking or rewards tokens"
        );
        IERC20(tokenAddress).safeTransfer(owner, tokenAmount);
        emit Recovered(tokenAddress, tokenAmount);
    }

    function setRewardsDuration(uint256 _rewardsDuration) external onlyOwner {
        require(block.timestamp > periodFinish,
            "Previous rewards period must be complete before changing the duration for the new period"
        );
        rewardsDuration = _rewardsDuration;
        emit RewardsDurationUpdated(rewardsDuration);
    }

    /* ========== MODIFIERS ========== */

    modifier updateReward(address account) {
        rewardPerTokenStored = rewardPerToken();
        lastUpdateTime = lastTimeRewardApplicable();
        if (account != address(0)) {
            rewards[account] = earned(account);
            userRewardPerTokenPaid[account] = rewardPerTokenStored;
        }
        _;
    }

    /* ========== EVENTS ========== */

    event RewardAdded(uint256 reward);
    event Staked(address indexed user, uint256 amount);
    event Withdrawn(address indexed user, uint256 amount);
    event RewardPaid(address indexed user, uint256 reward);
    event RewardsDurationUpdated(uint256 newDuration);
    event Recovered(address token, uint256 amount);

    /* ========== RECEIVE FUNCTION ========== */

    // Needed to receive eth refund buying options from the market-maker
    receive() external payable {}
}
