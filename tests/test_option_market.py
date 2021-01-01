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
    cost = mx + b * log(a)
    return SCALE * cost


@pytest.mark.parametrize("isEth", [False, True])
@pytest.mark.parametrize("isPut", [False, True])
@pytest.mark.parametrize("tradingFee", [0, 10 * PERCENT, SCALE - 1])
@pytest.mark.parametrize("balanceLimit", [0, 40 * SCALE])
def test_initialize(
    a,
    OptionMarket,
    MockToken,
    MockOracle,
    OptionToken,
    isEth,
    isPut,
    tradingFee,
    balanceLimit,
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
        balanceLimit,
    )

    # check variables all set
    assert market.baseToken() == baseToken
    assert market.oracle() == oracle
    assert market.expiryTime() == 2000000000
    assert market.b() == 0
    assert market.isPut() == isPut
    assert market.tradingFee() == tradingFee
    assert market.balanceLimit() == balanceLimit

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
            isPut,
            tradingFee,
            balanceLimit,
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
            SCALE,  # tradingFee = 100%
            40 * SCALE,  # balanceLimit = 40
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
            1e16,  # tradingFee = 1%
            40 * SCALE,  # balanceLimit = 40
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
            1e16,  # tradingFee = 1%
            40 * SCALE,  # balanceLimit = 40
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
            1e16,  # tradingFee = 1%
            40 * SCALE,  # balanceLimit = 40
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
            1e16,  # tradingFee = 1%
            40 * SCALE,  # balanceLimit = 40
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
            1e16,  # tradingFee = 1%
            40 * SCALE,  # balanceLimit = 40
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
            1e16,  # tradingFee = 1%
            40 * SCALE,  # balanceLimit = 40
        )


