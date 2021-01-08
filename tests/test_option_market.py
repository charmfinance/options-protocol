from brownie import reverts
import pytest
from pytest import approx


SCALE = 10 ** 18
PERCENT = SCALE // 100
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

CALL = PUT = True
COVER = False


def lmsr(q, b):
    from math import exp, log

    mx = max(q)
    a = sum(exp((x - mx) / b) for x in q)
    return mx + b * log(a)


@pytest.mark.parametrize("isEth", [False, True])
@pytest.mark.parametrize("isPut", [False, True])
@pytest.mark.parametrize("tradingFee", [0, 10 * PERCENT, SCALE - 1])
@pytest.mark.parametrize("balanceCap", [0, 40 * SCALE])
@pytest.mark.parametrize("disputePeriod", [0, 3600])
def test_initialize(
    a,
    OptionMarket,
    MockToken,
    MockOracle,
    OptionToken,
    isEth,
    isPut,
    tradingFee,
    balanceCap,
    disputePeriod,
):

    # setup args
    deployer = a[0]
    baseToken = ZERO_ADDRESS if isEth else deployer.deploy(MockToken)
    oracle = deployer.deploy(MockOracle)
    longTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    shortTokens = [deployer.deploy(OptionToken) for _ in range(4)]

    # deploy and initialize
    market = deployer.deploy(OptionMarket)
    market.initialize(
        baseToken,
        oracle,
        longTokens,
        shortTokens,
        [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
        2000000000,  # expiry = 18 May 2033
        isPut,
        tradingFee,
        balanceCap,
        disputePeriod,
    )

    # check variables all set
    assert market.baseToken() == baseToken
    assert market.oracle() == oracle
    assert market.expiryTime() == 2000000000
    assert market.b() == 0
    assert market.isPut() == isPut
    assert market.tradingFee() == tradingFee
    assert market.balanceCap() == balanceCap
    assert market.disputePeriod() == disputePeriod
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
            isPut,
            tradingFee,
            balanceCap,
            disputePeriod,
        )


