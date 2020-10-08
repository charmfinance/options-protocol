from brownie import reverts
import pytest


SCALE = 10 ** 18
DAYS = 24 * 60 * 60
TIME1 = 2000000000


def test_staking_rewards(StakingRewards, MockToken, fast_forward, accounts):
    deployer, user, user2 = accounts[:3]

    fast_forward(TIME1 - 1 * DAYS)
    rewards_token = deployer.deploy(MockToken)
    staking_token = deployer.deploy(MockToken)
    sr = deployer.deploy(
        StakingRewards,
        rewards_token,
        staking_token,
        10 * DAYS,
    )

    rewards_token.mint(deployer, 1000 * SCALE, {"from": deployer})
    for u in [user, user2]:
        staking_token.mint(u, 100 * SCALE, {"from": deployer})
        staking_token.approve(sr, 100 * SCALE, {"from": u})

    assert sr.owner() == deployer
    assert sr.rewardsDuration() == 10 * DAYS

    # can't withdraw before staking
    assert staking_token.balanceOf(user) == 100 * SCALE
    with reverts("SafeMath: subtraction overflow"):
        sr.withdraw(1)
    assert staking_token.balanceOf(user) == 100 * SCALE

    # can't claim rewards before staking
    assert rewards_token.balanceOf(user) == 0
    sr.claimReward({"from": user})
    assert rewards_token.balanceOf(user) == 0

    # can't stake 100
    with reverts("ERC20: transfer amount exceeds balance"):
        sr.stake(101 * SCALE, {"from": user})

    # user stakes 10
    sr.stake(10 * SCALE, {"from": user})
    assert staking_token.balanceOf(user) == 90 * SCALE
    assert sr.rewards(user) == 0

    # can't notify rewards before sending rewards to contract
    with reverts("Provided reward too high"):
        sr.notifyRewardAmount(100 * SCALE)

    # sent rewards and notify
    rewards_token.transfer(sr, 1000 * SCALE, {"from": deployer})
    fast_forward(TIME1 + 0 * DAYS)
    sr.notifyRewardAmount(1000 * SCALE)

    # 1 day has passed. So user is eligible to 10% of reward
    fast_forward(TIME1 + 1 * DAYS)

    # user2 stakes 30
    sr.stake(30 * SCALE, {"from": user2})

    # 5 days have passed. So user gets 10+10%, user2 gets 30%
    fast_forward(TIME1 + 5 * DAYS)
    sr.claimReward({"from": user})
    assert pytest.approx(rewards_token.balanceOf(user)) == 200 * SCALE

    # 6 days have passed. User2 stakes another 10
    fast_forward(TIME1 + 6 * DAYS)
    sr.stake(10 * SCALE, {"from": user2})

    # 7 days have passed. So user gets 10+10+2.5+2%, user2 gets 30+7.5+8%
    fast_forward(TIME1 + 7 * DAYS)
    sr.exit({"from": user})
    assert pytest.approx(rewards_token.balanceOf(user)) == 245 * SCALE

    # reward period has ended. So user gets 10+10+2%, user2 gets 30+7.5+8+30%
    fast_forward(TIME1 + 100 * DAYS)
    sr.claimReward({"from": user2})
    assert pytest.approx(rewards_token.balanceOf(user2)) == 755 * SCALE
    assert pytest.approx(rewards_token.balanceOf(sr), abs=1e6) == 0