@pytest.mark.parametrize("isEth", [False, True])
@pytest.mark.parametrize("balanceLimit", [0, 40 * SCALE])
def test_increase_b(
    a,
    OptionMarket,
    MockToken,
    MockOracle,
    OptionToken,
    fast_forward,
    isEth,
    balanceLimit,
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
        1 * PERCENT,  # tradingFee = 1%
        balanceLimit,
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
        market.increaseBAndBuy(
            100 * SCALE,
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            1000 * SCALE,
            {"from": alice, **valueDict},
        )

    # not enough balance
    if isEth:
        with reverts("UniERC20: not enough value"):
            market.increaseBAndBuy(
                100 * SCALE,
                [0, 0, 0, 0],
                [0, 0, 0, 0],
                1000 * SCALE,
                {"from": deployer, **valueDict},
            )
    else:
        with reverts("ERC20: transfer amount exceeds balance"):
            market.increaseBAndBuy(
                100 * SCALE,
                [0, 0, 0, 0],
                [0, 0, 0, 0],
                1000 * SCALE,
                {"from": deployer, **valueDict},
            )

    with reverts("Lengths do not match"):
        market.increaseBAndBuy(
            10 * SCALE,
            [0, 0, 0],
            [0, 0, 0, 0],
            1000 * SCALE,
            {"from": deployer, **valueDict},
        )
    with reverts("Lengths do not match"):
        market.increaseBAndBuy(
            10 * SCALE,
            [0, 0, 0, 0],
            [0, 0, 0],
            1000 * SCALE,
            {"from": deployer, **valueDict},
        )

    # can increase b
    tx = market.increaseBAndBuy(
        10 * SCALE,
        [0, 1 * SCALE, 0, 0],
        [0, 0, 0, 0],
        1000 * SCALE,
        {"from": deployer, **valueDict},
    )
    assert approx(tx.return_value) == lmsr([0, 0, 1, 1, 1], 10)
    assert approx(getBalance(deployer)) == 100 * SCALE - tx.return_value

    # can't decrease b
    with reverts("New b must be higher"):
        market.increaseBAndBuy(
            9 * SCALE,
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            1000 * SCALE,
            {"from": deployer, **valueDict},
        )

    # but can increase b
    tx = market.increaseBAndBuy(
        15 * SCALE,
        [0, 0, 2 * SCALE, 0],
        [2 * SCALE, 0, 0, 0],
        1000 * SCALE,
        {"from": deployer, **valueDict},
    )
    assert approx(tx.return_value) == lmsr([2, 0, 1, 3, 3], 15) - lmsr(
        [0, 0, 1, 1, 1], 10
    )

    # can trade now
    market.buy(CALL, 3, SCALE, 100 * SCALE, {"from": alice, **valueDict})

    # can't increase b beyond balance limit
    if balanceLimit > 0:
        with reverts("Balance limit exceeded"):
            market.increaseBAndBuy(
                25 * SCALE,
                [0, 0, 0, 0],
                [0, 0, 0, 0],
                1000 * SCALE,
                {"from": deployer, **valueDict},
            )

    # no balance limit
    else:
        market.increaseBAndBuy(
            25 * SCALE,
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            1000 * SCALE,
            {"from": deployer, **valueDict},
        )


@pytest.mark.parametrize("isEth", [False, True])
@pytest.mark.parametrize("balanceLimit", [0, 40 * SCALE])
def test_buy_and_sell_calls(
    a,
    OptionMarket,
    MockToken,
    MockOracle,
    OptionToken,
    fast_forward,
    isEth,
    balanceLimit,
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
        1 * PERCENT,  # tradingFee = 1%
        balanceLimit,
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

    # needs to call increaseBAndBuy
    market.increaseBAndBuy(
        10 * SCALE,
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        1000 * SCALE,
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

    initial = lmsr([0, 0, 0, 0, 0], 10)

    # buy 2 calls
    tx = market.buy(CALL, 0, 2 * SCALE, 100 * SCALE, {"from": alice, **valueDict})
    cost = lmsr([0, 2, 2, 2, 2], 10) + 2 * PERCENT
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
    tx = market.buy(CALL, 2, 3 * SCALE, 100 * SCALE, {"from": alice, **valueDict})
    cost1 = lmsr([0, 2, 2, 2, 2], 10) + 2 * PERCENT
    cost2 = lmsr([0, 2, 2, 5, 5], 10) + 5 * PERCENT
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
    tx = market.buy(COVER, 3, 5 * SCALE, 100 * SCALE, {"from": alice, **valueDict})
    cost1 = lmsr([0, 2, 2, 5, 5], 10) + 5 * PERCENT
    cost2 = lmsr([5, 7, 7, 10, 5], 10) + 10 * PERCENT
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
    tx = market.buy(COVER, 0, 6 * SCALE, 100 * SCALE, {"from": alice, **valueDict})
    cost1 = lmsr([5, 7, 7, 10, 5], 10) + 10 * PERCENT
    cost2 = lmsr([11, 7, 7, 10, 5], 10) + 16 * PERCENT
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
    tx = market.sell(COVER, 0, 2 * SCALE, 0, {"from": alice})
    cost1 = lmsr([11, 7, 7, 10, 5], 10) + 16 * PERCENT
    cost2 = lmsr([9, 7, 7, 10, 5], 10) + 16 * PERCENT
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
    tx = market.sell(CALL, 0, 2 * SCALE, 0, {"from": alice})
    cost1 = lmsr([9, 7, 7, 10, 5], 10) + 16 * PERCENT
    cost2 = lmsr([9, 5, 5, 8, 3], 10) + 16 * PERCENT
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
    tx = market.sell(CALL, 2, 3 * SCALE, 0, {"from": alice})
    cost1 = lmsr([9, 5, 5, 8, 3], 10) + 16 * PERCENT
    cost2 = lmsr([9, 5, 5, 5, 0], 10) + 16 * PERCENT
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
    tx = market.sell(COVER, 3, 5 * SCALE, 0, {"from": alice})
    cost1 = lmsr([9, 5, 5, 5, 0], 10) + 16 * PERCENT
    cost2 = lmsr([4, 0, 0, 0, 0], 10) + 16 * PERCENT
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
    tx = market.sell(COVER, 0, 4 * SCALE, 0, {"from": alice})
    cost1 = lmsr([4, 0, 0, 0, 0], 10) + 16 * PERCENT
    cost2 = lmsr([0, 0, 0, 0, 0], 10) + 16 * PERCENT
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

    # can't buy beyond balance limit
    if balanceLimit > 0:
        with reverts("Balance limit exceeded"):
            tx = market.buy(
                COVER, 0, 40 * SCALE, 1000 * SCALE, {"from": alice, **valueDict}
            )

    # no balance limit
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


@pytest.mark.parametrize("balanceLimit", [0, 40000 * SCALE])
def test_buy_and_sell_puts(
    a, OptionMarket, MockToken, MockOracle, OptionToken, balanceLimit
):

    # setup args
    deployer, alice = a[:2]
    baseToken = deployer.deploy(MockToken)
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
        1 * PERCENT,  # tradingFee = 1%
        balanceLimit,
    )
    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", 18)

    # give users base tokens
    baseToken.mint(deployer, 100000 * SCALE, {"from": deployer})
    baseToken.approve(market, 100000 * SCALE, {"from": deployer})
    baseToken.mint(alice, 100000 * SCALE, {"from": deployer})
    baseToken.approve(market, 100000 * SCALE, {"from": alice})

    # needs to call increaseBAndBuy
    market.increaseBAndBuy(
        10 * SCALE, [0, 0, 0, 0], [0, 0, 0, 0], 100000 * SCALE, {"from": deployer}
    )

    # index out of range
    with reverts("Index too large"):
        tx = market.buy(PUT, 4, SCALE, 100 * SCALE, {"from": alice})
    with reverts("Index too large"):
        tx = market.buy(COVER, 4, SCALE, 100 * SCALE, {"from": alice})

    # can't buy too much
    with reverts("ERC20: transfer amount exceeds balance"):
        market.buy(PUT, 0, 1000 * SCALE, 1000000 * SCALE, {"from": alice})

    initial = 600 * lmsr([0, 0, 0, 0, 0], 10)

    # buy 2 puts
    tx = market.buy(PUT, 0, 2 * SCALE, 10000 * SCALE, {"from": alice})
    cost = 600 * lmsr([2, 0, 0, 0, 0], 10) + 300 * 2 * PERCENT
    assert approx(tx.return_value) == cost - initial
    assert approx(baseToken.balanceOf(alice)) == 100000 * SCALE - cost + initial
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
    cost1 = 600 * lmsr([2, 0, 0, 0, 0], 10) + 300 * 2 * PERCENT
    cost2 = 600 * lmsr([2, 0, 0, 5, 5], 10) + 300 * 2 * PERCENT + 500 * 5 * PERCENT
    assert approx(tx.return_value) == cost2 - cost1
    assert approx(baseToken.balanceOf(alice)) == 100000 * SCALE - cost2 + initial
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

    # sell 2 covers
    tx = market.sell(COVER, 2, 2 * SCALE, 0, {"from": alice})
    cost1 = 600 * lmsr([2, 0, 0, 5, 5], 10) + 300 * 2 * PERCENT + 500 * 5 * PERCENT
    cost2 = 600 * lmsr([2, 0, 0, 3, 3], 10) + 300 * 2 * PERCENT + 500 * 5 * PERCENT
    assert approx(tx.return_value) == cost1 - cost2
    assert approx(baseToken.balanceOf(alice)) == 100000 * SCALE - cost2 + initial
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

    # can't buy beyond balance limit
    if balanceLimit > 0:
        with reverts("Balance limit exceeded"):
            tx = market.buy(COVER, 0, 70 * SCALE, 100000 * SCALE, {"from": alice})

    # no balance limit
    else:
        tx = market.buy(COVER, 0, 70 * SCALE, 100000 * SCALE, {"from": alice})


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
        1 * PERCENT,  # tradingFee = 1%
        40000 * SCALE,  # balanceLimit = 40000
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
        1 * PERCENT,  # tradingFee = 1%
        40000 * SCALE,  # balanceLimit = 40000
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

    # needs to call increaseBAndBuy
    market.increaseBAndBuy(
        10 * SCALE,
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        1000 * SCALE,
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

    cost = lmsr([3, 5, 2, 2, 3], 10)
    assert approx(market.calcCost()) == cost

    fast_forward(2000000000 + 3600)

    alicePayoff = 2 * (444 - 300)
    bobPayoff = 3 * 400

    balance = getBalance(market)
    aliceBalance = getBalance(alice)
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
    assert approx(tx.return_value) == bobPayoff * SCALE / 444
    assert approx(balance - getBalance(market)) == bobPayoff * SCALE / 444
    assert approx(getBalance(bob) - bobBalance) == bobPayoff * SCALE / 444
    assert tx.events["Redeemed"] == {
        "account": bob,
        "isLongToken": False,
        "strikeIndex": 1,
        "amount": tx.return_value,
    }

    skimmed = 8 * PERCENT + cost - (alicePayoff + bobPayoff) * SCALE / 444
    assert approx(market.calcSkimAmount()) == skimmed

    balance1 = getBalance(deployer)
    tx = market.skim({"from": deployer})
    assert approx(tx.return_value) == skimmed
    assert approx(getBalance(deployer) - balance1) == skimmed
    assert market.calcSkimAmount() == 0


def test_redeem_puts(a, OptionMarket, MockToken, MockOracle, OptionToken, fast_forward):

    # setup args
    deployer, alice, bob = a[:3]
    baseToken = deployer.deploy(MockToken)
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
        1 * PERCENT,  # tradingFee = 1%
        40000 * SCALE,  # balanceLimit = 40000
    )
    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", 18)

    # give users base tokens
    baseToken.mint(deployer, 10000 * SCALE, {"from": deployer})
    baseToken.approve(market, 10000 * SCALE, {"from": deployer})
    baseToken.mint(alice, 10000 * SCALE, {"from": deployer})
    baseToken.approve(market, 10000 * SCALE, {"from": alice})
    baseToken.mint(bob, 10000 * SCALE, {"from": deployer})
    baseToken.approve(market, 10000 * SCALE, {"from": bob})

    # needs to call increaseBAndBuy
    market.increaseBAndBuy(
        10 * SCALE, [0, 0, 0, 0], [0, 0, 0, 0], 100000 * SCALE, {"from": deployer}
    )

    # buy 2 puts (strike=500)
    market.buy(PUT, 2, 2 * SCALE, 10000 * SCALE, {"from": alice})

    # buy 1 put (strike=600) and 3 covers (strike=400)
    market.buy(PUT, 3, 3 * SCALE, 10000 * SCALE, {"from": bob})
    market.buy(COVER, 1, 3 * SCALE, 10000 * SCALE, {"from": bob})
    market.sell(PUT, 3, 2 * SCALE, 0, {"from": bob})

    cost = 600 * lmsr([3, 3, 6, 4, 3], 10)
    assert approx(market.calcCost()) == cost

    fast_forward(2000000000 + 3600)
    market.settle({"from": alice})

    alicePayoff = 2 * (500 - 444)
    bobPayoff1 = 3 * 400
    bobPayoff2 = 1 * (600 - 444)

    balance = baseToken.balanceOf(market)
    aliceBalance = baseToken.balanceOf(alice)
    tx = market.redeem(PUT, 2, {"from": alice})
    assert approx(tx.return_value) == alicePayoff * SCALE
    assert approx(balance - baseToken.balanceOf(market)) == alicePayoff * SCALE
    assert approx(baseToken.balanceOf(alice) - aliceBalance) == alicePayoff * SCALE
    assert tx.events["Redeemed"] == {
        "account": alice,
        "isLongToken": True,
        "strikeIndex": 2,
        "amount": tx.return_value,
    }

    balance = baseToken.balanceOf(market)
    bobBalance = baseToken.balanceOf(bob)
    tx = market.redeem(COVER, 1, {"from": bob})
    assert approx(tx.return_value) == bobPayoff1 * SCALE
    assert approx(balance - baseToken.balanceOf(market)) == bobPayoff1 * SCALE
    assert approx(baseToken.balanceOf(bob) - bobBalance) == bobPayoff1 * SCALE
    assert tx.events["Redeemed"] == {
        "account": bob,
        "isLongToken": False,
        "strikeIndex": 1,
        "amount": tx.return_value,
    }

    balance = baseToken.balanceOf(market)
    bobBalance = baseToken.balanceOf(bob)
    tx = market.redeem(PUT, 3, {"from": bob})
    assert approx(tx.return_value) == bobPayoff2 * SCALE
    assert approx(balance - baseToken.balanceOf(market)) == bobPayoff2 * SCALE
    assert approx(baseToken.balanceOf(bob) - bobBalance) == bobPayoff2 * SCALE
    assert tx.events["Redeemed"] == {
        "account": bob,
        "isLongToken": True,
        "strikeIndex": 3,
        "amount": tx.return_value,
    }

    skimmed = (
        2 * 500 * PERCENT
        + 3 * 600 * PERCENT
        + 3 * 400 * PERCENT
        + cost
        - (alicePayoff + bobPayoff1 + bobPayoff2) * SCALE
    )
    assert approx(market.calcSkimAmount()) == skimmed

    balance1 = baseToken.balanceOf(deployer)
    tx = market.skim({"from": deployer})
    assert approx(tx.return_value) == skimmed
    assert approx(baseToken.balanceOf(deployer) - balance1) == skimmed
    assert market.calcSkimAmount() == 0


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
        1 * PERCENT,  # tradingFee = 1%
        40000 * SCALE,  # balanceLimit = 40000
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

    # needs to call increaseBAndBuy
    market.increaseBAndBuy(
        0.01 * SCALE,
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        1000 * SCALE,
        {"from": deployer, **valueDict},
    )

    # pause and unpause
    with reverts("Ownable: caller is not the owner"):
        market.pause({"from": alice})
    market.pause({"from": deployer})

    with reverts("This method has been paused"):
        market.buy(CALL, 0, 1 * PERCENT, 100 * SCALE, {"from": alice, **valueDict})

    with reverts("Ownable: caller is not the owner"):
        market.unpause({"from": alice})
    market.unpause({"from": deployer})
    market.buy(CALL, 0, 1 * PERCENT, 100 * SCALE, {"from": alice, **valueDict})

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
