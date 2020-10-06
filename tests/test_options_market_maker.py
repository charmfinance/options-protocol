from brownie import reverts
from math import log
import pytest
import time


SCALE = 10 ** 18
EXPIRY_TIME = 2000000000  # 18 May 2033
ALPHA = int(SCALE // 10 // 2 / log(2))


@pytest.fixture
def deployer(accounts):
    return accounts[0]


@pytest.fixture
def user(accounts):
    return accounts[1]


@pytest.fixture
def user2(accounts):
    return accounts[2]


@pytest.fixture
def user3(accounts):
    return accounts[3]


@pytest.fixture
def base_token(MockToken, deployer):
    return deployer.deploy(MockToken)


@pytest.fixture
def usd_token(MockToken, deployer):
    return deployer.deploy(MockToken)


@pytest.fixture
def oracle(deployer, MockOracle):
    return deployer.deploy(MockOracle)


@pytest.fixture
def mm(OptionsMarketMaker, base_token, oracle, deployer, user, user2, user3):
    mm = deployer.deploy(
        OptionsMarketMaker,
        base_token,
        oracle,
        100 * SCALE,  # strikePrice = 100 usd
        ALPHA,  # alpha = 0.1 / 2 / log 2
        EXPIRY_TIME,
        SCALE,  # multiplier = 1
        "long name",
        "long symbol",
        "short name",
        "short symbol",
    )

    # mint 100 tokens to all users
    for u in [user, user2, user3]:
        base_token.mint(u, 100 * SCALE, {"from": deployer})
        base_token.approve(mm, 1000 * SCALE, {"from": u})

    return mm


@pytest.fixture
def ethmm(OptionsMarketMaker, oracle, deployer):
    zero_address = "0x0000000000000000000000000000000000000000"
    return deployer.deploy(
        OptionsMarketMaker,
        zero_address,  # eth
        oracle,
        100 * SCALE,  # strikePrice = 100 usd
        ALPHA,  # alpha = 0.1 / 2 / log 2
        EXPIRY_TIME,
        SCALE,  # multiplier = 1
        "long name",
        "long symbol",
        "short name",
        "short symbol",
    )


@pytest.fixture
def putmm(OptionsMarketMaker, usd_token, oracle, deployer, user, user2, user3):
    mm = deployer.deploy(
        OptionsMarketMaker,
        usd_token,
        oracle,
        100 * SCALE,  # strikePrice = 100 usd
        ALPHA,  # alpha = 0.1 / 2 / log 2
        EXPIRY_TIME,
        100 * SCALE,  # multiplier = 100
        "long name",
        "long symbol",
        "short name",
        "short symbol",
    )

    # mint 10000 tokens to all users
    for u in [user, user2, user3]:
        usd_token.mint(u, 10000 * SCALE, {"from": deployer})
        usd_token.approve(mm, 100000 * SCALE, {"from": u})

    return mm


@pytest.fixture
def longToken(OptionsToken, mm):
    return OptionsToken.at(mm.longToken())


@pytest.fixture
def shortToken(OptionsToken, mm):
    return OptionsToken.at(mm.shortToken())


def test_options_market_constructor(
    mm, longToken, shortToken, base_token, oracle, deployer
):
    assert mm.owner() == deployer

    assert longToken.name() == "long name"
    assert longToken.symbol() == "long symbol"
    assert shortToken.name() == "short name"
    assert shortToken.symbol() == "short symbol"

    assert mm.baseToken() == base_token
    assert mm.oracle() == oracle
    assert mm.strikePrice() == 100 * SCALE
    assert mm.expiryTime() == EXPIRY_TIME

    # check alpha is correctly calculated from liquidity parameter in
    # constructor
    liquidity_param = SCALE // 10
    alpha = int(liquidity_param // 2 // log(2))
    assert pytest.approx(mm.alpha()) == liquidity_param // 2 // log(2)


# for checking costs, we check they are almost equal as exp and log in the
# contract code are only approximations
def test_buy_and_sell(mm, base_token, user, longToken, shortToken, fast_forward):

    # check initial state
    assert base_token.balanceOf(user) == 100 * SCALE
    assert longToken.totalSupply() == shortToken.totalSupply() == 0

    # buy 1 long token. set maxAmountIn very high so it's ignored
    tx = mm.buy(1 * SCALE, 0, 1000 * SCALE, {"from": user})

    # >> python calc_lslmsr_cost.py 1 0 0.1
    # 1000000068793027456
    assert base_token.balanceOf(mm) == 1000000068793027542
    assert tx.return_value == 1000000068793027542
    assert base_token.balanceOf(user) + base_token.balanceOf(mm) == 100 * SCALE
    assert longToken.totalSupply() == 1 * SCALE
    assert shortToken.totalSupply() == 0
    assert tx.events["Trade"] == {
        "account": user,
        "isBuy": True,
        "longShares": 1 * SCALE,
        "shortShares": 0,
        "cost": 1000000068793027542,
        "newLongSupply": 1 * SCALE,
        "newShortSupply": 0,
    }

    # buy 5 long tokens and 2 short tokens
    tx = mm.buy(5 * SCALE, 2 * SCALE, 1000 * SCALE, {"from": user})

    # >> python calc_lslmsr_cost.py 6 2 0.1
    # 6000563277757123584
    assert base_token.balanceOf(mm) == 6000563277757123355
    assert tx.return_value == 6000563277757123355 - 1000000068793027542
    assert base_token.balanceOf(user) + base_token.balanceOf(mm) == 100 * SCALE
    assert longToken.totalSupply() == 6 * SCALE
    assert shortToken.totalSupply() == 2 * SCALE
    assert tx.events["Trade"] == {
        "account": user,
        "isBuy": True,
        "longShares": 5 * SCALE,
        "shortShares": 2 * SCALE,
        "cost": 6000563277757123355 - 1000000068793027542,
        "newLongSupply": 6 * SCALE,
        "newShortSupply": 2 * SCALE,
    }

    # sell 2 long tokens and short tokens. set minAmountOut to 0 so it's ignored
    tx = mm.sell(2 * SCALE, 2 * SCALE, 0, {"from": user})

    # >> python calc_lslmsr_cost.py 4 0 0.1
    # 4000000275172109824
    assert base_token.balanceOf(mm) == 4000000275172110168
    assert tx.return_value == 6000563277757123355 - 4000000275172110168
    assert base_token.balanceOf(user) + base_token.balanceOf(mm) == 100 * SCALE
    assert longToken.totalSupply() == 4 * SCALE
    assert shortToken.totalSupply() == 0 * SCALE
    assert tx.events["Trade"] == {
        "account": user,
        "isBuy": False,
        "longShares": 2 * SCALE,
        "shortShares": 2 * SCALE,
        "cost": 6000563277757123355 - 4000000275172110168,
        "newLongSupply": 4 * SCALE,
        "newShortSupply": 0 * SCALE,
    }

    # sell rest of long tokens
    tx = mm.sell(4 * SCALE, 0, 0, {"from": user})
    assert base_token.balanceOf(mm) == 0
    assert tx.return_value == 4000000275172110168
    assert base_token.balanceOf(user) + base_token.balanceOf(mm) == 100 * SCALE
    assert longToken.totalSupply() == 0
    assert shortToken.totalSupply() == 0
    assert tx.events["Trade"] == {
        "account": user,
        "isBuy": False,
        "longShares": 4 * SCALE,
        "shortShares": 0,
        "cost": 4000000275172110168,
        "newLongSupply": 0 * SCALE,
        "newShortSupply": 0 * SCALE,
    }

    # cannot buy or sell after expiry
    fast_forward(EXPIRY_TIME)
    with reverts("Cannot be called after expiry"):
        mm.buy(10 * SCALE, 0, 1000 * SCALE, {"from": user})
    with reverts("Cannot be called after expiry"):
        mm.sell(0, 10 * SCALE, 0, {"from": user})


def test_cannot_buy_or_sell_if_insufficient_balance(
    mm, longToken, shortToken, base_token, user
):
    assert base_token.balanceOf(user) == 100 * SCALE

    # only have 100 tokens so can buy at most 99 shares
    # >> python calc_lslmsr_cost.py 99 0 0.1
    # 99000006810509737984
    # >> python calc_lslmsr_cost.py 100 0 0.1
    # 100000006879302762496
    with reverts("ERC20: transfer amount exceeds balance"):
        mm.buy(100 * SCALE, 0, 1000 * SCALE, {"from": user})

    mm.buy(0, 99 * SCALE, 1000 * SCALE, {"from": user})

    # can sell at most 99 shares
    with reverts("ERC20: burn amount exceeds balance"):
        mm.sell(100 * SCALE, 0, 0, {"from": user})

    mm.sell(0, 99 * SCALE, 0, {"from": user})

    # after buying 90 long tokens, can buy at most 91 short tokens
    # >> python calc_lslmsr_cost.py 90 91 0.1
    # 99559571516926771200
    # >> python calc_lslmsr_cost.py 90 92 0.1
    # 100138048239407169536
    mm.buy(90 * SCALE, 0, 1000 * SCALE, {"from": user})

    with reverts("ERC20: transfer amount exceeds balance"):
        mm.buy(0, 92 * SCALE, 1000 * SCALE, {"from": user})

    mm.buy(0, 91 * SCALE, 1000 * SCALE, {"from": user})


# we need to use tolerance of 0.999999 and 1.000001 as costs are not exact
def test_buy_and_sell_reverts_when_slippage_too_high(mm, longToken, shortToken, user):

    # >> python calc_lslmsr_cost.py 10 0 0.1
    # 10000000687930275840
    cost = 10000000687930275840

    with reverts("Max slippage exceeded"):
        mm.buy(10 * SCALE, 0, cost * 0.999999, {"from": user})
    mm.buy(10 * SCALE, 0, cost * 1.000001, {"from": user})

    # >> python calc_lslmsr_cost.py 10 3 0.1
    # 10000537157956245504
    cost = 10000537157956245504 - 10000000687930275840
    with reverts("Max slippage exceeded"):
        mm.buy(0, 3 * SCALE, cost * 0.999999, {"from": user})
    mm.buy(0, 3 * SCALE, cost * 1.000001, {"from": user})

    # >> python calc_lslmsr_cost.py 0 3 0.1
    # 3000000206379082752
    cost = 10000537157956245504 - 3000000206379082752
    with reverts("Max slippage exceeded"):
        mm.sell(10 * SCALE, 0, cost * 1.000001, {"from": user})
    mm.sell(10 * SCALE, 0, cost * 0.999999, {"from": user})

    cost = 3000000206379082752
    with reverts("Max slippage exceeded"):
        mm.sell(0, 3 * SCALE, cost * 1.000001, {"from": user})
    mm.sell(0, 3 * SCALE, cost * 0.999999, {"from": user})


def test_buy_and_sell_with_extreme_amounts(mm, longToken, shortToken, base_token, user):
    base_token.mint(user, 10 ** 40 * SCALE)
    base_token.approve(mm, 10 ** 40 * SCALE, {"from": user})
    total_balance = base_token.balanceOf(user) + base_token.balanceOf(mm)

    # buy 10**18 long tokens
    tx = mm.buy(10 ** 18 * SCALE, 0, 10 ** 40, {"from": user})

    # >> python calc_lslmsr_cost.py 1000000000000000000 0 0.1
    # 1000000068793027590977033455817195520
    assert tx.return_value == 1000000068793027542051701528520680644
    assert base_token.balanceOf(mm) == 1000000068793027542051701528520680644

    # small buy still works
    bal = base_token.balanceOf(mm)
    tx = mm.buy(1, 0, 10 ** 40, {"from": user})
    assert tx.return_value == 1
    assert base_token.balanceOf(mm) - bal == 1

    # small sell still works
    bal = base_token.balanceOf(mm)
    tx = mm.sell(1, 0, 0, {"from": user})
    assert tx.return_value == 1
    assert bal - base_token.balanceOf(mm) == 1

    # buy 10**18 short tokens
    # >> python calc_lslmsr_cost.py 1000000000000000000 1000000000000000000 0.1
    # 1100000000000000002390515334516834304
    tx = mm.buy(0, 10 ** 18 * SCALE, 10 ** 40, {"from": user})
    assert base_token.balanceOf(mm) == 1100000000000000007801447287920083588
    assert (
        tx.return_value
        == 1100000000000000007801447287920083588 - 1000000068793027542051701528520680644
    )

    # small buy still works
    bal = base_token.balanceOf(mm)
    tx = mm.buy(1, 0, 10 ** 40, {"from": user})
    assert tx.return_value == 1
    assert base_token.balanceOf(mm) - bal == 1

    # small sell still works
    bal = base_token.balanceOf(mm)
    tx = mm.sell(1, 0, 0, {"from": user})
    assert tx.return_value == 1
    assert bal - base_token.balanceOf(mm) == 1

    # sell everything
    mm.sell(10 ** 18 * SCALE, 0, 0, {"from": user})
    mm.sell(0, 10 ** 18 * SCALE, 0, {"from": user})
    assert base_token.balanceOf(user) + base_token.balanceOf(mm) == total_balance
    assert longToken.totalSupply() == 0 * SCALE
    assert shortToken.totalSupply() == 0 * SCALE


def test_buy_and_sell_eth(OptionsToken, ethmm, user):
    assert user.balance() == 100 * SCALE
    longToken = OptionsToken.at(ethmm.longToken())

    # reverts if not enough eth sent with transaction
    with reverts("UniERC20: not enough value"):
        tx = ethmm.buy(10 * SCALE, 0, 1000 * SCALE, {"from": user})
    with reverts("UniERC20: not enough value"):
        tx = ethmm.buy(10 * SCALE, 0, 1000 * SCALE, {"from": user, "value": 1 * SCALE})

    # buy 10 long tokens
    tx = ethmm.buy(10 * SCALE, 0, 1000 * SCALE, {"from": user, "value": 12 * SCALE})

    # >> python calc_lslmsr_cost.py 10 0 0.1
    # 10000000687930275840
    assert tx.return_value == 10000000687930275420
    assert ethmm.balance() == 10000000687930275420
    assert user.balance() + ethmm.balance() == 100 * SCALE

    # sell 10 long tokens
    tx = ethmm.sell(10 * SCALE, 0, 0, {"from": user})
    assert tx.return_value == 10000000687930275420
    assert ethmm.balance() == 0
    assert user.balance() + ethmm.balance() == 100 * SCALE


def test_calc_lslmsr_cost(mm):

    # max commission = 0.1
    alpha = int(SCALE // 10 // 2 // log(2))

    assert mm.calcLsLmsrCost(0, 0, alpha) == 0
    assert mm.calcLsLmsrCost(1, 0, alpha) == 1
    assert mm.calcLsLmsrCost(0, 1, alpha) == 1
    assert mm.calcLsLmsrCost(1, 1, alpha) == 1

    # >> python calc_lslmsr_cost.py 1 1 0.1
    # 1100000000000000128
    assert mm.calcLsLmsrCost(1 * SCALE, 1 * SCALE, alpha) == 1100000000000000007

    # >> python calc_lslmsr_cost.py 5 5 0.1
    # 5500000000000000000
    assert mm.calcLsLmsrCost(5 * SCALE, 5 * SCALE, alpha) == 5500000000000000039

    # >> python calc_lslmsr_cost.py 3 11 0.1
    # 11000366311880366080
    assert mm.calcLsLmsrCost(3 * SCALE, 11 * SCALE, alpha) == 11000366311880366618

    # >> python calc_lslmsr_cost.py 1000000000000 5 0.1
    # 1000000068793027574674002804736
    assert (
        mm.calcLsLmsrCost(10 ** 12 * SCALE, 5 * SCALE, alpha)
        == 1000000068793027551929301695942
    )

    # max commission = 10**-12
    alpha = int(SCALE // 10 ** 12 // 2 // log(2))

    # >> python calc_lslmsr_cost.py 1 1 0.000000000001
    # 1000000000001000064
    assert mm.calcLsLmsrCost(1 * SCALE, 1 * SCALE, alpha) == 1000000000000999999

    # max commission = 10**12
    alpha = int(SCALE * 10 ** 12 // 2 // log(2))

    # >> python calc_lslmsr_cost.py 1 1 1000000000000
    # 1000000000000999959739389444096
    assert (
        mm.calcLsLmsrCost(1 * SCALE, 1 * SCALE, alpha)
        == 1000000000001000136983480685343
    )


def test_settle(mm, oracle, user, fast_forward):
    oracle.setPrice(123 * SCALE)
    with reverts("Cannot be called before expiry"):
        mm.settle()

    # can only call settle() after expiry time and can only call once
    fast_forward(EXPIRY_TIME)
    assert mm.settlementPrice() == 0
    tx = mm.settle({"from": user})
    assert mm.settlementPrice() == 123 * SCALE
    assert tx.events["Settled"] == {
        "settlementPrice": 123 * SCALE,
    }

    with reverts("Already settled"):
        mm.settle()


def test_redeem_in_the_money(
    mm, longToken, shortToken, base_token, oracle, user, user2, fast_forward
):

    # users buy 10 long tokens and 15 short tokens for a cost of 15.109
    # >> python calc_lslmsr_cost.py 10 15 0.1
    # 15109328551562924032
    mm.buy(5 * SCALE, 5 * SCALE, 1000 * SCALE, {"from": user})
    mm.buy(5 * SCALE, 10 * SCALE, 1000 * SCALE, {"from": user2})

    bal1 = base_token.balanceOf(user)
    bal2 = base_token.balanceOf(user2)

    oracle.setPrice(125 * SCALE)
    with reverts("Cannot be called before expiry"):
        mm.redeem({"from": user})

    fast_forward(EXPIRY_TIME)
    with reverts("Cannot be called before settlement"):
        mm.redeem({"from": user})

    mm.settle()
    tx1 = mm.redeem({"from": user})
    tx2 = mm.redeem({"from": user2})

    # exercise price is 125 usd and strike price is 100 usd
    # long token settle price is (1 - 100 / 125) = 0.2
    # short token settle price is 100 / 125 = 0.8
    # so each long token pays out 0.2 / (10 * 0.2 + 15 * 0.8) * 15.109 = 0.216
    # and each short token pays out 0.8 / (10 * 0.2 + 15 * 0.8) * 15.109 = 0.863

    # >>> 0.21584755073661324 * 5 + 0.863390202946453 * 5
    # 5.396188768415331
    assert tx1.return_value == 5396188768415330103

    # >>> 0.21584755073661324 * 5 + 0.863390202946453 * 10
    # 9.713139783147597
    assert tx2.return_value == 9713139783147594188

    assert base_token.balanceOf(user) - bal1 == 5396188768415330103
    assert base_token.balanceOf(user2) - bal2 == 9713139783147594188
    assert longToken.balanceOf(user) == 0
    assert shortToken.balanceOf(user) == 0
    assert longToken.balanceOf(user2) == 0
    assert shortToken.balanceOf(user2) == 0
    assert tx1.events["Redeemed"] == {
        "account": user,
        "longSharesIn": 5 * SCALE,
        "shortSharesIn": 5 * SCALE,
        "amountOut": 5396188768415330103,
    }
    assert tx2.events["Redeemed"] == {
        "account": user2,
        "longSharesIn": 5 * SCALE,
        "shortSharesIn": 10 * SCALE,
        "amountOut": 9713139783147594188,
    }

    # can't call again
    with reverts("Balance must be > 0"):
        tx = mm.redeem({"from": user})


def test_redeem_out_of_the_money(
    mm,
    longToken,
    shortToken,
    base_token,
    oracle,
    user,
    user2,
    fast_forward,
):

    # users buy 15.109 tokens worth of options
    # >> python calc_lslmsr_cost.py 10 15 0.1
    # 15109328551562924032
    mm.buy(5 * SCALE, 5 * SCALE, 1000 * SCALE, {"from": user})
    mm.buy(5 * SCALE, 10 * SCALE, 1000 * SCALE, {"from": user2})

    bal1 = base_token.balanceOf(user)
    bal2 = base_token.balanceOf(user2)

    oracle.setPrice(99 * SCALE)

    fast_forward(EXPIRY_TIME)
    mm.settle()
    tx1 = mm.redeem({"from": user})
    tx2 = mm.redeem({"from": user2})

    # exercise price is 99 usd and strike price is 100 usd
    # long token settle price is 0
    # short token settle price is 1
    # so each long token pays out 0
    # and each short token pays out 15.109 / 15 = 1.007

    # >>> 15109328551562924032e-18 * 5 / 15
    # 5.036442850520975
    assert tx1.return_value == 5036442850520974763

    # >>> 15109328551562924032e-18 * 10 / 15
    # 10.07288570104195
    assert tx2.return_value == 10072885701041949528

    assert base_token.balanceOf(user) - bal1 == 5036442850520974763
    assert base_token.balanceOf(user2) - bal2 == 10072885701041949528
    assert longToken.balanceOf(user) == 0
    assert shortToken.balanceOf(user) == 0
    assert longToken.balanceOf(user2) == 0
    assert shortToken.balanceOf(user2) == 0


def test_redeem_eth(OptionsToken, ethmm, oracle, user, fast_forward):
    longToken = OptionsToken.at(ethmm.longToken())

    # user buys 10.0 eth worth of options
    # python calc_lslmsr_cost.py 10 0 0.1
    # 10000000687930275840
    ethmm.buy(10 * SCALE, 0, 1000 * SCALE, {"from": user, "value": 12 * SCALE})
    oracle.setPrice(125 * SCALE)
    fast_forward(EXPIRY_TIME)
    ethmm.settle()

    bal = user.balance()
    tx = ethmm.redeem({"from": user})

    assert tx.return_value == 10000000687930275420
    assert user.balance() - bal == 10000000687930275420


def test_transfer_ownership(mm, deployer, user):

    # only owner
    with reverts("Ownable: caller is not the owner"):
        mm.transferOwnership(user, {"from": user})

    mm.transferOwnership(user, {"from": deployer})
    assert mm.owner() == user


def test_set_oracle(MockOracle, mm, deployer, user):
    oracle2 = deployer.deploy(MockOracle)

    # only owner
    with reverts("Ownable: caller is not the owner"):
        mm.setOracle(oracle2, {"from": user})

    mm.setOracle(oracle2, {"from": deployer})
    assert mm.oracle() == oracle2


def test_pause_unpause(mm, deployer, user, longToken):
    with reverts("Ownable: caller is not the owner"):
        mm.pause({"from": user})
    mm.pause({"from": deployer})

    with reverts("This method has been paused"):
        mm.buy(1 * SCALE, 0, 1000 * SCALE, {"from": user})

    with reverts("Ownable: caller is not the owner"):
        mm.unpause({"from": user})
    mm.unpause({"from": deployer})
    mm.buy(1 * SCALE, 0, 1000 * SCALE, {"from": user})


def test_with_multiplier(OptionsToken, putmm, oracle, usd_token, user, fast_forward):
    longToken = OptionsToken.at(putmm.longToken())
    shortToken = OptionsToken.at(putmm.shortToken())

    # check initial state
    assert usd_token.balanceOf(user) == 10000 * SCALE
    assert longToken.totalSupply() == shortToken.totalSupply() == 0

    # buy 1 long token. set maxAmountIn very high so it's ignored
    tx = putmm.buy(1 * SCALE, 0, 10000 * SCALE, {"from": user})

    # >> python calc_lslmsr_cost.py 100 0 0.1
    # 100000006879302762496
    assert usd_token.balanceOf(putmm) == 100000006879302754205
    assert tx.return_value == 100000006879302754205
    assert usd_token.balanceOf(user) + usd_token.balanceOf(putmm) == 10000 * SCALE
    assert longToken.totalSupply() == 1 * SCALE
    assert shortToken.totalSupply() == 0
    assert tx.events["Trade"] == {
        "account": user,
        "isBuy": True,
        "longShares": 1 * SCALE,
        "shortShares": 0,
        "cost": 100000006879302754205,
        "newLongSupply": 1 * SCALE,
        "newShortSupply": 0,
    }

    # buy 2 short tokens
    tx = putmm.buy(0, 2 * SCALE, 10000 * SCALE, {"from": user})

    # >> python calc_lslmsr_cost.py 100 200 0.1
    # 200211968079890808832
    assert usd_token.balanceOf(putmm) == 200211968079890787869
    assert tx.return_value == 200211968079890787869 - 100000006879302754205
    assert usd_token.balanceOf(user) + usd_token.balanceOf(putmm) == 10000 * SCALE
    assert longToken.totalSupply() == 1 * SCALE
    assert shortToken.totalSupply() == 2 * SCALE
    assert tx.events["Trade"] == {
        "account": user,
        "isBuy": True,
        "longShares": 0,
        "shortShares": 2 * SCALE,
        "cost": 200211968079890787869 - 100000006879302754205,
        "newLongSupply": 1 * SCALE,
        "newShortSupply": 2 * SCALE,
    }

    # we can buy 97 short tokens but not 98
    # >> python calc_lslmsr_cost.py 100 9900 0.1
    # 9900000907729301405696
    # >> python calc_lslmsr_cost.py 100 10000 0.1
    # 10000000914293287550976
    assert longToken.totalSupply() == 1 * SCALE
    assert shortToken.totalSupply() == 2 * SCALE
    with reverts("ERC20: transfer amount exceeds balance"):
        putmm.buy(0, 98 * SCALE, 10000 * SCALE, {"from": user})
    putmm.buy(0, 97 * SCALE, 10000 * SCALE, {"from": user})
    putmm.sell(0, 97 * SCALE, 0, {"from": user})

    # we can sell 1 long token but not 2
    with reverts("ERC20: burn amount exceeds balance"):
        putmm.sell(2 * SCALE, 0, 0, {"from": user})
    putmm.sell(1 * SCALE, 0, 0, {"from": user})
    putmm.buy(1 * SCALE, 0, 10000 * SCALE, {"from": user})

    # if maxAmountIn is set to 10000, we can buy at most 10
    assert longToken.totalSupply() == 1 * SCALE
    assert shortToken.totalSupply() == 2 * SCALE
    with reverts("Max slippage exceeded"):
        putmm.buy(0, 11 * SCALE, 1000 * SCALE, {"from": user})
    putmm.buy(0, 10 * SCALE, 1000 * SCALE, {"from": user})

    # cannot buy or sell after expiry
    fast_forward(EXPIRY_TIME)
    with reverts("Cannot be called after expiry"):
        putmm.buy(10 * SCALE, 0, 10000 * SCALE, {"from": user})
    with reverts("Cannot be called after expiry"):
        putmm.buy(0, 10 * SCALE, 10000 * SCALE, {"from": user})
    with reverts("Cannot be called after expiry"):
        putmm.sell(10 * SCALE, 0, 0, {"from": user})
    with reverts("Cannot be called after expiry"):
        putmm.sell(0, 10 * SCALE, 0, {"from": user})
