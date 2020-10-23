from brownie import reverts
from math import log
import pytest


SCALE = 10 ** 18
EXPIRY_TIME = 2000000000  # 18 May 2033
ALPHA = int(SCALE // 10 // 2 / log(2))

DAYS = 24 * 60 * 60
TIME1 = 1900000000

CALL = 0
PUT = 1


def test_seed_rewards(
    SeedRewards,
    OptionsMarketMaker,
    OptionsToken,
    MockOracle,
    MockToken,
    accounts,
    fast_forward,
):
    deployer, user = accounts[:2]

    oracle = deployer.deploy(MockOracle)
    base_token = deployer.deploy(MockToken)

    mm = deployer.deploy(
        OptionsMarketMaker,
        base_token,
        oracle,
        CALL,
        100 * SCALE,  # strikePrice = 100 usd
        ALPHA,  # alpha = 0.1 / 2 / log 2
        EXPIRY_TIME,
        "long name",
        "long symbol",
        "short name",
        "short symbol",
    )
    long_token = OptionsToken.at(mm.longToken())
    short_token = OptionsToken.at(mm.shortToken())

    rewards_token = deployer.deploy(MockToken)
    staking_token = deployer.deploy(MockToken)
    pool = deployer.deploy(
        SeedRewards,
        mm,
        deployer,
        deployer,
        rewards_token,
        10 * DAYS,
    )

    rewards_token.mint(deployer, 1000 * SCALE, {"from": deployer})
    rewards_token.transfer(pool, 1000 * SCALE, {"from": deployer})
    fast_forward(TIME1 + 0 * DAYS)
    pool.notifyRewardAmount(1000 * SCALE)

    base_token.mint(user, 100 * SCALE, {"from": deployer})
    base_token.approve(pool, 1000 * SCALE, {"from": user})

    with reverts("SafeMath: subtraction overflow"):
        pool.withdraw(1 * SCALE, 0, {"from": user})

    with reverts("Cannot stake 0"):
        pool.stake(0, 20 * SCALE, {"from": user})

    # stake 10
    fast_forward(TIME1 + 1 * DAYS)
    pool.stake(10 * SCALE, 20 * SCALE, {"from": user})
    assert long_token.totalSupply() == 10 * SCALE
    assert short_token.totalSupply() == 10 * SCALE
    assert long_token.balanceOf(pool) == 10 * SCALE
    assert short_token.balanceOf(pool) == 10 * SCALE
    assert long_token.balanceOf(user) == 0
    assert short_token.balanceOf(user) == 0
    assert pool.balanceOf(user) == 10 * SCALE

    # >> python calc_lslmsr_cost.py 10 10 0.1
    # 11000000000000000000
    assert pytest.approx(base_token.balanceOf(user)) == 89 * SCALE

    with reverts("SafeMath: subtraction overflow"):
        pool.withdraw(11 * SCALE, 0, {"from": user})

    with reverts("Cannot withdraw 0"):
        pool.withdraw(0, 0, {"from": user})

    # withdraw 7
    fast_forward(TIME1 + 2 * DAYS)
    pool.withdraw(7 * SCALE, 0, {"from": user})
    assert long_token.totalSupply() == 3 * SCALE
    assert short_token.totalSupply() == 3 * SCALE
    assert long_token.balanceOf(pool) == 3 * SCALE
    assert short_token.balanceOf(pool) == 3 * SCALE
    assert long_token.balanceOf(user) == 0
    assert short_token.balanceOf(user) == 0
    assert pool.balanceOf(user) == 3 * SCALE

    # >> python calc_lslmsr_cost.py 3 3 0.1
    # 3300000000000000000
    assert pytest.approx(base_token.balanceOf(user)) == 96.7 * SCALE

    assert rewards_token.balanceOf(user) == 0
    fast_forward(TIME1 + 3 * DAYS)

    pool.getReward({"from": user})
    assert pytest.approx(rewards_token.balanceOf(user)) == 200 * SCALE

    # exit reverts if minAmountOut is too high
    with reverts("Max slippage exceeded"):
        pool.exit(97 * SCALE, {"from": user})

    # if withdraw after expiration, receive options tokens that can be redeemed
    fast_forward(EXPIRY_TIME)
    pool.exit(96 * SCALE, {"from": user})
    assert long_token.totalSupply() == 3 * SCALE
    assert short_token.totalSupply() == 3 * SCALE
    assert long_token.balanceOf(pool) == 0
    assert short_token.balanceOf(pool) == 0
    assert long_token.balanceOf(user) == 3 * SCALE
    assert short_token.balanceOf(user) == 3 * SCALE
    assert pool.balanceOf(user) == 0

    assert pytest.approx(base_token.balanceOf(user)) == 96.7 * SCALE


def test_seed_rewards_for_put_mm(
    SeedRewards,
    OptionsMarketMaker,
    OptionsToken,
    MockOracle,
    MockToken,
    accounts,
    fast_forward,
):
    deployer, user = accounts[:2]

    oracle = deployer.deploy(MockOracle)
    base_token = deployer.deploy(MockToken)

    mm = deployer.deploy(
        OptionsMarketMaker,
        base_token,
        oracle,
        PUT,
        100 * SCALE,  # strikePrice = 100 usd
        ALPHA,  # alpha = 0.1 / 2 / log 2
        EXPIRY_TIME,
        "long name",
        "long symbol",
        "short name",
        "short symbol",
    )
    long_token = OptionsToken.at(mm.longToken())
    short_token = OptionsToken.at(mm.shortToken())

    rewards_token = deployer.deploy(MockToken)
    staking_token = deployer.deploy(MockToken)
    pool = deployer.deploy(
        SeedRewards,
        mm,
        deployer,
        deployer,
        rewards_token,
        10 * DAYS,
    )

    rewards_token.mint(deployer, 1000 * SCALE, {"from": deployer})
    rewards_token.transfer(pool, 1000 * SCALE, {"from": deployer})
    fast_forward(TIME1 + 0 * DAYS)
    pool.notifyRewardAmount(1000 * SCALE)

    base_token.mint(user, 10000 * SCALE, {"from": deployer})
    base_token.approve(pool, 100000 * SCALE, {"from": user})

    with reverts("SafeMath: subtraction overflow"):
        pool.withdraw(1 * SCALE, 0, {"from": user})

    with reverts("Cannot stake 0"):
        pool.stake(0, 20 * SCALE, {"from": user})

    # stake 10
    fast_forward(TIME1 + 1 * DAYS)
    pool.stake(10 * SCALE, 2000 * SCALE, {"from": user})
    assert long_token.totalSupply() == 10 * SCALE
    assert short_token.totalSupply() == 10 * SCALE
    assert long_token.balanceOf(pool) == 10 * SCALE
    assert short_token.balanceOf(pool) == 10 * SCALE
    assert long_token.balanceOf(user) == 0
    assert short_token.balanceOf(user) == 0
    assert pool.balanceOf(user) == 10 * SCALE

    # >> python calc_lslmsr_cost.py 10 10 0.1
    # 11000000000000000000
    assert pytest.approx(base_token.balanceOf(user)) == 8900 * SCALE

    with reverts("SafeMath: subtraction overflow"):
        pool.withdraw(11 * SCALE, 0, {"from": user})

    with reverts("Cannot withdraw 0"):
        pool.withdraw(0, 0, {"from": user})

    # withdraw 7
    fast_forward(TIME1 + 2 * DAYS)
    pool.withdraw(7 * SCALE, 0, {"from": user})
    assert long_token.totalSupply() == 3 * SCALE
    assert short_token.totalSupply() == 3 * SCALE
    assert long_token.balanceOf(pool) == 3 * SCALE
    assert short_token.balanceOf(pool) == 3 * SCALE
    assert long_token.balanceOf(user) == 0
    assert short_token.balanceOf(user) == 0
    assert pool.balanceOf(user) == 3 * SCALE

    # >> python calc_lslmsr_cost.py 3 3 0.1
    # 3300000000000000000
    assert pytest.approx(base_token.balanceOf(user)) == 9670 * SCALE

    assert rewards_token.balanceOf(user) == 0
    fast_forward(TIME1 + 3 * DAYS)
    pool.getReward({"from": user})
    assert pytest.approx(rewards_token.balanceOf(user), rel=1e-4) == 200 * SCALE

    # if withdraw after expiration, receive options tokens that can be redeemed
    fast_forward(EXPIRY_TIME)
    pool.exit(0, {"from": user})
    assert long_token.totalSupply() == 3 * SCALE
    assert short_token.totalSupply() == 3 * SCALE
    assert long_token.balanceOf(pool) == 0
    assert short_token.balanceOf(pool) == 0
    assert long_token.balanceOf(user) == 3 * SCALE
    assert short_token.balanceOf(user) == 3 * SCALE
    assert pool.balanceOf(user) == 0

    assert pytest.approx(base_token.balanceOf(user)) == 9670 * SCALE


def test_seed_rewards_with_eth(
    SeedRewards,
    OptionsMarketMaker,
    OptionsToken,
    MockOracle,
    MockToken,
    accounts,
    fast_forward,
):
    deployer, user = accounts[:2]

    oracle = deployer.deploy(MockOracle)
    base_token = deployer.deploy(MockToken)

    zero_address = "0x0000000000000000000000000000000000000000"
    mm = deployer.deploy(
        OptionsMarketMaker,
        zero_address,
        oracle,
        CALL,
        100 * SCALE,  # strikePrice = 100 usd
        ALPHA,  # alpha = 0.1 / 2 / log 2
        EXPIRY_TIME,
        "long name",
        "long symbol",
        "short name",
        "short symbol",
    )
    long_token = OptionsToken.at(mm.longToken())
    short_token = OptionsToken.at(mm.shortToken())

    rewards_token = deployer.deploy(MockToken)
    staking_token = deployer.deploy(MockToken)
    pool = deployer.deploy(
        SeedRewards,
        mm,
        deployer,
        deployer,
        rewards_token,
        10 * DAYS,
    )

    rewards_token.mint(deployer, 1000 * SCALE, {"from": deployer})
    rewards_token.transfer(pool, 1000 * SCALE, {"from": deployer})
    fast_forward(TIME1 + 0 * DAYS)
    pool.notifyRewardAmount(1000 * SCALE)

    assert user.balance() == 100 * SCALE

    with reverts("SafeMath: subtraction overflow"):
        pool.withdraw(1 * SCALE, 0, {"from": user})

    with reverts("Cannot stake 0"):
        pool.stake(0, 20 * SCALE, {"from": user})

    # stake 10
    fast_forward(TIME1 + 1 * DAYS)
    pool.stake(10 * SCALE, 20 * SCALE, {"from": user, "value": 20 * SCALE})
    assert long_token.totalSupply() == 10 * SCALE
    assert short_token.totalSupply() == 10 * SCALE
    assert long_token.balanceOf(pool) == 10 * SCALE
    assert short_token.balanceOf(pool) == 10 * SCALE
    assert long_token.balanceOf(user) == 0
    assert short_token.balanceOf(user) == 0
    assert pool.balanceOf(user) == 10 * SCALE

    # >> python calc_lslmsr_cost.py 10 10 0.1
    # 11000000000000000000
    assert pytest.approx(user.balance()) == 89 * SCALE

    with reverts("SafeMath: subtraction overflow"):
        pool.withdraw(11 * SCALE, 0, {"from": user})

    with reverts("Cannot withdraw 0"):
        pool.withdraw(0, 0, {"from": user})

    # withdraw 7
    fast_forward(TIME1 + 2 * DAYS)
    pool.withdraw(7 * SCALE, 0, {"from": user})
    assert long_token.totalSupply() == 3 * SCALE
    assert short_token.totalSupply() == 3 * SCALE
    assert long_token.balanceOf(pool) == 3 * SCALE
    assert short_token.balanceOf(pool) == 3 * SCALE
    assert long_token.balanceOf(user) == 0
    assert short_token.balanceOf(user) == 0
    assert pool.balanceOf(user) == 3 * SCALE

    # >> python calc_lslmsr_cost.py 3 3 0.1
    # 3300000000000000000
    assert pytest.approx(user.balance()) == 96.7 * SCALE

    assert rewards_token.balanceOf(user) == 0
    fast_forward(TIME1 + 3 * DAYS)
    pool.getReward({"from": user})
    assert pytest.approx(rewards_token.balanceOf(user)) == 200 * SCALE

    # if withdraw after expiration, receive options tokens that can be redeemed
    fast_forward(EXPIRY_TIME)
    pool.exit(0, {"from": user})
    assert long_token.totalSupply() == 3 * SCALE
    assert short_token.totalSupply() == 3 * SCALE
    assert long_token.balanceOf(pool) == 0
    assert short_token.balanceOf(pool) == 0
    assert long_token.balanceOf(user) == 3 * SCALE
    assert short_token.balanceOf(user) == 3 * SCALE
    assert pool.balanceOf(user) == 0

    assert pytest.approx(user.balance()) == 96.7 * SCALE
