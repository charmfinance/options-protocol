from brownie import reverts
import pytest
from pytest import approx


SCALE = 10 ** 18
PERCENT = SCALE // 100
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

CALL = PUT = True
COVER = False


def lslmsr(q, alpha):
    from math import exp, log

    b = alpha * sum(q)
    if b == 0:
        return 0
    mx = max(q)
    a = sum(exp((x - mx) / b) for x in q)
    cost = mx + b * log(a)
    return SCALE * cost


@pytest.mark.parametrize("isEth", [False, True])
@pytest.mark.parametrize("alpha", [1, 10 * PERCENT, SCALE - 1])
@pytest.mark.parametrize("isPut", [False, True])
@pytest.mark.parametrize("tradingFee", [0, 10 * PERCENT, SCALE - 1])
def test_initialize(
    a,
    OptionLsLmsr,
    MockToken,
    MockOracle,
    OptionToken,
    isEth,
    alpha,
    isPut,
    tradingFee,
):
    # setup args
    deployer = a[0]
    baseToken = ZERO_ADDRESS if isEth else deployer.deploy(MockToken)
    oracle = deployer.deploy(MockOracle)
    longTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    shortTokens = [deployer.deploy(OptionToken) for _ in range(4)]

    # deploy and initialize
    market = deployer.deploy(OptionLsLmsr)
    market.initialize(
        baseToken,
        oracle,
        longTokens,
        shortTokens,
        [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
        2000000000,  # expiry = 18 May 2033
        alpha,
        isPut,
        tradingFee,
    )

    # check variables all set
    assert market.baseToken() == baseToken
    assert market.oracle() == oracle
    assert market.expiryTime() == 2000000000
    assert market.alpha() == alpha
    assert market.isPut() == isPut
    assert market.tradingFee() == tradingFee

    assert market.maxStrikePrice() == 600 * SCALE
    assert market.numStrikes() == 4

    # check token arrays
    for i in range(4):
        assert market.longTokens(i) == longTokens[i]
    for i in range(4):
        assert market.shortTokens(i) == shortTokens[i]
    with reverts():
        market.longTokens(4)
    with reverts():
        market.shortTokens(4)

    # check strike price array
    for i in range(4):
        assert (
            market.strikePrices(i)
            == [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE][i]
        )
    with reverts():
        market.strikePrices(4)

    # can't initialize again
    with reverts("Contract instance has already been initialized"):
        market.initialize(
            baseToken,
            oracle,
            longTokens,
            shortTokens,
            [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
            2000000000,  # expiry = 18 May 2033
            1e17,  # alpha = 0.1
            isPut,
            1e16,  # tradingFee = 1%
        )


@pytest.mark.parametrize("isPut", [False, True])
@pytest.mark.parametrize("isEth", [False, True])
def test_initialize_errors(
    a, OptionLsLmsr, MockToken, MockOracle, OptionToken, isPut, isEth
):
    # setup args
    deployer = a[0]
    baseToken = ZERO_ADDRESS if isEth else deployer.deploy(MockToken)
    oracle = deployer.deploy(MockOracle)
    longTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    shortTokens = [deployer.deploy(OptionToken) for _ in range(4)]

    market = deployer.deploy(OptionLsLmsr)
    with reverts("Alpha must be > 0"):
        market.initialize(
            baseToken,
            oracle,
            longTokens,
            shortTokens,
            [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
            2000000000,  # expiry = 18 May 2033
            0,  # alpha = 0
            isPut,
            1e16,  # tradingFee = 1%
        )

    market = deployer.deploy(OptionLsLmsr)
    with reverts("Alpha must be < 1"):
        market.initialize(
            baseToken,
            oracle,
            longTokens,
            shortTokens,
            [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
            2000000000,  # expiry = 18 May 2033
            SCALE,  # alpha = 1
            isPut,
            1e16,  # tradingFee = 1%
        )

    market = deployer.deploy(OptionLsLmsr)
    with reverts("Trading fee must be < 1"):
        market.initialize(
            baseToken,
            oracle,
            longTokens,
            shortTokens,
            [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
            2000000000,  # expiry = 18 May 2033
            1e17,  # alpha = 0.1
            isPut,
            SCALE,  # tradingFee = 100%
        )

    market = deployer.deploy(OptionLsLmsr)
    with reverts("Already expired"):
        market.initialize(
            baseToken,
            oracle,
            longTokens,
            shortTokens,
            [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
            1500000000,  # expiry = 14 July 2017
            1e17,  # alpha = 0.1
            isPut,
            1e16,  # tradingFee = 1%
        )

    market = deployer.deploy(OptionLsLmsr)
    with reverts("Lengths do not match"):
        market.initialize(
            baseToken,
            oracle,
            longTokens[:3],
            shortTokens,
            [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
            2000000000,  # expiry = 18 May 2033
            1e17,  # alpha = 0.1
            isPut,
            1e16,  # tradingFee = 1%
        )

    market = deployer.deploy(OptionLsLmsr)
    with reverts("Lengths do not match"):
        market.initialize(
            baseToken,
            oracle,
            longTokens,
            shortTokens[:3],
            [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
            2000000000,  # expiry = 18 May 2033
            1e17,  # alpha = 0.1
            isPut,
            1e16,  # tradingFee = 1%
        )

    market = deployer.deploy(OptionLsLmsr)
    with reverts("Strike prices must not be empty"):
        market.initialize(
            baseToken,
            oracle,
            [],
            [],
            [],
            2000000000,  # expiry = 18 May 2033
            1e17,  # alpha = 0.1
            isPut,
            1e16,  # tradingFee = 1%
        )

    market = deployer.deploy(OptionLsLmsr)
    with reverts("Strike prices must be > 0"):
        market.initialize(
            baseToken,
            oracle,
            longTokens,
            shortTokens,
            [0, 400 * SCALE, 500 * SCALE, 600 * SCALE],
            2000000000,  # expiry = 18 May 2033
            1e17,  # alpha = 0.1
            isPut,
            1e16,  # tradingFee = 1%
        )

    market = deployer.deploy(OptionLsLmsr)
    with reverts("Strike prices must be increasing"):
        market.initialize(
            baseToken,
            oracle,
            longTokens,
            shortTokens,
            [300 * SCALE, 400 * SCALE, 500 * SCALE, 500 * SCALE],
            2000000000,  # expiry = 18 May 2033
            1e17,  # alpha = 0.1
            isPut,
            1e16,  # tradingFee = 1%
        )


@pytest.mark.parametrize("isEth", [False, True])
def test_buy_and_sell_calls(
    a, OptionLsLmsr, MockToken, MockOracle, OptionToken, fast_forward, isEth
):

    # setup args
    deployer, alice = a[:2]
    baseToken = ZERO_ADDRESS if isEth else deployer.deploy(MockToken)
    oracle = deployer.deploy(MockOracle)
    longTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    shortTokens = [deployer.deploy(OptionToken) for _ in range(4)]

    def getBalance(wallet):
        return wallet.balance() if isEth else baseToken.balanceOf(wallet)

    # deploy and initialize
    market = deployer.deploy(OptionLsLmsr)
    market.initialize(
        baseToken,
        oracle,
        longTokens,
        shortTokens,
        [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
        2000000000,  # expiry = 18 May 2033
        10 * PERCENT,  # alpha = 0.1
        False,  # call
        1 * PERCENT,  # tradingFee = 1%
    )
    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", 18)

    # give users base tokens
    if not isEth:
        baseToken.mint(alice, 100 * SCALE, {"from": deployer})
        baseToken.approve(market, 100 * SCALE, {"from": alice})
    value = 50 * SCALE if isEth else 0

    # index out of range
    with reverts("Index too large"):
        tx = market.buy(CALL, 4, SCALE, 100 * SCALE, {"from": alice, "value": value})
    with reverts("Index too large"):
        tx = market.buy(COVER, 4, SCALE, 100 * SCALE, {"from": alice, "value": value})

    # can't buy too much
    if isEth:
        with reverts("UniERC20: not enough value"):
            market.buy(CALL, 0, 100 * SCALE, 10000 * SCALE, {"from": alice})
    else:
        with reverts("ERC20: transfer amount exceeds balance"):
            market.buy(CALL, 0, 100 * SCALE, 10000 * SCALE, {"from": alice})

    # buy 2 calls
    tx = market.buy(CALL, 0, 2 * SCALE, 100 * SCALE, {"from": alice, "value": value})
    cost = lslmsr([0, 2, 2, 2, 2], 0.1) + 2 * PERCENT
    assert approx(tx.return_value) == cost
    assert approx(getBalance(alice)) == 100 * SCALE - cost
    assert longTokens[0].balanceOf(alice) == 2 * SCALE
    assert tx.events["Trade"] == {
        "account": alice,
        "isBuy": True,
        "isLongToken": True,
        "strikeIndex": 0,
        "size": 2 * SCALE,
        "cost": tx.return_value,
        "newSupply": 2 * SCALE,
    }

    # buy 3 calls
    tx = market.buy(CALL, 2, 3 * SCALE, 100 * SCALE, {"from": alice, "value": value})
    cost1 = lslmsr([0, 2, 2, 2, 2], 0.1) + 2 * PERCENT
    cost2 = lslmsr([0, 2, 2, 5, 5], 0.1) + 5 * PERCENT
    assert approx(tx.return_value) == cost2 - cost1
    assert approx(getBalance(alice)) == 100 * SCALE - cost2
    assert longTokens[0].balanceOf(alice) == 2 * SCALE
    assert longTokens[2].balanceOf(alice) == 3 * SCALE
    assert tx.events["Trade"] == {
        "account": alice,
        "isBuy": True,
        "isLongToken": True,
        "strikeIndex": 2,
        "size": 3 * SCALE,
        "cost": tx.return_value,
        "newSupply": 3 * SCALE,
    }

    # buy 5 covers
    tx = market.buy(COVER, 3, 5 * SCALE, 100 * SCALE, {"from": alice, "value": value})
    cost1 = lslmsr([0, 2, 2, 5, 5], 0.1) + 5 * PERCENT
    cost2 = lslmsr([5, 7, 7, 10, 5], 0.1) + 10 * PERCENT
    assert approx(tx.return_value) == cost2 - cost1
    assert approx(getBalance(alice)) == 100 * SCALE - cost2
    assert longTokens[0].balanceOf(alice) == 2 * SCALE
    assert longTokens[2].balanceOf(alice) == 3 * SCALE
    assert shortTokens[3].balanceOf(alice) == 5 * SCALE
    assert tx.events["Trade"] == {
        "account": alice,
        "isBuy": True,
        "isLongToken": False,
        "strikeIndex": 3,
        "size": 5 * SCALE,
        "cost": tx.return_value,
        "newSupply": 5 * SCALE,
    }

    # buy 6 covers
    tx = market.buy(COVER, 0, 6 * SCALE, 100 * SCALE, {"from": alice, "value": value})
    cost1 = lslmsr([5, 7, 7, 10, 5], 0.1) + 10 * PERCENT
    cost2 = lslmsr([11, 7, 7, 10, 5], 0.1) + 16 * PERCENT
    assert approx(tx.return_value) == cost2 - cost1
    assert approx(getBalance(alice)) == 100 * SCALE - cost2
    assert longTokens[0].balanceOf(alice) == 2 * SCALE
    assert longTokens[2].balanceOf(alice) == 3 * SCALE
    assert shortTokens[0].balanceOf(alice) == 6 * SCALE
    assert shortTokens[3].balanceOf(alice) == 5 * SCALE
    assert tx.events["Trade"] == {
        "account": alice,
        "isBuy": True,
        "isLongToken": False,
        "strikeIndex": 0,
        "size": 6 * SCALE,
        "cost": tx.return_value,
        "newSupply": 6 * SCALE,
    }

    # can't sell more than you have
    with reverts("ERC20: burn amount exceeds balance"):
        market.sell(CALL, 0, 3 * SCALE, 0, {"from": alice})
    with reverts("ERC20: burn amount exceeds balance"):
        market.sell(COVER, 0, 7 * SCALE, 0, {"from": alice})
    with reverts("ERC20: burn amount exceeds balance"):
        market.sell(COVER, 1, 1 * SCALE, 0, {"from": alice})

    # only pool owner can skim
    with reverts("Ownable: caller is not the owner"):
        market.skim({"from": alice})

    balance1 = getBalance(deployer)
    assert market.calcSkimAmount() == 16 * PERCENT
    tx = market.skim({"from": deployer})
    assert approx(tx.return_value) == 16 * PERCENT
    assert approx(getBalance(deployer) - balance1) == 16 * PERCENT

    # can't skim again
    balance1 = getBalance(deployer)
    assert market.calcSkimAmount() == 0
    tx = market.skim({"from": deployer})
    assert tx.return_value == 0 * PERCENT
    assert getBalance(deployer) - balance1 == 0

    # sell 2 covers
    tx = market.sell(COVER, 0, 2 * SCALE, 0, {"from": alice})
    cost1 = lslmsr([11, 7, 7, 10, 5], 0.1) + 16 * PERCENT
    cost2 = lslmsr([9, 7, 7, 10, 5], 0.1) + 18 * PERCENT
    assert approx(tx.return_value) == cost1 - cost2
    assert approx(getBalance(alice)) == 100 * SCALE - cost2
    assert longTokens[0].balanceOf(alice) == 2 * SCALE
    assert longTokens[2].balanceOf(alice) == 3 * SCALE
    assert shortTokens[0].balanceOf(alice) == 4 * SCALE
    assert shortTokens[3].balanceOf(alice) == 5 * SCALE
    assert tx.events["Trade"] == {
        "account": alice,
        "isBuy": False,
        "isLongToken": False,
        "strikeIndex": 0,
        "size": 2 * SCALE,
        "cost": tx.return_value,
        "newSupply": 4 * SCALE,
    }

    # sell 2 calls
    tx = market.sell(CALL, 0, 2 * SCALE, 0, {"from": alice})
    cost1 = lslmsr([9, 7, 7, 10, 5], 0.1) + 18 * PERCENT
    cost2 = lslmsr([9, 5, 5, 8, 3], 0.1) + 20 * PERCENT
    assert approx(tx.return_value) == cost1 - cost2
    assert approx(getBalance(alice)) == 100 * SCALE - cost2
    assert longTokens[0].balanceOf(alice) == 0
    assert longTokens[2].balanceOf(alice) == 3 * SCALE
    assert shortTokens[0].balanceOf(alice) == 4 * SCALE
    assert shortTokens[3].balanceOf(alice) == 5 * SCALE
    assert tx.events["Trade"] == {
        "account": alice,
        "isBuy": False,
        "isLongToken": True,
        "strikeIndex": 0,
        "size": 2 * SCALE,
        "cost": tx.return_value,
        "newSupply": 0,
    }

    # sell 3 calls
    tx = market.sell(CALL, 2, 3 * SCALE, 0, {"from": alice})
    cost1 = lslmsr([9, 5, 5, 8, 3], 0.1) + 20 * PERCENT
    cost2 = lslmsr([9, 5, 5, 5, 0], 0.1) + 23 * PERCENT
    assert approx(tx.return_value) == cost1 - cost2
    assert approx(getBalance(alice)) == 100 * SCALE - cost2
    assert longTokens[0].balanceOf(alice) == 0
    assert longTokens[2].balanceOf(alice) == 0
    assert shortTokens[0].balanceOf(alice) == 4 * SCALE
    assert shortTokens[3].balanceOf(alice) == 5 * SCALE
    assert tx.events["Trade"] == {
        "account": alice,
        "isBuy": False,
        "isLongToken": True,
        "strikeIndex": 2,
        "size": 3 * SCALE,
        "cost": tx.return_value,
        "newSupply": 0,
    }

    # sell 5 covers
    tx = market.sell(COVER, 3, 5 * SCALE, 0, {"from": alice})
    cost1 = lslmsr([9, 5, 5, 5, 0], 0.1) + 23 * PERCENT
    cost2 = lslmsr([4, 0, 0, 0, 0], 0.1) + 28 * PERCENT
    assert approx(tx.return_value) == cost1 - cost2
    assert approx(getBalance(alice)) == 100 * SCALE - cost2
    assert longTokens[0].balanceOf(alice) == 0
    assert longTokens[2].balanceOf(alice) == 0
    assert shortTokens[0].balanceOf(alice) == 4 * SCALE
    assert shortTokens[3].balanceOf(alice) == 0
    assert tx.events["Trade"] == {
        "account": alice,
        "isBuy": False,
        "isLongToken": False,
        "strikeIndex": 3,
        "size": 5 * SCALE,
        "cost": tx.return_value,
        "newSupply": 0,
    }

    # sell 4 covers
    tx = market.sell(COVER, 0, 4 * SCALE, 0, {"from": alice})
    cost1 = lslmsr([4, 0, 0, 0, 0], 0.1) + 28 * PERCENT
    cost2 = 32 * PERCENT
    assert approx(tx.return_value) == cost1 - cost2
    assert approx(getBalance(alice)) == 100 * SCALE - cost2
    assert longTokens[0].balanceOf(alice) == 0
    assert longTokens[2].balanceOf(alice) == 0
    assert shortTokens[0].balanceOf(alice) == 0
    assert shortTokens[3].balanceOf(alice) == 0
    assert tx.events["Trade"] == {
        "account": alice,
        "isBuy": False,
        "isLongToken": False,
        "strikeIndex": 0,
        "size": 4 * SCALE,
        "cost": tx.return_value,
        "newSupply": 0,
    }

    balance1 = getBalance(deployer)
    tx = market.skim({"from": deployer})
    assert approx(tx.return_value) == 16 * PERCENT
    assert approx(getBalance(deployer) - balance1) == 16 * PERCENT

    # cannot buy or sell after expiry
    fast_forward(2000000000)
    with reverts("Already expired"):
        market.buy(CALL, 1, 1 * SCALE, 100 * SCALE, {"from": alice})
    with reverts("Already expired"):
        market.sell(COVER, 2, 1 * SCALE, 0, {"from": alice})


def test_buy_and_sell_puts(a, OptionLsLmsr, MockToken, MockOracle, OptionToken):

    # setup args
    deployer, alice = a[:2]
    baseToken = deployer.deploy(MockToken)
    oracle = deployer.deploy(MockOracle)
    longTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    shortTokens = [deployer.deploy(OptionToken) for _ in range(4)]

    # deploy and initialize
    market = deployer.deploy(OptionLsLmsr)
    market.initialize(
        baseToken,
        oracle,
        longTokens,
        shortTokens,
        [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
        2000000000,  # expiry = 18 May 2033
        10 * PERCENT,  # alpha = 0.1
        True,  # put
        1 * PERCENT,  # tradingFee = 1%
    )
    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", 18)

    # give users base tokens
    baseToken.mint(alice, 10000 * SCALE, {"from": deployer})
    baseToken.approve(market, 10000 * SCALE, {"from": alice})

    # index out of range
    with reverts("Index too large"):
        tx = market.buy(PUT, 4, SCALE, 100 * SCALE, {"from": alice})
    with reverts("Index too large"):
        tx = market.buy(COVER, 4, SCALE, 100 * SCALE, {"from": alice})

    # can't buy too much
    with reverts("ERC20: transfer amount exceeds balance"):
        market.buy(PUT, 0, 100 * SCALE, 1000000 * SCALE, {"from": alice})

    # buy 2 puts
    tx = market.buy(PUT, 0, 2 * SCALE, 10000 * SCALE, {"from": alice})
    cost = 600 * lslmsr([2, 0, 0, 0, 0], 0.1) + 300 * 2 * PERCENT
    assert approx(tx.return_value) == cost
    assert approx(baseToken.balanceOf(alice)) == 10000 * SCALE - cost
    assert longTokens[0].balanceOf(alice) == 2 * SCALE
    assert tx.events["Trade"] == {
        "account": alice,
        "isBuy": True,
        "isLongToken": True,
        "strikeIndex": 0,
        "size": 2 * SCALE,
        "cost": tx.return_value,
        "newSupply": 2 * SCALE,
    }

    # buy 5 covers
    tx = market.buy(COVER, 2, 5 * SCALE, 10000 * SCALE, {"from": alice})
    cost1 = 600 * lslmsr([2, 0, 0, 0, 0], 0.1) + 300 * 2 * PERCENT
    cost2 = 600 * lslmsr([2, 0, 0, 5, 5], 0.1) + 300 * 2 * PERCENT + 500 * 5 * PERCENT
    assert approx(tx.return_value) == cost2 - cost1
    assert approx(baseToken.balanceOf(alice)) == 10000 * SCALE - cost2
    assert longTokens[0].balanceOf(alice) == 2 * SCALE
    assert shortTokens[2].balanceOf(alice) == 5 * SCALE
    assert tx.events["Trade"] == {
        "account": alice,
        "isBuy": True,
        "isLongToken": False,
        "strikeIndex": 2,
        "size": 5 * SCALE,
        "cost": tx.return_value,
        "newSupply": 5 * SCALE,
    }

    # can't sell more than you have
    with reverts("ERC20: burn amount exceeds balance"):
        market.sell(CALL, 0, 3 * SCALE, 0, {"from": alice})
    with reverts("ERC20: burn amount exceeds balance"):
        market.sell(COVER, 1, 1 * SCALE, 0, {"from": alice})

    assert baseToken.balanceOf(deployer) == 0
    tx = market.skim({"from": deployer})
    assert approx(tx.return_value) == 300 * 2 * PERCENT + 500 * 5 * PERCENT
    assert (
        approx(baseToken.balanceOf(deployer)) == 300 * 2 * PERCENT + 500 * 5 * PERCENT
    )

    # sell 2 covers
    tx = market.sell(COVER, 2, 2 * SCALE, 0, {"from": alice})
    cost1 = 600 * lslmsr([2, 0, 0, 5, 5], 0.1) + 300 * 2 * PERCENT + 500 * 5 * PERCENT
    cost2 = 600 * lslmsr([2, 0, 0, 3, 3], 0.1) + 300 * 2 * PERCENT + 500 * 7 * PERCENT
    assert approx(tx.return_value) == cost1 - cost2
    assert approx(baseToken.balanceOf(alice)) == 10000 * SCALE - cost2
    assert longTokens[0].balanceOf(alice) == 2 * SCALE
    assert shortTokens[2].balanceOf(alice) == 3 * SCALE
    assert tx.events["Trade"] == {
        "account": alice,
        "isBuy": False,
        "isLongToken": False,
        "strikeIndex": 2,
        "size": 2 * SCALE,
        "cost": tx.return_value,
        "newSupply": 3 * SCALE,
    }

    tx = market.skim({"from": deployer})
    assert approx(tx.return_value) == 500 * 2 * PERCENT
    assert (
        approx(baseToken.balanceOf(deployer)) == 300 * 2 * PERCENT + 500 * 7 * PERCENT
    )


@pytest.mark.parametrize("isEth", [False, True])
@pytest.mark.parametrize("isPut", [False, True])
def test_settle(
    a, OptionLsLmsr, MockToken, MockOracle, OptionToken, fast_forward, isEth, isPut
):

    # setup args
    deployer, alice = a[:2]
    baseToken = ZERO_ADDRESS if isEth else deployer.deploy(MockToken)
    oracle = deployer.deploy(MockOracle)
    longTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    shortTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    oracle.setPrice(444 * SCALE)

    # deploy and initialize
    market = deployer.deploy(OptionLsLmsr)
    market.initialize(
        baseToken,
        oracle,
        longTokens,
        shortTokens,
        [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
        2000000000,  # expiry = 18 May 2033
        10 * PERCENT,  # alpha = 0.1
        isPut,
        1 * PERCENT,  # tradingFee = 1%
    )
    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", 18)

    with reverts("Cannot be called before expiry"):
        market.settle({"from": alice})

    # can only call settle() after expiry time and can only call once
    fast_forward(2000000000)
    assert market.expiryPrice() == 0
    tx = market.settle({"from": alice})
    assert market.expiryPrice() == 444 * SCALE
    assert tx.events["Settled"] == {
        "expiryPrice": 444 * SCALE,
    }

    with reverts("Already settled"):
        market.settle({"from": alice})


@pytest.mark.parametrize("isEth", [False, True])
def test_redeem_calls(
    a, OptionLsLmsr, MockToken, MockOracle, OptionToken, fast_forward, isEth
):

    # setup args
    deployer, alice, bob = a[:3]
    baseToken = ZERO_ADDRESS if isEth else deployer.deploy(MockToken)
    oracle = deployer.deploy(MockOracle)
    longTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    shortTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    oracle.setPrice(444 * SCALE)

    def getBalance(wallet):
        return wallet.balance() if isEth else baseToken.balanceOf(wallet)

    # deploy and initialize
    market = deployer.deploy(OptionLsLmsr)
    market.initialize(
        baseToken,
        oracle,
        longTokens,
        shortTokens,
        [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
        2000000000,  # expiry = 18 May 2033
        10 * PERCENT,  # alpha = 0.1
        False,  # call
        1 * PERCENT,  # tradingFee = 1%
    )
    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", 18)

    # give users base tokens
    if not isEth:
        baseToken.mint(alice, 100 * SCALE, {"from": deployer})
        baseToken.approve(market, 100 * SCALE, {"from": alice})
        baseToken.mint(bob, 100 * SCALE, {"from": deployer})
        baseToken.approve(market, 100 * SCALE, {"from": bob})

    # buy 2 calls (strike=300)
    market.buy(CALL, 0, 2 * SCALE, 100 * SCALE, {"from": alice, "value": 50 * SCALE})

    # buy 1 call (strike=600) and 3 covers (strike=400)
    market.buy(CALL, 3, 3 * SCALE, 100 * SCALE, {"from": bob, "value": 50 * SCALE})
    market.buy(COVER, 1, 3 * SCALE, 100 * SCALE, {"from": bob, "value": 50 * SCALE})
    market.sell(CALL, 3, 2 * SCALE, 0, {"from": bob})

    with reverts("Cannot be called before expiry"):
        market.redeem(CALL, 0, {"from": alice})

    fast_forward(2000000000)
    with reverts("Cannot be called before settlement"):
        market.redeem(CALL, 0, {"from": alice})

    market.settle({"from": alice})
    with reverts("Cannot be called during dispute period"):
        market.redeem(CALL, 0, {"from": alice})

    fast_forward(2000000000 + 3600)

    cost = lslmsr([3, 5, 2, 2, 3], 0.1)
    alicePayoff = 2 * (444 - 300)
    bobPayoff = 3 * 400
    payoff = alicePayoff + bobPayoff
    assert approx(market.costAtSettlement()) == cost
    assert market.payoffAtSettlement() == payoff * SCALE

    balance = getBalance(market)
    aliceBalance = getBalance(alice)
    tx = market.redeem(CALL, 0, {"from": alice})
    assert approx(tx.return_value) == cost * alicePayoff / payoff
    assert approx(balance - getBalance(market)) == cost * alicePayoff / payoff
    assert approx(getBalance(alice) - aliceBalance) == cost * alicePayoff / payoff
    assert tx.events["Redeemed"] == {
        "account": alice,
        "isLongToken": True,
        "strikeIndex": 0,
        "amount": tx.return_value,
    }

    with reverts("Balance must be > 0"):
        market.redeem(CALL, 0, {"from": alice})
    with reverts("Balance must be > 0"):
        market.redeem(CALL, 1, {"from": alice})

    balance = getBalance(market)
    bobBalance = getBalance(bob)
    tx = market.redeem(CALL, 3, {"from": bob})
    assert approx(tx.return_value) == 0
    assert approx(balance - getBalance(market)) == 0
    assert approx(getBalance(bob) - bobBalance) == 0
    assert tx.events["Redeemed"] == {
        "account": bob,
        "isLongToken": True,
        "strikeIndex": 3,
        "amount": 0,
    }

    balance = getBalance(market)
    bobBalance = getBalance(bob)
    tx = market.redeem(COVER, 1, {"from": bob})
    assert approx(tx.return_value) == cost * bobPayoff / payoff
    assert approx(balance - getBalance(market)) == cost * bobPayoff / payoff
    assert approx(getBalance(bob) - bobBalance) == cost * bobPayoff / payoff
    assert tx.events["Redeemed"] == {
        "account": bob,
        "isLongToken": False,
        "strikeIndex": 1,
        "amount": tx.return_value,
    }

    balance1 = getBalance(deployer)
    tx = market.skim({"from": deployer})
    assert approx(tx.return_value) == 10 * PERCENT
    assert approx(getBalance(deployer) - balance1) == 10 * PERCENT


def test_redeem_puts(a, OptionLsLmsr, MockToken, MockOracle, OptionToken, fast_forward):

    # setup args
    deployer, alice, bob = a[:3]
    baseToken = deployer.deploy(MockToken)
    oracle = deployer.deploy(MockOracle)
    longTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    shortTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    oracle.setPrice(444 * SCALE)

    # deploy and initialize
    market = deployer.deploy(OptionLsLmsr)
    market.initialize(
        baseToken,
        oracle,
        longTokens,
        shortTokens,
        [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
        2000000000,  # expiry = 18 May 2033
        10 * PERCENT,  # alpha = 0.1
        True,  # put
        1 * PERCENT,  # tradingFee = 1%
    )
    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", 18)

    # give users base tokens
    baseToken.mint(alice, 10000 * SCALE, {"from": deployer})
    baseToken.approve(market, 10000 * SCALE, {"from": alice})
    baseToken.mint(bob, 10000 * SCALE, {"from": deployer})
    baseToken.approve(market, 10000 * SCALE, {"from": bob})

    # buy 2 puts (strike=500)
    market.buy(PUT, 2, 2 * SCALE, 10000 * SCALE, {"from": alice})

    # buy 1 put (strike=600) and 3 covers (strike=400)
    market.buy(PUT, 3, 3 * SCALE, 10000 * SCALE, {"from": bob})
    market.buy(COVER, 1, 3 * SCALE, 10000 * SCALE, {"from": bob})
    market.sell(PUT, 3, 2 * SCALE, 0, {"from": bob})

    fast_forward(2000000000 + 3600)
    market.settle({"from": alice})

    cost = 600 * lslmsr([3, 3, 6, 4, 3], 0.1)
    alicePayoff = 2 * (500 - 444)
    bobPayoff1 = 3 * 400
    bobPayoff2 = 1 * (600 - 444)
    payoff = alicePayoff + bobPayoff1 + bobPayoff2
    assert approx(market.costAtSettlement()) == cost
    assert market.payoffAtSettlement() == payoff * SCALE

    balance = baseToken.balanceOf(market)
    aliceBalance = baseToken.balanceOf(alice)
    tx = market.redeem(PUT, 2, {"from": alice})
    assert approx(tx.return_value) == cost * alicePayoff / payoff
    assert approx(balance - baseToken.balanceOf(market)) == cost * alicePayoff / payoff
    assert (
        approx(baseToken.balanceOf(alice) - aliceBalance) == cost * alicePayoff / payoff
    )
    assert tx.events["Redeemed"] == {
        "account": alice,
        "isLongToken": True,
        "strikeIndex": 2,
        "amount": tx.return_value,
    }

    balance = baseToken.balanceOf(market)
    bobBalance = baseToken.balanceOf(bob)
    tx = market.redeem(COVER, 1, {"from": bob})
    assert approx(tx.return_value) == cost * bobPayoff1 / payoff
    assert approx(balance - baseToken.balanceOf(market)) == cost * bobPayoff1 / payoff
    assert approx(baseToken.balanceOf(bob) - bobBalance) == cost * bobPayoff1 / payoff
    assert tx.events["Redeemed"] == {
        "account": bob,
        "isLongToken": False,
        "strikeIndex": 1,
        "amount": tx.return_value,
    }

    balance = baseToken.balanceOf(market)
    bobBalance = baseToken.balanceOf(bob)
    tx = market.redeem(PUT, 3, {"from": bob})
    assert approx(tx.return_value) == cost * bobPayoff2 / payoff
    assert approx(balance - baseToken.balanceOf(market)) == cost * bobPayoff2 / payoff
    assert approx(baseToken.balanceOf(bob) - bobBalance) == cost * bobPayoff2 / payoff
    assert tx.events["Redeemed"] == {
        "account": bob,
        "isLongToken": True,
        "strikeIndex": 3,
        "amount": tx.return_value,
    }

    balance1 = baseToken.balanceOf(deployer)
    tx = market.skim({"from": deployer})
    assert (
        approx(tx.return_value)
        == 500 * 2 * PERCENT + 600 * 5 * PERCENT + 400 * 3 * PERCENT
    )
    assert (
        approx(baseToken.balanceOf(deployer) - balance1)
        == 500 * 2 * PERCENT + 600 * 5 * PERCENT + 400 * 3 * PERCENT
    )


def test_buy_and_redeem_large_size(
    a, OptionLsLmsr, MockToken, MockOracle, OptionToken, fast_forward
):

    # setup args
    deployer, alice = a[:2]
    baseToken = deployer.deploy(MockToken)
    oracle = deployer.deploy(MockOracle)
    longTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    shortTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    oracle.setPrice(444 * SCALE)

    # deploy and initialize
    market = deployer.deploy(OptionLsLmsr)
    market.initialize(
        baseToken,
        oracle,
        longTokens,
        shortTokens,
        [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
        2000000000,  # expiry = 18 May 2033
        10 * PERCENT,  # alpha = 0.1
        False,  # call
        1 * PERCENT,  # tradingFee = 1%
    )
    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", 18)

    # give users base tokens
    baseToken.mint(alice, 1e20 * SCALE, {"from": deployer})
    baseToken.approve(market, 1e20 * SCALE, {"from": alice})

    # buy, sell, buy large trade
    market.buy(CALL, 3, 1e18 * SCALE, 1e20 * SCALE, {"from": alice})
    market.sell(CALL, 3, 1e18 * SCALE, 0, {"from": alice})
    market.buy(CALL, 3, 1e18 * SCALE, 1e20 * SCALE, {"from": alice})

    # buy, sell, buy large trade
    market.buy(COVER, 0, 1e18 * SCALE, 1e20 * SCALE, {"from": alice})
    market.sell(COVER, 0, 1e18 * SCALE, 0, {"from": alice})
    market.buy(COVER, 0, 1e18 * SCALE, 1e20 * SCALE, {"from": alice})

    fast_forward(2000000000 + 3600)
    market.settle({"from": alice})

    cost = lslmsr([1e18, 0, 0, 0, 1e18], 0.1)
    assert approx(market.costAtSettlement()) == cost

    market.redeem(COVER, 0, {"from": alice})
    market.redeem(CALL, 3, {"from": alice})
    assert approx(baseToken.balanceOf(market)) == 6 * 1e18 * PERCENT
    assert approx(baseToken.balanceOf(alice)) == 1e20 * SCALE - 6 * 1e18 * PERCENT


@pytest.mark.parametrize("isEth", [False, True])
@pytest.mark.parametrize("isPut", [False, True])
def test_emergency_methods(
    a, OptionLsLmsr, MockToken, MockOracle, OptionToken, fast_forward, isEth, isPut
):

    # setup args
    deployer, alice = a[:2]
    baseToken = ZERO_ADDRESS if isEth else deployer.deploy(MockToken)
    oracle = deployer.deploy(MockOracle)
    oracle2 = deployer.deploy(MockOracle)
    longTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    shortTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    oracle.setPrice(444 * SCALE)
    oracle2.setPrice(555 * SCALE)

    # deploy and initialize
    market = deployer.deploy(OptionLsLmsr)
    market.initialize(
        baseToken,
        oracle,
        longTokens,
        shortTokens,
        [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
        2000000000,  # expiry = 18 May 2033
        10 * PERCENT,  # alpha = 0.1
        isPut,
        1 * PERCENT,  # tradingFee = 1%
    )
    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", 18)

    # give users base tokens
    if not isEth:
        baseToken.mint(alice, 100 * SCALE, {"from": deployer})
        baseToken.approve(market, 100 * SCALE, {"from": alice})

    # pause and unpause
    with reverts("Ownable: caller is not the owner"):
        market.pause({"from": alice})
    market.pause({"from": deployer})

    with reverts("This method has been paused"):
        market.buy(
            CALL, 0, 1 * PERCENT, 100 * SCALE, {"from": alice, "value": 50 * SCALE}
        )

    with reverts("Ownable: caller is not the owner"):
        market.unpause({"from": alice})
    market.unpause({"from": deployer})
    market.buy(CALL, 0, 1 * PERCENT, 100 * SCALE, {"from": alice, "value": 50 * SCALE})

    # change oracle and expiry
    with reverts("Ownable: caller is not the owner"):
        market.setOracle(oracle2, {"from": alice})
    with reverts("Ownable: caller is not the owner"):
        market.setExpiryTime(2000000000 - 1, {"from": alice})

    market.setOracle(oracle2, {"from": deployer})
    assert market.oracle() == oracle2

    market.setExpiryTime(2000000000 - 1, {"from": deployer})
    assert market.expiryTime() == 2000000000 - 1

    # dispute expiry price
    fast_forward(2000000000)
    with reverts("Ownable: caller is not the owner"):
        market.disputeExpiryPrice(666 * SCALE, {"from": alice})
    with reverts("Cannot be called before settlement"):
        market.disputeExpiryPrice(666 * SCALE, {"from": deployer})

    market.settle({"from": alice})
    market.disputeExpiryPrice(666 * SCALE, {"from": deployer})
    assert market.expiryPrice() == 666 * SCALE

    fast_forward(2000000000 + 3600)
    with reverts("Not dispute period"):
        market.disputeExpiryPrice(777 * SCALE, {"from": deployer})

    # change owner
    with reverts("Ownable: caller is not the owner"):
        market.transferOwnership(alice, {"from": alice})

    market.transferOwnership(alice, {"from": deployer})
    assert market.owner() == alice


@pytest.mark.parametrize("isEth", [False, True])
def test_cannot_sell_when_amount_out_lower_than_fee(
    a, OptionLsLmsr, MockToken, MockOracle, OptionToken, fast_forward, isEth
):

    # setup args
    deployer, alice = a[:2]
    baseToken = ZERO_ADDRESS if isEth else deployer.deploy(MockToken)
    oracle = deployer.deploy(MockOracle)
    longTokens = [deployer.deploy(OptionToken) for _ in range(3)]
    shortTokens = [deployer.deploy(OptionToken) for _ in range(3)]

    def getBalance(wallet):
        return wallet.balance() if isEth else baseToken.balanceOf(wallet)

    # deploy and initialize
    market = deployer.deploy(OptionLsLmsr)
    market.initialize(
        baseToken,
        oracle,
        longTokens,
        shortTokens,
        [400 * SCALE, 500 * SCALE, 600 * SCALE],
        2000000000,  # expiry = 18 May 2033
        60682615108455816,  # max loss = 0.2
        False,  # call
        10 * PERCENT,  # tradingFee = 10%
    )
    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", 18)

    # give users base tokens
    if not isEth:
        baseToken.mint(alice, 100 * SCALE, {"from": deployer})
        baseToken.approve(market, 100 * SCALE, {"from": alice})
    value = 50 * SCALE if isEth else 0

    # buy 1 call
    market.buy(CALL, 2, 1 * SCALE, 100 * SCALE, {"from": alice, "value": value})

    # buy 3 covers
    market.buy(COVER, 2, 3 * SCALE, 100 * SCALE, {"from": alice, "value": value})

    # sell the call
    with reverts("Amount out must be > 0"):
        market.sell(CALL, 2, 1 * SCALE, 0, {"from": alice})