@pytest.mark.parametrize("isPut", [False, True])
@pytest.mark.parametrize("isEth", [False, True])
def test_initialize_errors(
    a, OptionMarket, MockToken, MockOracle, OptionToken, isPut, isEth
):

    # setup args
    deployer = a[0]
    baseToken = ZERO_ADDRESS if isEth else deployer.deploy(MockToken)
    oracle = deployer.deploy(MockOracle)
    longTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    shortTokens = [deployer.deploy(OptionToken) for _ in range(4)]

    market = deployer.deploy(OptionMarket)
    with reverts("Trading fee must be < 1"):
        market.initialize(
            baseToken,
            oracle,
            longTokens,
            shortTokens,
            [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
            2000000000,  # expiry = 18 May 2033
            isPut,
            SCALE,  # trading fee = 100%
            40 * SCALE,  # balance cap = 40
            3600,  # dispute period = 1 hour
        )

    market = deployer.deploy(OptionMarket)
    with reverts("Already expired"):
        market.initialize(
            baseToken,
            oracle,
            longTokens,
            shortTokens,
            [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
            1500000000,  # expiry = 14 July 2017
            isPut,
            1e16,  # trading fee = 1%
            40 * SCALE,  # balance cap = 40
            3600,  # dispute period = 1 hour
        )

    market = deployer.deploy(OptionMarket)
    with reverts("Lengths do not match"):
        market.initialize(
            baseToken,
            oracle,
            longTokens[:3],
            shortTokens,
            [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
            2000000000,  # expiry = 18 May 2033
            isPut,
            1e16,  # trading fee = 1%
            40 * SCALE,  # balance cap = 40
            3600,  # dispute period = 1 hour
        )

    market = deployer.deploy(OptionMarket)
    with reverts("Lengths do not match"):
        market.initialize(
            baseToken,
            oracle,
            longTokens,
            shortTokens[:3],
            [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
            2000000000,  # expiry = 18 May 2033
            isPut,
            1e16,  # trading fee = 1%
            40 * SCALE,  # balance cap = 40
            3600,  # dispute period = 1 hour
        )

    market = deployer.deploy(OptionMarket)
    with reverts("Strike prices must not be empty"):
        market.initialize(
            baseToken,
            oracle,
            [],
            [],
            [],
            2000000000,  # expiry = 18 May 2033
            isPut,
            1e16,  # trading fee = 1%
            40 * SCALE,  # balance cap = 40
            3600,  # dispute period = 1 hour
        )

    market = deployer.deploy(OptionMarket)
    with reverts("Strike prices must be > 0"):
        market.initialize(
            baseToken,
            oracle,
            longTokens,
            shortTokens,
            [0, 400 * SCALE, 500 * SCALE, 600 * SCALE],
            2000000000,  # expiry = 18 May 2033
            isPut,
            1e16,  # trading fee = 1%
            40 * SCALE,  # balance cap = 40
            3600,  # dispute period = 1 hour
        )

    market = deployer.deploy(OptionMarket)
    with reverts("Strike prices must be increasing"):
        market.initialize(
            baseToken,
            oracle,
            longTokens,
            shortTokens,
            [300 * SCALE, 400 * SCALE, 500 * SCALE, 500 * SCALE],
            2000000000,  # expiry = 18 May 2033
            isPut,
            1e16,  # trading fee = 1%
            40 * SCALE,  # balance cap = 40
            3600,  # dispute period = 1 hour
        )


@pytest.mark.parametrize("isEth", [False, True])
@pytest.mark.parametrize("balanceCap", [0, 40 * SCALE])
def test_increase_b(
    a,
    OptionMarket,
    MockToken,
    MockOracle,
    OptionToken,
    fast_forward,
    isEth,
    balanceCap,
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
    market = deployer.deploy(OptionMarket)
    market.initialize(
        baseToken,
        oracle,
        longTokens,
        shortTokens,
        [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
        2000000000,  # expiry = 18 May 2033
        False,  # call
        1 * PERCENT,  # trading fee = 1%
        balanceCap,
        3600,  # dispute period = 1 hour
    )
    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", 18)

    # give deployer and user base tokens
    if not isEth:
        baseToken.mint(deployer, 100 * SCALE, {"from": deployer})
        baseToken.approve(market, 100 * SCALE, {"from": deployer})
        baseToken.mint(alice, 100 * SCALE, {"from": deployer})
        baseToken.approve(market, 100 * SCALE, {"from": alice})
    valueDict = {"value": 50 * SCALE} if isEth else {}

    # can't trade before setting b
    with reverts("Cannot be called before b is set"):
        market.buy(CALL, 4, SCALE, 100 * SCALE, {"from": alice, **valueDict})

    # only owner
    with reverts("Ownable: caller is not the owner"):
        market.increaseB(
            100 * SCALE,
            {"from": alice, **valueDict},
        )

    # not enough balance
    if isEth:
        with reverts("UniERC20: not enough value"):
            market.increaseB(
                100 * SCALE,
                {"from": deployer, **valueDict},
            )
    else:
        with reverts("ERC20: transfer amount exceeds balance"):
            market.increaseB(
                100 * SCALE,
                {"from": deployer, **valueDict},
            )

    # can increase b
    tx = market.increaseB(
        10 * SCALE,
        {"from": deployer, **valueDict},
    )
    assert approx(tx.return_value) == SCALE * lmsr([0, 0, 0, 0, 0], 10)
    assert approx(getBalance(deployer)) == 100 * SCALE - tx.return_value
    assert approx(tx.return_value) == SCALE * lmsr([0, 0, 0, 0, 0], 10)
    assert tx.events["UpdatedB"] == {
        "b": 10 * SCALE,
        "cost": tx.return_value,
    }

    # can't decrease b
    with reverts("New b must be higher"):
        market.increaseB(
            9 * SCALE,
            {"from": deployer, **valueDict},
        )

    # but can increase b
    tx = market.increaseB(
        15 * SCALE,
        {"from": deployer, **valueDict},
    )
    assert approx(tx.return_value) == SCALE * lmsr([0, 0, 0, 0, 0], 15) - SCALE * lmsr(
        [0, 0, 0, 0, 0], 10
    )
    assert approx(tx.return_value) == SCALE * (
        lmsr([0, 0, 0, 0, 0], 15) - lmsr([0, 0, 0, 0, 0], 10)
    )
    assert tx.events["UpdatedB"] == {
        "b": 15 * SCALE,
        "cost": tx.return_value,
    }

    # can trade now
    market.buy(CALL, 3, SCALE, 100 * SCALE, {"from": alice, **valueDict})

    # can't increase b beyond balance cap
    if balanceCap > 0:
        with reverts("Balance cap exceeded"):
            market.increaseB(
                25 * SCALE,
                {"from": deployer, **valueDict},
            )

    # no balance cap
    else:
        market.increaseB(
            25 * SCALE,
            {"from": deployer, **valueDict},
        )


@pytest.mark.parametrize("balanceCap", [0, 5000 * 1e6])
def test_increase_b_puts(
    a,
    OptionMarket,
    MockToken,
    MockOracle,
    OptionToken,
    fast_forward,
    balanceCap,
):

    # setup args
    deployer, alice = a[:2]
    baseToken = deployer.deploy(MockToken)
    baseToken.setDecimals(6)
    oracle = deployer.deploy(MockOracle)
    longTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    shortTokens = [deployer.deploy(OptionToken) for _ in range(4)]

    # deploy and initialize
    market = deployer.deploy(OptionMarket)
    market.initialize(
        baseToken,
        oracle,
        longTokens,
        shortTokens,
        [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
        2000000000,  # expiry = 18 May 2033
        True,  # put
        1 * PERCENT,  # trading fee = 1%
        balanceCap,
        3600,  # dispute period = 1 hour
    )
    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", 18)

    # give deployer and user base tokens
    baseToken.mint(deployer, 100000 * 1e6, {"from": deployer})
    baseToken.approve(market, 100000 * 1e6, {"from": deployer})
    baseToken.mint(alice, 100000 * 1e6, {"from": deployer})
    baseToken.approve(market, 100000 * 1e6, {"from": alice})

    # not enough balance
    with reverts("ERC20: transfer amount exceeds balance"):
        market.increaseB(
            70000 * 1e6,
            {"from": deployer},
        )

    # can increase b
    tx = market.increaseB(
        10 * 1e6,
        {"from": deployer},
    )
    assert approx(tx.return_value) == lmsr([0, 0, 0, 0, 0], 10) * 1e6
    assert approx(baseToken.balanceOf(deployer)) == 100000 * 1e6 - tx.return_value
    assert tx.events["UpdatedB"] == {
        "b": 10 * 1e6,
        "cost": tx.return_value,
    }

    # can't decrease b
    with reverts("New b must be higher"):
        market.increaseB(
            9 * 1e6,
            {"from": deployer},
        )

    # but can increase b
    tx = market.increaseB(
        15 * 1e6,
        {"from": deployer},
    )
    assert approx(tx.return_value) == 1e6 * lmsr([0, 0, 0, 0, 0], 15) - 1e6 * lmsr(
        [0, 0, 0, 0, 0], 10
    )
    assert tx.events["UpdatedB"] == {
        "b": 15 * 1e6,
        "cost": tx.return_value,
    }

    # can trade now
    market.buy(PUT, 1, 1e6, 10000 * 1e6, {"from": alice})

    # can't increase b beyond balance cap
    if balanceCap > 0:
        with reverts("Balance cap exceeded"):
            market.increaseB(
                40000 * 1e6,
                {"from": deployer},
            )

    # no balance cap
    else:
        market.increaseB(
            40000 * 1e6,
            {"from": deployer},
        )


@pytest.mark.parametrize("isEth", [False, True])
@pytest.mark.parametrize("balanceCap", [0, 40 * SCALE])
def test_buy_and_sell_calls(
    a,
    OptionMarket,
    MockToken,
    MockOracle,
    OptionToken,
    fast_forward,
    isEth,
    balanceCap,
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
    market = deployer.deploy(OptionMarket)
    market.initialize(
        baseToken,
        oracle,
        longTokens,
        shortTokens,
        [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
        2000000000,  # expiry = 18 May 2033
        False,  # call
        1 * PERCENT,  # trading fee = 1%
        balanceCap,
        3600,  # dispute period = 1 hour
    )
    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", 18)

    # give users base tokens
    if not isEth:
        baseToken.mint(deployer, 100 * SCALE, {"from": deployer})
        baseToken.approve(market, 100 * SCALE, {"from": deployer})
        baseToken.mint(alice, 100 * SCALE, {"from": deployer})
        baseToken.approve(market, 100 * SCALE, {"from": alice})
    valueDict = {"value": 50 * SCALE} if isEth else {}

    # needs to call increaseB
    market.increaseB(
        10 * SCALE,
        {"from": deployer, **valueDict},
    )

    # index out of range
    with reverts("Index too large"):
        market.buy(CALL, 4, SCALE, 100 * SCALE, {"from": alice, **valueDict})
    with reverts("Index too large"):
        market.buy(COVER, 4, SCALE, 100 * SCALE, {"from": alice, **valueDict})

    # can't buy too much
    if isEth:
        with reverts("UniERC20: not enough value"):
            market.buy(CALL, 0, 120 * SCALE, 10000 * SCALE, {"from": alice})
    else:
        with reverts("ERC20: transfer amount exceeds balance"):
            tx = market.buy(CALL, 0, 120 * SCALE, 10000 * SCALE, {"from": alice})

    initial = SCALE * lmsr([0, 0, 0, 0, 0], 10)

    # buy 2 calls
    cost = SCALE * lmsr([0, 2, 2, 2, 2], 10)
    assert approx(market.calcBuyAmountAndFee(CALL, 0, 2 * SCALE)) == (
        cost - initial,
        2 * PERCENT,
    )

    cost = SCALE * lmsr([0, 2, 2, 2, 2], 10) + 2 * PERCENT
    tx = market.buy(CALL, 0, 2 * SCALE, 100 * SCALE, {"from": alice, **valueDict})
    assert approx(tx.return_value) == cost - initial
    assert approx(getBalance(alice)) == 100 * SCALE - cost + initial
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
    cost1 = SCALE * lmsr([0, 2, 2, 2, 2], 10)
    cost2 = SCALE * lmsr([0, 2, 2, 5, 5], 10)
    assert approx(market.calcBuyAmountAndFee(CALL, 2, 3 * SCALE)) == (
        cost2 - cost1,
        3 * PERCENT,
    )

    cost1 = SCALE * lmsr([0, 2, 2, 2, 2], 10) + 2 * PERCENT
    cost2 = SCALE * lmsr([0, 2, 2, 5, 5], 10) + 5 * PERCENT
    tx = market.buy(CALL, 2, 3 * SCALE, 100 * SCALE, {"from": alice, **valueDict})
    assert approx(tx.return_value) == cost2 - cost1
    assert approx(getBalance(alice)) == 100 * SCALE - cost2 + initial
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
    cost1 = SCALE * lmsr([0, 2, 2, 5, 5], 10)
    cost2 = SCALE * lmsr([5, 7, 7, 10, 5], 10)
    assert approx(market.calcBuyAmountAndFee(COVER, 3, 5 * SCALE)) == (
        cost2 - cost1,
        5 * PERCENT,
    )

    cost1 = SCALE * lmsr([0, 2, 2, 5, 5], 10) + 5 * PERCENT
    cost2 = SCALE * lmsr([5, 7, 7, 10, 5], 10) + 10 * PERCENT
    tx = market.buy(COVER, 3, 5 * SCALE, 100 * SCALE, {"from": alice, **valueDict})
    assert approx(tx.return_value) == cost2 - cost1
    assert approx(getBalance(alice)) == 100 * SCALE - cost2 + initial
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
    cost1 = SCALE * lmsr([5, 7, 7, 10, 5], 10)
    cost2 = SCALE * lmsr([11, 7, 7, 10, 5], 10)
    assert approx(market.calcBuyAmountAndFee(COVER, 0, 6 * SCALE)) == (
        cost2 - cost1,
        6 * PERCENT,
    )

    cost1 = SCALE * lmsr([5, 7, 7, 10, 5], 10) + 10 * PERCENT
    cost2 = SCALE * lmsr([11, 7, 7, 10, 5], 10) + 16 * PERCENT
    tx = market.buy(COVER, 0, 6 * SCALE, 100 * SCALE, {"from": alice, **valueDict})
    assert approx(tx.return_value) == cost2 - cost1
    assert approx(getBalance(alice)) == 100 * SCALE - cost2 + initial
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

    # sell 2 covers
    cost1 = SCALE * lmsr([11, 7, 7, 10, 5], 10)
    cost2 = SCALE * lmsr([9, 7, 7, 10, 5], 10)
    assert approx(market.calcSellAmountAndFee(COVER, 0, 2 * SCALE)) == (
        cost1 - cost2,
        0,
    )

    cost1 = SCALE * lmsr([11, 7, 7, 10, 5], 10) + 16 * PERCENT
    cost2 = SCALE * lmsr([9, 7, 7, 10, 5], 10) + 16 * PERCENT
    tx = market.sell(COVER, 0, 2 * SCALE, 0, {"from": alice})
    assert approx(tx.return_value) == cost1 - cost2
    assert approx(getBalance(alice)) == 100 * SCALE - cost2 + initial
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
    cost1 = SCALE * lmsr([9, 7, 7, 10, 5], 10)
    cost2 = SCALE * lmsr([9, 5, 5, 8, 3], 10)
    assert approx(market.calcSellAmountAndFee(CALL, 0, 2 * SCALE)) == (cost1 - cost2, 0)

    cost1 = SCALE * lmsr([9, 7, 7, 10, 5], 10) + 16 * PERCENT
    cost2 = SCALE * lmsr([9, 5, 5, 8, 3], 10) + 16 * PERCENT
    tx = market.sell(CALL, 0, 2 * SCALE, 0, {"from": alice})
    assert approx(tx.return_value) == cost1 - cost2
    assert approx(getBalance(alice)) == 100 * SCALE - cost2 + initial
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
    cost1 = SCALE * lmsr([9, 5, 5, 8, 3], 10)
    cost2 = SCALE * lmsr([9, 5, 5, 5, 0], 10)
    assert approx(market.calcSellAmountAndFee(CALL, 2, 3 * SCALE)) == (cost1 - cost2, 0)

    cost1 = SCALE * lmsr([9, 5, 5, 8, 3], 10) + 16 * PERCENT
    cost2 = SCALE * lmsr([9, 5, 5, 5, 0], 10) + 16 * PERCENT
    tx = market.sell(CALL, 2, 3 * SCALE, 0, {"from": alice})
    assert approx(tx.return_value) == cost1 - cost2
    assert approx(getBalance(alice)) == 100 * SCALE - cost2 + initial
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
    cost1 = SCALE * lmsr([9, 5, 5, 5, 0], 10)
    cost2 = SCALE * lmsr([4, 0, 0, 0, 0], 10)
    assert approx(market.calcSellAmountAndFee(COVER, 3, 5 * SCALE)) == (
        cost1 - cost2,
        0,
    )

    cost1 = SCALE * lmsr([9, 5, 5, 5, 0], 10) + 16 * PERCENT
    cost2 = SCALE * lmsr([4, 0, 0, 0, 0], 10) + 16 * PERCENT
    tx = market.sell(COVER, 3, 5 * SCALE, 0, {"from": alice})
    assert approx(tx.return_value) == cost1 - cost2
    assert approx(getBalance(alice)) == 100 * SCALE - cost2 + initial
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
    cost1 = SCALE * lmsr([4, 0, 0, 0, 0], 10)
    cost2 = SCALE * lmsr([0, 0, 0, 0, 0], 10)
    assert approx(market.calcSellAmountAndFee(COVER, 0, 4 * SCALE)) == (
        cost1 - cost2,
        0,
    )

    cost1 = SCALE * lmsr([4, 0, 0, 0, 0], 10) + 16 * PERCENT
    cost2 = SCALE * lmsr([0, 0, 0, 0, 0], 10) + 16 * PERCENT
    tx = market.sell(COVER, 0, 4 * SCALE, 0, {"from": alice})
    assert approx(tx.return_value) == cost1 - cost2
    assert approx(getBalance(alice)) == 100 * SCALE - cost2 + initial
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

    # can't buy beyond balance cap
    if balanceCap > 0:
        with reverts("Balance cap exceeded"):
            tx = market.buy(
                COVER, 0, 40 * SCALE, 1000 * SCALE, {"from": alice, **valueDict}
            )

    # no balance cap
    else:
        tx = market.buy(
            COVER, 0, 40 * SCALE, 1000 * SCALE, {"from": alice, **valueDict}
        )

    # cannot buy or sell after expiry
    fast_forward(2000000000)
    with reverts("Already expired"):
        market.buy(CALL, 1, 1 * SCALE, 100 * SCALE, {"from": alice})
    with reverts("Already expired"):
        market.sell(COVER, 2, 1 * SCALE, 0, {"from": alice})


@pytest.mark.parametrize("balanceCap", [0, 40000 * 1e6])
def test_buy_and_sell_puts(
    a, OptionMarket, MockToken, MockOracle, OptionToken, balanceCap
):

    # setup args
    deployer, alice = a[:2]
    baseToken = deployer.deploy(MockToken)
    baseToken.setDecimals(6)
    oracle = deployer.deploy(MockOracle)
    longTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    shortTokens = [deployer.deploy(OptionToken) for _ in range(4)]

    # deploy and initialize
    market = deployer.deploy(OptionMarket)
    market.initialize(
        baseToken,
        oracle,
        longTokens,
        shortTokens,
        [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
        2000000000,  # expiry = 18 May 2033
        True,  # put
        1 * PERCENT,  # trading fee = 1%
        balanceCap,
        3600,  # dispute period = 1 hour
    )
    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", 18)

    # give users base tokens
    baseToken.mint(deployer, 100000 * 1e6, {"from": deployer})
    baseToken.approve(market, 100000 * 1e6, {"from": deployer})
    baseToken.mint(alice, 100000 * 1e6, {"from": deployer})
    baseToken.approve(market, 100000 * 1e6, {"from": alice})

    # needs to call increaseB
    market.increaseB(1000 * 1e6, {"from": deployer})

    # index out of range
    with reverts("Index too large"):
        tx = market.buy(PUT, 4, 1e6, 100 * 1e6, {"from": alice})
    with reverts("Index too large"):
        tx = market.buy(COVER, 4, 1e6, 100 * 1e6, {"from": alice})

    # can't buy too much
    with reverts("ERC20: transfer amount exceeds balance"):
        market.buy(PUT, 0, 1000 * 1e6, 1000000 * 1e6, {"from": alice})

    initial = 1e6 * lmsr([0, 0, 0, 0, 0], 1000)

    # buy 2 puts
    cost = lmsr([2 * 300, 0, 0, 0, 0], 1000) * 1e6
    assert approx(market.calcBuyAmountAndFee(PUT, 0, 2 * 1e6)) == (
        cost - initial,
        300 * 2 * 1e4,
    )

    cost = lmsr([2 * 300, 0, 0, 0, 0], 1000) * 1e6 + 300 * 2 * 1e4
    tx = market.buy(PUT, 0, 2 * 1e6, 10000 * 1e6, {"from": alice})
    assert approx(tx.return_value, rel=1e-5) == cost - initial
    assert approx(baseToken.balanceOf(alice), rel=1e-5) == 100000 * 1e6 - cost + initial
    assert longTokens[0].balanceOf(alice) == 2 * 1e6
    assert tx.events["Trade"] == {
        "account": alice,
        "isBuy": True,
        "isLongToken": True,
        "strikeIndex": 0,
        "size": 2 * 1e6,
        "cost": tx.return_value,
        "newSupply": 2 * 1e6,
    }

    # buy 5 covers
    cost1 = lmsr([2 * 300, 0, 0, 0, 0], 1000) * 1e6
    cost2 = lmsr([2 * 300, 0, 0, 5 * 500, 5 * 500], 1000) * 1e6
    assert approx(market.calcBuyAmountAndFee(COVER, 2, 5 * 1e6)) == (
        cost2 - cost1,
        500 * 5 * 1e4,
    )

    cost1 = lmsr([2 * 300, 0, 0, 0, 0], 1000) * 1e6 + 300 * 2 * 1e4
    cost2 = (
        lmsr([2 * 300, 0, 0, 5 * 500, 5 * 500], 1000) * 1e6
        + 300 * 2 * 1e4
        + 500 * 5 * 1e4
    )
    tx = market.buy(COVER, 2, 5 * 1e6, 10000 * 1e6, {"from": alice})
    assert approx(tx.return_value) == cost2 - cost1
    assert approx(baseToken.balanceOf(alice)) == 100000 * 1e6 - cost2 + initial
    assert longTokens[0].balanceOf(alice) == 2 * 1e6
    assert shortTokens[2].balanceOf(alice) == 5 * 1e6
    assert tx.events["Trade"] == {
        "account": alice,
        "isBuy": True,
        "isLongToken": False,
        "strikeIndex": 2,
        "size": 5 * 1e6,
        "cost": tx.return_value,
        "newSupply": 5 * 1e6,
    }

    # can't sell more than you have
    with reverts("ERC20: burn amount exceeds balance"):
        market.sell(CALL, 0, 3 * 1e6, 0, {"from": alice})
    with reverts("ERC20: burn amount exceeds balance"):
        market.sell(COVER, 1, 1 * 1e6, 0, {"from": alice})

    # sell 2 covers
    cost1 = lmsr([2 * 300, 0, 0, 5 * 500, 5 * 500], 1000) * 1e6
    cost2 = lmsr([2 * 300, 0, 0, 3 * 500, 3 * 500], 1000) * 1e6
    assert approx(market.calcSellAmountAndFee(COVER, 2, 2 * 1e6)) == (cost1 - cost2, 0)

    cost1 = (
        lmsr([2 * 300, 0, 0, 5 * 500, 5 * 500], 1000) * 1e6
        + 300 * 2 * 1e4
        + 500 * 5 * 1e4
    )
    cost2 = (
        lmsr([2 * 300, 0, 0, 3 * 500, 3 * 500], 1000) * 1e6
        + 300 * 2 * 1e4
        + 500 * 5 * 1e4
    )
    tx = market.sell(COVER, 2, 2 * 1e6, 0, {"from": alice})
    assert approx(tx.return_value) == cost1 - cost2
    assert approx(baseToken.balanceOf(alice)) == 100000 * 1e6 - cost2 + initial
    assert longTokens[0].balanceOf(alice) == 2 * 1e6
    assert shortTokens[2].balanceOf(alice) == 3 * 1e6
    assert tx.events["Trade"] == {
        "account": alice,
        "isBuy": False,
        "isLongToken": False,
        "strikeIndex": 2,
        "size": 2 * 1e6,
        "cost": tx.return_value,
        "newSupply": 3 * 1e6,
    }

    # can't buy beyond balance cap
    if balanceCap > 0:
        with reverts("Balance cap exceeded"):
            tx = market.buy(COVER, 0, 150 * 1e6, 100000 * 1e6, {"from": alice})

    # no balance cap
    else:
        tx = market.buy(COVER, 0, 150 * 1e6, 100000 * 1e6, {"from": alice})


@pytest.mark.parametrize("isEth", [False, True])
@pytest.mark.parametrize("isPut", [False, True])
def test_settle(
    a, OptionMarket, MockToken, MockOracle, OptionToken, fast_forward, isEth, isPut
):

    # setup args
    deployer, alice = a[:2]
    baseToken = ZERO_ADDRESS if isEth else deployer.deploy(MockToken)
    oracle = deployer.deploy(MockOracle)
    longTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    shortTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    oracle.setPrice(444 * SCALE)

    # deploy and initialize
    market = deployer.deploy(OptionMarket)
    market.initialize(
        baseToken,
        oracle,
        longTokens,
        shortTokens,
        [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
        2000000000,  # expiry = 18 May 2033
        isPut,
        1 * PERCENT,  # trading fee = 1%
        40000 * SCALE,  # balance cap = 40000
        3600,  # dispute period = 1 hour
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
    a, OptionMarket, MockToken, MockOracle, OptionToken, fast_forward, isEth
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
    market = deployer.deploy(OptionMarket)
    market.initialize(
        baseToken,
        oracle,
        longTokens,
        shortTokens,
        [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
        2000000000,  # expiry = 18 May 2033
        False,  # call
        1 * PERCENT,  # trading fee = 1%
        40000 * SCALE,  # balance cap = 40000
        3600,  # dispute period = 1 hour
    )
    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", 18)

    # give users base tokens
    if not isEth:
        baseToken.mint(deployer, 100 * SCALE, {"from": deployer})
        baseToken.approve(market, 100 * SCALE, {"from": deployer})
        baseToken.mint(alice, 100 * SCALE, {"from": deployer})
        baseToken.approve(market, 100 * SCALE, {"from": alice})
        baseToken.mint(bob, 100 * SCALE, {"from": deployer})
        baseToken.approve(market, 100 * SCALE, {"from": bob})
    valueDict = {"value": 50 * SCALE} if isEth else {}

    # needs to call increaseB
    market.increaseB(
        10 * SCALE,
        {"from": deployer, **valueDict},
    )

    # buy 2 calls (strike=300)
    market.buy(CALL, 0, 2 * SCALE, 100 * SCALE, {"from": alice, **valueDict})

    # buy 1 call (strike=600) and 3 covers (strike=400)
    market.buy(CALL, 3, 3 * SCALE, 100 * SCALE, {"from": bob, **valueDict})
    market.buy(COVER, 1, 3 * SCALE, 100 * SCALE, {"from": bob, **valueDict})
    market.sell(CALL, 3, 2 * SCALE, 0, {"from": bob})

    with reverts("Cannot be called before expiry"):
        market.redeem(CALL, 0, {"from": alice})

    fast_forward(2000000000)
    with reverts("Cannot be called before settlement"):
        market.redeem(CALL, 0, {"from": alice})

    market.settle({"from": alice})
    with reverts("Cannot be called during dispute period"):
        market.redeem(CALL, 0, {"from": alice})

    cost = SCALE * lmsr([3, 5, 2, 2, 3], 10)
    assert approx(market.currentCumulativeCost()) == cost

    fast_forward(2000000000 + 3600)

    alicePayoff = 2 * (444 - 300)
    bobPayoff = 3 * 400

    balance = getBalance(market)
    aliceBalance = getBalance(alice)
    assert approx(market.calcRedeemAmountAndFee(CALL, 0, {"from": alice})) == (
        alicePayoff * SCALE / 444,
        0,
    )

    tx = market.redeem(CALL, 0, {"from": alice})
    assert approx(tx.return_value) == alicePayoff * SCALE / 444
    assert approx(balance - getBalance(market)) == alicePayoff * SCALE / 444
    assert approx(getBalance(alice) - aliceBalance) == alicePayoff * SCALE / 444
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
    assert approx(market.calcRedeemAmountAndFee(CALL, 3, {"from": bob})) == (0, 0)

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
    assert approx(market.calcRedeemAmountAndFee(COVER, 1, {"from": bob})) == (
        bobPayoff * SCALE / 444,
        0,
    )

    tx = market.redeem(COVER, 1, {"from": bob})
    assert approx(tx.return_value) == bobPayoff * SCALE / 444
    assert approx(balance - getBalance(market)) == bobPayoff * SCALE / 444
    assert approx(getBalance(bob) - bobBalance) == bobPayoff * SCALE / 444
    assert tx.events["Redeemed"] == {
        "account": bob,
        "isLongToken": False,
        "strikeIndex": 1,
        "amount": tx.return_value,
    }

    feesAccrued = 8 * PERCENT + cost - (alicePayoff + bobPayoff) * SCALE / 444
    assert approx(market.calcFeesAccrued()) == feesAccrued

    balance1 = getBalance(deployer)
    tx = market.collectFees({"from": deployer})
    assert approx(tx.return_value) == feesAccrued
    assert approx(getBalance(deployer) - balance1) == feesAccrued
    assert market.calcFeesAccrued() == 0


def test_redeem_puts(a, OptionMarket, MockToken, MockOracle, OptionToken, fast_forward):

    # setup args
    deployer, alice, bob = a[:3]
    baseToken = deployer.deploy(MockToken)
    baseToken.setDecimals(6)
    oracle = deployer.deploy(MockOracle)
    longTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    shortTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    oracle.setPrice(444 * SCALE)

    # deploy and initialize
    market = deployer.deploy(OptionMarket)
    market.initialize(
        baseToken,
        oracle,
        longTokens,
        shortTokens,
        [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
        2000000000,  # expiry = 18 May 2033
        True,  # put
        1 * PERCENT,  # trading fee = 1%
        40000 * 1e6,  # balance cap = 40000
        3600,  # dispute period = 1 hour
    )
    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", 18)

    # give users base tokens
    baseToken.mint(deployer, 10000 * 1e6, {"from": deployer})
    baseToken.approve(market, 10000 * 1e6, {"from": deployer})
    baseToken.mint(alice, 10000 * 1e6, {"from": deployer})
    baseToken.approve(market, 10000 * 1e6, {"from": alice})
    baseToken.mint(bob, 10000 * 1e6, {"from": deployer})
    baseToken.approve(market, 10000 * 1e6, {"from": bob})

    # needs to call increaseB
    market.increaseB(1000 * 1e6, {"from": deployer})

    # buy 2 puts (strike=500)
    market.buy(PUT, 2, 2 * 1e6, 10000 * 1e6, {"from": alice})

    # buy 1 put (strike=600) and 3 covers (strike=400)
    market.buy(PUT, 3, 3 * 1e6, 10000 * 1e6, {"from": bob})
    market.buy(COVER, 1, 3 * 1e6, 10000 * 1e6, {"from": bob})
    market.sell(PUT, 3, 2 * 1e6, 0, {"from": bob})

    cost = (
        lmsr(
            [
                2 * 500 + 1 * 600,
                2 * 500 + 1 * 600,
                2 * 500 + 1 * 600 + 3 * 400,
                1 * 600 + 3 * 400,
                3 * 400,
            ],
            1000,
        )
        * 1e6
    )
    assert approx(market.currentCumulativeCost()) == cost

    fast_forward(2000000000 + 3600)
    market.settle({"from": alice})

    alicePayoff = 2 * (500 - 444)
    bobPayoff1 = 3 * 400
    bobPayoff2 = 1 * (600 - 444)

    balance = baseToken.balanceOf(market)
    aliceBalance = baseToken.balanceOf(alice)
    assert approx(market.calcRedeemAmountAndFee(PUT, 2, {"from": alice})) == (
        alicePayoff * 1e6,
        0,
    )

    tx = market.redeem(PUT, 2, {"from": alice})
    assert approx(tx.return_value) == alicePayoff * 1e6
    assert approx(balance - baseToken.balanceOf(market)) == alicePayoff * 1e6
    assert approx(baseToken.balanceOf(alice) - aliceBalance) == alicePayoff * 1e6
    assert tx.events["Redeemed"] == {
        "account": alice,
        "isLongToken": True,
        "strikeIndex": 2,
        "amount": tx.return_value,
    }

    balance = baseToken.balanceOf(market)
    bobBalance = baseToken.balanceOf(bob)
    assert approx(market.calcRedeemAmountAndFee(COVER, 1, {"from": bob})) == (
        bobPayoff1 * 1e6,
        0,
    )

    tx = market.redeem(COVER, 1, {"from": bob})
    assert approx(tx.return_value) == bobPayoff1 * 1e6
    assert approx(balance - baseToken.balanceOf(market)) == bobPayoff1 * 1e6
    assert approx(baseToken.balanceOf(bob) - bobBalance) == bobPayoff1 * 1e6
    assert tx.events["Redeemed"] == {
        "account": bob,
        "isLongToken": False,
        "strikeIndex": 1,
        "amount": tx.return_value,
    }

    balance = baseToken.balanceOf(market)
    bobBalance = baseToken.balanceOf(bob)
    assert approx(market.calcRedeemAmountAndFee(PUT, 3, {"from": bob})) == (
        bobPayoff2 * 1e6,
        0,
    )

    tx = market.redeem(PUT, 3, {"from": bob})
    assert approx(tx.return_value) == bobPayoff2 * 1e6
    assert approx(balance - baseToken.balanceOf(market)) == bobPayoff2 * 1e6
    assert approx(baseToken.balanceOf(bob) - bobBalance) == bobPayoff2 * 1e6
    assert tx.events["Redeemed"] == {
        "account": bob,
        "isLongToken": True,
        "strikeIndex": 3,
        "amount": tx.return_value,
    }

    feesAccrued = (
        2 * 500 * 1e4
        + 3 * 600 * 1e4
        + 3 * 400 * 1e4
        + cost
        - (alicePayoff + bobPayoff1 + bobPayoff2) * 1e6
    )
    assert approx(market.calcFeesAccrued()) == feesAccrued

    balance1 = baseToken.balanceOf(deployer)
    tx = market.collectFees({"from": deployer})
    assert approx(tx.return_value) == feesAccrued
    assert approx(baseToken.balanceOf(deployer) - balance1) == feesAccrued
    assert market.calcFeesAccrued() == 0


@pytest.mark.parametrize("isEth", [False, True])
@pytest.mark.parametrize("isPut", [False, True])
def test_emergency_methods(
    a, OptionMarket, MockToken, MockOracle, OptionToken, fast_forward, isEth, isPut
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
    market = deployer.deploy(OptionMarket)
    market.initialize(
        baseToken,
        oracle,
        longTokens,
        shortTokens,
        [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
        2000000000,  # expiry = 18 May 2033
        isPut,
        1 * PERCENT,  # trading fee = 1%
        40000 * SCALE,  # balance cap = 40000
        3600,  # dispute period = 1 hour
    )
    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", 18)

    # give users base tokens
    if not isEth:
        baseToken.mint(deployer, 100 * SCALE, {"from": deployer})
        baseToken.approve(market, 100 * SCALE, {"from": deployer})
        baseToken.mint(alice, 100 * SCALE, {"from": deployer})
        baseToken.approve(market, 100 * SCALE, {"from": alice})
    valueDict = {"value": 50 * SCALE} if isEth else {}

    # needs to call increaseB
    market.increaseB(
        0.01 * SCALE,
        {"from": deployer, **valueDict},
    )

    # pause and unpause
    with reverts("Ownable: caller is not the owner"):
        market.pause({"from": alice})
    market.pause({"from": deployer})

    with reverts("This method has been paused"):
        market.buy(CALL, 0, 1 * PERCENT, 100 * SCALE, {"from": alice, **valueDict})
    with reverts("This method has been paused"):
        market.sell(CALL, 0, 1 * PERCENT, 0, {"from": alice})

    # can call paused methods from deployer
    market.buy(COVER, 0, 2 * PERCENT, 100 * SCALE, {"from": deployer, **valueDict})
    market.sell(COVER, 0, 1 * PERCENT, 0, {"from": deployer})

    with reverts("Ownable: caller is not the owner"):
        market.unpause({"from": alice})
    market.unpause({"from": deployer})
    market.buy(COVER, 0, 1 * PERCENT, 100 * SCALE, {"from": alice, **valueDict})

    # change oracle and expiry
    with reverts("Ownable: caller is not the owner"):
        market.setOracle(oracle2, {"from": alice})
    with reverts("Ownable: caller is not the owner"):
        market.setExpiryTime(2000000000 - 1, {"from": alice})

    market.setOracle(oracle2, {"from": deployer})
    assert market.oracle() == oracle2

    market.setExpiryTime(2000000000 - 1, {"from": deployer})
    assert market.expiryTime() == 2000000000 - 1

    market.setDisputePeriod(2400)
    assert market.disputePeriod() == 2400

    # dispute expiry price
    fast_forward(2000000000)
    with reverts("Ownable: caller is not the owner"):
        market.disputeExpiryPrice(666 * SCALE, {"from": alice})
    with reverts("Cannot be called before settlement"):
        market.disputeExpiryPrice(666 * SCALE, {"from": deployer})

    market.settle({"from": alice})
    market.disputeExpiryPrice(666 * SCALE, {"from": deployer})
    assert market.expiryPrice() == 666 * SCALE

    fast_forward(2000000000 + 2400)
    with reverts("Not dispute period"):
        market.disputeExpiryPrice(777 * SCALE, {"from": deployer})

    market.pause({"from": deployer})
    with reverts("This method has been paused"):
        market.redeem(CALL, 0, {"from": alice})

    # can call paused methods from deployer
    market.redeem(COVER, 0, {"from": deployer})

    market.unpause({"from": deployer})
    market.redeem(COVER, 0, {"from": alice})

    # change owner
    with reverts("Ownable: caller is not the owner"):
        market.transferOwnership(alice, {"from": alice})

    market.transferOwnership(alice, {"from": deployer})
    assert market.owner() == alice


@pytest.mark.parametrize("isEth", [False, True])
@pytest.mark.parametrize("balanceCap", [0, 20 * SCALE])
def test_set_balance_limit(
    a,
    OptionMarket,
    MockToken,
    MockOracle,
    OptionToken,
    fast_forward,
    isEth,
    balanceCap,
):

    # setup args
    deployer, alice = a[:2]
    baseToken = ZERO_ADDRESS if isEth else deployer.deploy(MockToken)
    oracle = deployer.deploy(MockOracle)
    longTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    shortTokens = [deployer.deploy(OptionToken) for _ in range(4)]

    # deploy and initialize
    market = deployer.deploy(OptionMarket)
    market.initialize(
        baseToken,
        oracle,
        longTokens,
        shortTokens,
        [300 * SCALE, 400 * SCALE, 500 * SCALE, 600 * SCALE],
        2000000000,  # expiry = 18 May 2033
        False,
        1 * PERCENT,  # trading fee = 1%
        10 * SCALE,  # balance cap = 10
        3600,  # dispute period = 1 hour
    )
    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", 18)

    # give users base tokens
    if not isEth:
        baseToken.mint(deployer, 100 * SCALE, {"from": deployer})
        baseToken.approve(market, 100 * SCALE, {"from": deployer})
        baseToken.mint(alice, 100 * SCALE, {"from": deployer})
        baseToken.approve(market, 100 * SCALE, {"from": alice})
    valueDict = {"value": 50 * SCALE} if isEth else {}

    # balance cap too low
    with reverts("Balance cap exceeded"):
        market.increaseB(
            10 * SCALE,
            {"from": deployer, **valueDict},
        )

    # only owner
    with reverts("Ownable: caller is not the owner"):
        market.setBalanceCap(20 * SCALE, {"from": alice})

    # increase cap
    market.setBalanceCap(balanceCap, {"from": deployer})
    assert market.balanceCap() == balanceCap

    # now works
    market.increaseB(
        10 * SCALE,
        {"from": deployer, **valueDict},
    )
