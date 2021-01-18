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
@pytest.mark.parametrize("baseDecimals", [6, 18])
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
    baseDecimals,
):

    # setup args
    deployer = a[0]

    if isEth:
        baseToken = ZERO_ADDRESS
    else:
        baseToken = deployer.deploy(MockToken)
        baseToken.setDecimals(baseDecimals)

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
        "symbol",
    )

    # check variables all set
    assert market.baseToken() == baseToken
    assert market.oracle() == oracle
    assert market.expiryTime() == 2000000000
    assert market.isPut() == isPut
    assert market.tradingFee() == tradingFee
    assert market.balanceCap() == balanceCap
    assert market.disputePeriod() == disputePeriod
    assert market.name() == "symbol"
    assert market.symbol() == "symbol"
    assert market.decimals() == 18 if isEth else baseDecimals
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
            "symbol",
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
            "symbol",
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
            "symbol",
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
            "symbol",
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
            "symbol",
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
            "symbol",
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
            "symbol",
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
            "symbol",
        )


@pytest.mark.parametrize("isEth", [False, True])
@pytest.mark.parametrize("balanceCap", [0, 40])
@pytest.mark.parametrize("baseDecimals", [6, 18])
def test_calls(
    a,
    OptionMarket,
    MockToken,
    MockOracle,
    OptionToken,
    fast_forward,
    isEth,
    balanceCap,
    baseDecimals,
):

    # setup args
    deployer, alice, bob = a[:3]
    oracle = deployer.deploy(MockOracle)
    oracle.setPrice(555 * SCALE)
    longTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    shortTokens = [deployer.deploy(OptionToken) for _ in range(4)]

    if isEth:
        scale = 1e18
        baseToken = ZERO_ADDRESS
    else:
        scale = 10 ** baseDecimals
        baseToken = deployer.deploy(MockToken)
        baseToken.setDecimals(baseDecimals)
    percent = scale // 100

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
        balanceCap * scale,
        3600,  # dispute period = 1 hour
        "symbol",
    )
    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", 18)

    # give users base tokens
    if not isEth:
        for user in [deployer, alice, bob]:
            baseToken.mint(user, 100 * scale, {"from": deployer})
            baseToken.approve(market, 100 * scale, {"from": user})
    valueDict = {"value": 50 * scale} if isEth else {}

    # can't trade before setting b
    with reverts("No liquidity"):
        market.buy(CALL, 4, scale, 100 * scale, {"from": alice, **valueDict})

    # not enough balance to deposit
    if isEth:
        with reverts("UniERC20: not enough value"):
            market.deposit(
                100 * scale,
                1000 * scale,
                {"from": alice, **valueDict},
            )
    else:
        with reverts("ERC20: transfer amount exceeds balance"):
            market.deposit(
                100 * scale,
                1000 * scale,
                {"from": alice, **valueDict},
            )

    # try to deposit
    with reverts("Max slippage exceeded"):
        market.deposit(
            10 * scale,
            12 * scale,
            {"from": alice, **valueDict},
        )

    # alice deposits
    tx = market.deposit(
        10 * scale,
        100 * scale,
        {"from": alice, **valueDict},
    )
    cost = scale * lmsr([0, 0, 0, 0, 0], 10)
    assert approx(tx.return_value) == cost
    assert approx(getBalance(alice)) == 100 * scale - tx.return_value
    assert approx(getBalance(market)) == cost
    assert tx.events["Deposit"] == {
        "account": alice,
        "sharesOut": 10 * scale,
        "amountIn": tx.return_value,
        "newB": 10 * scale,
    }

    # index out of range
    with reverts("Index too large"):
        market.buy(CALL, 4, scale, 100 * scale, {"from": alice, **valueDict})
    with reverts("Index too large"):
        market.buy(COVER, 4, scale, 100 * scale, {"from": alice, **valueDict})

    # can't buy too much
    if isEth:
        with reverts("UniERC20: not enough value"):
            market.buy(CALL, 0, 120 * scale, 10000 * scale, {"from": alice})
    else:
        with reverts("ERC20: transfer amount exceeds balance"):
            tx = market.buy(CALL, 0, 120 * scale, 10000 * scale, {"from": alice})

    # try to buy
    with reverts("Max slippage exceeded"):
        market.buy(CALL, 0, 2 * scale, 1.6 * scale, {"from": alice, **valueDict})

    # buy 2 calls
    balance = getBalance(alice)
    tx = market.buy(CALL, 0, 2 * scale, 100 * scale, {"from": alice, **valueDict})
    cost1 = scale * lmsr([0, 0, 0, 0, 0], 10)
    cost2 = scale * lmsr([0, 2, 2, 2, 2], 10) + 2 * percent
    assert approx(tx.return_value) == cost2 - cost1
    assert approx(balance - getBalance(alice)) == cost2 - cost1
    assert approx(getBalance(market)) == cost2
    assert longTokens[0].balanceOf(alice) == 2 * scale
    assert tx.events["Buy"] == {
        "account": alice,
        "isLongToken": True,
        "strikeIndex": 0,
        "optionsOut": 2 * scale,
        "amountIn": tx.return_value,
        "newSupply": 2 * scale,
    }

    # bob deposits
    balance = getBalance(bob)
    tx = market.deposit(
        5 * scale,
        100 * scale,
        {"from": bob, **valueDict},
    )
    cost1 = scale * lmsr([0, 2, 2, 2, 2], 10) + 2 * percent
    cost2 = scale * lmsr([0, 2, 2, 2, 2], 15) + 3 * percent
    assert approx(tx.return_value) == cost2 - cost1
    assert approx(balance - getBalance(bob)) == cost2 - cost1
    assert approx(getBalance(market)) == cost2
    assert tx.events["Deposit"] == {
        "account": bob,
        "sharesOut": 5 * scale,
        "amountIn": tx.return_value,
        "newB": 15 * scale,
    }

    # bob buys 3 calls
    balance = getBalance(bob)
    tx = market.buy(CALL, 2, 3 * scale, 100 * scale, {"from": bob, **valueDict})
    cost1 = scale * lmsr([0, 2, 2, 2, 2], 15) + 3 * percent
    cost2 = scale * lmsr([0, 2, 2, 5, 5], 15) + 6 * percent
    assert approx(tx.return_value) == cost2 - cost1
    assert approx(balance - getBalance(bob)) == cost2 - cost1
    assert approx(getBalance(market)) == cost2
    assert longTokens[0].balanceOf(alice) == 2 * scale
    assert longTokens[2].balanceOf(bob) == 3 * scale
    assert tx.events["Buy"] == {
        "account": bob,
        "isLongToken": True,
        "strikeIndex": 2,
        "optionsOut": 3 * scale,
        "amountIn": tx.return_value,
        "newSupply": 3 * scale,
    }

    # buy 6 covers
    balance = getBalance(alice)
    tx = market.buy(COVER, 3, 6 * scale, 100 * scale, {"from": alice, **valueDict})
    cost1 = scale * lmsr([0, 2, 2, 5, 5], 15) + 6 * percent
    cost2 = scale * lmsr([6, 8, 8, 11, 5], 15) + 12 * percent
    assert approx(tx.return_value) == cost2 - cost1
    assert approx(balance - getBalance(alice)) == cost2 - cost1
    assert approx(getBalance(market)) == cost2
    assert longTokens[0].balanceOf(alice) == 2 * scale
    assert longTokens[2].balanceOf(bob) == 3 * scale
    assert shortTokens[3].balanceOf(alice) == 6 * scale
    assert tx.events["Buy"] == {
        "account": alice,
        "isLongToken": False,
        "strikeIndex": 3,
        "optionsOut": 6 * scale,
        "amountIn": tx.return_value,
        "newSupply": 6 * scale,
    }

    # can't sell more than you have
    with reverts("ERC20: burn amount exceeds balance"):
        market.sell(CALL, 0, 3 * scale, 0, {"from": alice})
    with reverts("ERC20: burn amount exceeds balance"):
        market.sell(COVER, 0, 7 * scale, 0, {"from": alice})
    with reverts("ERC20: burn amount exceeds balance"):
        market.sell(COVER, 1, 1 * scale, 0, {"from": alice})
    with reverts("ERC20: burn amount exceeds balance"):
        market.sell(CALL, 0, 1 * scale, 0, {"from": bob})

    # sell 1 calls
    balance = getBalance(alice)
    tx = market.sell(CALL, 0, 1 * scale, 0, {"from": alice})
    cost1 = scale * lmsr([6, 8, 8, 11, 5], 15) + 12 * percent
    cost2 = scale * lmsr([6, 7, 7, 10, 4], 15) + 12 * percent
    assert approx(tx.return_value) == cost1 - cost2
    assert approx(getBalance(alice) - balance) == cost1 - cost2
    assert longTokens[0].balanceOf(alice) == 1 * scale
    assert longTokens[2].balanceOf(bob) == 3 * scale
    assert shortTokens[3].balanceOf(alice) == 6 * scale
    assert tx.events["Sell"] == {
        "account": alice,
        "isLongToken": True,
        "strikeIndex": 0,
        "optionsIn": 1 * scale,
        "amountOut": tx.return_value,
        "newSupply": 1 * scale,
        "isSettled": False,
    }

    # sell 5 covers
    balance = getBalance(alice)
    tx = market.sell(COVER, 3, 5 * scale, 0, {"from": alice})
    cost1 = scale * lmsr([6, 7, 7, 10, 4], 15) + 12 * percent
    cost2 = scale * lmsr([1, 2, 2, 5, 4], 15) + 12 * percent
    assert approx(tx.return_value) == cost1 - cost2
    assert approx(getBalance(alice) - balance) == cost1 - cost2
    assert longTokens[0].balanceOf(alice) == 1 * scale
    assert longTokens[2].balanceOf(bob) == 3 * scale
    assert shortTokens[3].balanceOf(alice) == 1 * scale
    assert tx.events["Sell"] == {
        "account": alice,
        "isLongToken": False,
        "strikeIndex": 3,
        "optionsIn": 5 * scale,
        "amountOut": tx.return_value,
        "newSupply": 1 * scale,
        "isSettled": False,
    }

    # try to withdraw
    with reverts("Max slippage exceeded"):
        market.withdraw(3 * scale, 5 * scale, {"from": alice})
    with reverts("ERC20: burn amount exceeds balance"):
        market.withdraw(11 * scale, 0 * scale, {"from": alice})

    # alice withdraws
    balance = getBalance(alice)
    tx = market.withdraw(3 * scale, 0, {"from": alice})
    cost1 = scale * lmsr([1, 2, 2, 5, 4], 15) + 12 * percent
    cost2 = scale * lmsr([1, 2, 2, 5, 4], 12) + 9.6 * percent
    assert approx(tx.return_value) == cost1 - cost2
    assert approx(getBalance(alice) - balance) == cost1 - cost2
    assert tx.events["Withdraw"] == {
        "account": alice,
        "sharesIn": 3 * scale,
        "amountOut": tx.return_value,
        "newB": 12 * scale,
        "isSettled": False,
    }

    # can't deposit beyond balance cap
    if balanceCap > 0:
        with reverts("Balance cap exceeded"):
            market.deposit(
                25 * scale,
                100 * scale,
                {"from": alice, **valueDict},
            )

    # no balance cap
    else:
        market.deposit(
            25 * scale,
            100 * scale,
            {"from": alice, **valueDict},
        )
        market.withdraw(
            25 * scale,
            0 * scale,
            {"from": alice},
        )

    # can't settle before expiry
    with reverts("Cannot be called before expiry"):
        market.settle({"from": alice})

    # settle
    fast_forward(2000000000)
    assert market.expiryPrice() == 0
    tx = market.settle({"from": alice})
    assert market.expiryPrice() == 555 * SCALE
    assert tx.events["Settle"] == {
        "expiryPrice": 555 * SCALE,
    }

    # can't settle more than once
    with reverts("Already settled"):
        market.settle({"from": alice})

    # still dispute period
    with reverts("Dispute period"):
        market.sell(CALL, 0, 1 * scale, 0, {"from": alice})

    fast_forward(2000000000 + 3600)

    alicePayoff1 = 1 * (555 - 300)
    alicePayoff2 = 1 * 555
    bobPayoff = 3 * (555 - 500)

    cost = scale * lmsr([1, 2, 2, 5, 4], 12) + 9.6 * percent
    lpPayoff = cost - (alicePayoff1 + alicePayoff2 + bobPayoff) * scale / 555

    marketBalance = getBalance(market)
    aliceBalance = getBalance(alice)
    tx = market.sell(CALL, 0, 1 * scale, 0, {"from": alice})
    assert approx(tx.return_value) == alicePayoff1 * scale / 555
    assert approx(marketBalance - getBalance(market)) == alicePayoff1 * scale / 555
    assert approx(getBalance(alice) - aliceBalance) == alicePayoff1 * scale / 555
    assert tx.events["Sell"] == {
        "account": alice,
        "isLongToken": CALL,
        "strikeIndex": 0,
        "optionsIn": 1 * scale,
        "amountOut": tx.return_value,
        "newSupply": 0,
        "isSettled": True,
    }

    marketBalance = getBalance(market)
    aliceBalance = getBalance(alice)
    tx = market.sell(COVER, 3, 1 * scale, 0, {"from": alice})
    assert approx(tx.return_value) == alicePayoff2 * scale / 555
    assert approx(marketBalance - getBalance(market)) == alicePayoff2 * scale / 555
    assert approx(getBalance(alice) - aliceBalance) == alicePayoff2 * scale / 555
    assert tx.events["Sell"] == {
        "account": alice,
        "isLongToken": COVER,
        "strikeIndex": 3,
        "optionsIn": 1 * scale,
        "amountOut": tx.return_value,
        "newSupply": 0,
        "isSettled": True,
    }

    # bob withdraws
    balance = getBalance(bob)
    tx = market.withdraw(5 * scale, 0, {"from": bob})
    assert approx(tx.return_value) == lpPayoff * 5.0 / 12.0
    assert approx(getBalance(bob) - balance) == lpPayoff * 5.0 / 12.0
    assert tx.events["Withdraw"] == {
        "account": bob,
        "sharesIn": 5 * scale,
        "amountOut": tx.return_value,
        "newB": 7 * scale,
        "isSettled": True,
    }

    marketBalance = getBalance(market)
    bobBalance = getBalance(bob)
    tx = market.sell(CALL, 2, 3 * scale, 0, {"from": bob})
    assert approx(tx.return_value) == bobPayoff * scale / 555
    assert approx(marketBalance - getBalance(market)) == bobPayoff * scale / 555
    assert approx(getBalance(bob) - bobBalance) == bobPayoff * scale / 555
    assert tx.events["Sell"] == {
        "account": bob,
        "isLongToken": CALL,
        "strikeIndex": 2,
        "optionsIn": 3 * scale,
        "amountOut": tx.return_value,
        "newSupply": 0,
        "isSettled": True,
    }

    # alice withdraws
    balance = getBalance(alice)
    tx = market.withdraw(7 * scale, 0, {"from": alice})
    assert approx(tx.return_value) == lpPayoff * 7.0 / 12.0
    assert approx(getBalance(alice) - balance) == lpPayoff * 7.0 / 12.0
    assert tx.events["Withdraw"] == {
        "account": alice,
        "sharesIn": 7 * scale,
        "amountOut": tx.return_value,
        "newB": 0 * scale,
        "isSettled": True,
    }

    # no tvl left
    assert getBalance(market) == 0


@pytest.mark.parametrize("balanceCap", [0, 40000])
@pytest.mark.parametrize("baseDecimals", [6, 18])
def test_puts(
    a,
    OptionMarket,
    MockToken,
    MockOracle,
    OptionToken,
    fast_forward,
    balanceCap,
    baseDecimals,
):

    # setup args
    deployer, alice, bob = a[:3]
    oracle = deployer.deploy(MockOracle)
    oracle.setPrice(444 * SCALE)
    longTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    shortTokens = [deployer.deploy(OptionToken) for _ in range(4)]

    scale = 10 ** baseDecimals
    baseToken = deployer.deploy(MockToken)
    baseToken.setDecimals(baseDecimals)
    percent = scale // 100

    def getBalance(wallet):
        return baseToken.balanceOf(wallet)

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
        balanceCap * scale,
        3600,  # dispute period = 1 hour
        "symbol",
    )
    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", 18)

    # give users base tokens
    for user in [deployer, alice, bob]:
        baseToken.mint(user, 100000 * scale, {"from": deployer})
        baseToken.approve(market, 100000 * scale, {"from": user})

    # not enough balance to deposit
    with reverts("ERC20: transfer amount exceeds balance"):
        market.deposit(
            80000 * scale,
            1000000 * scale,
            {"from": alice},
        )

    # try to deposit
    with reverts("Max slippage exceeded"):
        market.deposit(
            10 * scale,
            12 * scale,
            {"from": alice},
        )

    # alice deposits
    tx = market.deposit(
        1000 * scale,
        10000 * scale,
        {"from": alice},
    )
    cost = scale * lmsr([0, 0, 0, 0, 0], 1000)
    assert approx(tx.return_value) == cost
    assert approx(getBalance(alice)) == 100000 * scale - tx.return_value
    assert approx(getBalance(market)) == cost
    assert tx.events["Deposit"] == {
        "account": alice,
        "sharesOut": 1000 * scale,
        "amountIn": tx.return_value,
        "newB": 1000 * scale,
    }

    # can't buy too much
    with reverts("ERC20: transfer amount exceeds balance"):
        tx = market.buy(CALL, 0, 1000 * scale, 1000000 * scale, {"from": alice})

    # try to buy
    with reverts("Max slippage exceeded"):
        market.buy(CALL, 0, 1000 * scale, 1500 * scale, {"from": alice})

    # buy 2 calls
    balance = getBalance(alice)
    tx = market.buy(PUT, 0, 2 * scale, 10000 * scale, {"from": alice})
    cost1 = scale * lmsr([0, 0, 0, 0, 0], 1000)
    cost2 = scale * lmsr([2 * 300, 0, 0, 0, 0], 1000) + 2 * 300 * percent
    assert approx(tx.return_value) == cost2 - cost1
    assert approx(balance - getBalance(alice)) == cost2 - cost1
    assert approx(getBalance(market)) == cost2
    assert longTokens[0].balanceOf(alice) == 2 * scale
    assert tx.events["Buy"] == {
        "account": alice,
        "isLongToken": True,
        "strikeIndex": 0,
        "optionsOut": 2 * scale,
        "amountIn": tx.return_value,
        "newSupply": 2 * scale,
    }

    # bob deposits
    balance = getBalance(bob)
    tx = market.deposit(
        500 * scale,
        1000 * scale,
        {"from": bob},
    )
    cost1 = scale * lmsr([2 * 300, 0, 0, 0, 0], 1000) + 2 * 300 * percent
    cost2 = scale * lmsr([2 * 300, 0, 0, 0, 0], 1500) + 3 * 300 * percent
    assert approx(tx.return_value) == cost2 - cost1
    assert approx(balance - getBalance(bob)) == cost2 - cost1
    assert approx(getBalance(market)) == cost2
    assert tx.events["Deposit"] == {
        "account": bob,
        "sharesOut": 500 * scale,
        "amountIn": tx.return_value,
        "newB": 1500 * scale,
    }

    # bob buys 3 puts
    balance = getBalance(bob)
    tx = market.buy(PUT, 2, 3 * scale, 10000 * scale, {"from": bob})
    cost1 = scale * lmsr([2 * 300, 0, 0, 0, 0], 1500) + 3 * 300 * percent
    cost2 = (
        scale * lmsr([2 * 300 + 3 * 500, 3 * 500, 3 * 500, 0, 0], 1500)
        + 3 * 300 * percent
        + 3 * 500 * percent
    )
    assert approx(tx.return_value) == cost2 - cost1
    assert approx(balance - getBalance(bob)) == cost2 - cost1
    assert approx(getBalance(market)) == cost2
    assert longTokens[0].balanceOf(alice) == 2 * scale
    assert longTokens[2].balanceOf(bob) == 3 * scale
    assert tx.events["Buy"] == {
        "account": bob,
        "isLongToken": True,
        "strikeIndex": 2,
        "optionsOut": 3 * scale,
        "amountIn": tx.return_value,
        "newSupply": 3 * scale,
    }

    # buy 6 covers
    balance = getBalance(alice)
    tx = market.buy(COVER, 3, 6 * scale, 10000 * scale, {"from": alice})
    cost1 = (
        scale * lmsr([2 * 300 + 3 * 500, 3 * 500, 3 * 500, 0, 0], 1500)
        + 3 * 300 * percent
        + 3 * 500 * percent
    )
    cost2 = (
        scale * lmsr([2 * 300 + 3 * 500, 3 * 500, 3 * 500, 0, 6 * 600], 1500)
        + 3 * 300 * percent
        + 3 * 500 * percent
        + 6 * 600 * percent
    )
    assert approx(tx.return_value) == cost2 - cost1
    assert approx(balance - getBalance(alice)) == cost2 - cost1
    assert approx(getBalance(market)) == cost2
    assert longTokens[0].balanceOf(alice) == 2 * scale
    assert longTokens[2].balanceOf(bob) == 3 * scale
    assert shortTokens[3].balanceOf(alice) == 6 * scale
    assert tx.events["Buy"] == {
        "account": alice,
        "isLongToken": False,
        "strikeIndex": 3,
        "optionsOut": 6 * scale,
        "amountIn": tx.return_value,
        "newSupply": 6 * scale,
    }

    # can't sell more than you have
    with reverts("ERC20: burn amount exceeds balance"):
        market.sell(PUT, 0, 3 * scale, 0, {"from": alice})
    with reverts("ERC20: burn amount exceeds balance"):
        market.sell(COVER, 0, 7 * scale, 0, {"from": alice})
    with reverts("ERC20: burn amount exceeds balance"):
        market.sell(COVER, 1, 1 * scale, 0, {"from": alice})
    with reverts("ERC20: burn amount exceeds balance"):
        market.sell(PUT, 0, 1 * scale, 0, {"from": bob})

    # sell 1 calls
    balance = getBalance(alice)
    tx = market.sell(PUT, 0, 1 * scale, 0, {"from": alice})
    cost1 = (
        scale * lmsr([2 * 300 + 3 * 500, 3 * 500, 3 * 500, 0, 6 * 600], 1500)
        + 3 * 300 * percent
        + 3 * 500 * percent
        + 6 * 600 * percent
    )
    cost2 = (
        scale * lmsr([1 * 300 + 3 * 500, 3 * 500, 3 * 500, 0, 6 * 600], 1500)
        + 3 * 300 * percent
        + 3 * 500 * percent
        + 6 * 600 * percent
    )
    assert approx(tx.return_value) == cost1 - cost2
    assert approx(getBalance(alice) - balance) == cost1 - cost2
    assert approx(getBalance(market)) == cost2
    assert longTokens[0].balanceOf(alice) == 1 * scale
    assert longTokens[2].balanceOf(bob) == 3 * scale
    assert shortTokens[3].balanceOf(alice) == 6 * scale
    assert tx.events["Sell"] == {
        "account": alice,
        "isLongToken": True,
        "strikeIndex": 0,
        "optionsIn": 1 * scale,
        "amountOut": tx.return_value,
        "newSupply": 1 * scale,
        "isSettled": False,
    }

    # sell 5 covers
    balance = getBalance(alice)
    tx = market.sell(COVER, 3, 5 * scale, 0, {"from": alice})
    cost1 = (
        scale * lmsr([1 * 300 + 3 * 500, 3 * 500, 3 * 500, 0, 6 * 600], 1500)
        + 3 * 300 * percent
        + 3 * 500 * percent
        + 6 * 600 * percent
    )
    cost2 = (
        scale * lmsr([1 * 300 + 3 * 500, 3 * 500, 3 * 500, 0, 1 * 600], 1500)
        + 3 * 300 * percent
        + 3 * 500 * percent
        + 6 * 600 * percent
    )
    assert approx(tx.return_value) == cost1 - cost2
    assert approx(getBalance(alice) - balance) == cost1 - cost2
    assert approx(getBalance(market)) == cost2
    assert longTokens[0].balanceOf(alice) == 1 * scale
    assert longTokens[2].balanceOf(bob) == 3 * scale
    assert shortTokens[3].balanceOf(alice) == 1 * scale
    assert tx.events["Sell"] == {
        "account": alice,
        "isLongToken": False,
        "strikeIndex": 3,
        "optionsIn": 5 * scale,
        "amountOut": tx.return_value,
        "newSupply": 1 * scale,
        "isSettled": False,
    }

    # try to withdraw
    with reverts("Max slippage exceeded"):
        market.withdraw(3 * scale, 5 * scale, {"from": alice})
    with reverts("ERC20: burn amount exceeds balance"):
        market.withdraw(1100 * scale, 0 * scale, {"from": alice})

    # alice withdraws
    balance = getBalance(alice)
    tx = market.withdraw(300 * scale, 0, {"from": alice})
    cost1 = (
        scale * lmsr([1 * 300 + 3 * 500, 3 * 500, 3 * 500, 0, 1 * 600], 1500)
        + 3 * 300 * percent
        + 3 * 500 * percent
        + 6 * 600 * percent
    )
    cost2 = (
        scale * lmsr([1 * 300 + 3 * 500, 3 * 500, 3 * 500, 0, 1 * 600], 1200)
        + 0.8 * 3 * 300 * percent
        + 0.8 * 3 * 500 * percent
        + 0.8 * 6 * 600 * percent
    )
    assert approx(tx.return_value) == cost1 - cost2
    assert approx(getBalance(alice) - balance) == cost1 - cost2
    assert approx(getBalance(market)) == cost2
    assert tx.events["Withdraw"] == {
        "account": alice,
        "sharesIn": 300 * scale,
        "amountOut": tx.return_value,
        "newB": 1200 * scale,
        "isSettled": False,
    }

    # can't deposit beyond balance cap
    if balanceCap > 0:
        with reverts("Balance cap exceeded"):
            market.deposit(
                25000 * scale,
                100000 * scale,
                {"from": alice},
            )

    # no balance cap
    else:
        market.deposit(
            25 * scale,
            100 * scale,
            {"from": alice},
        )
        market.withdraw(
            25 * scale,
            0 * scale,
            {"from": alice},
        )

    # can't settle before expiry
    with reverts("Cannot be called before expiry"):
        market.settle({"from": alice})

    # settle
    fast_forward(2000000000)
    assert market.expiryPrice() == 0
    tx = market.settle({"from": alice})
    assert market.expiryPrice() == 444 * SCALE
    assert tx.events["Settle"] == {
        "expiryPrice": 444 * SCALE,
    }

    # can't settle more than once
    with reverts("Already settled"):
        market.settle({"from": alice})

    # still dispute period
    with reverts("Dispute period"):
        market.sell(PUT, 0, 1 * scale, 0, {"from": alice})

    fast_forward(2000000000 + 3600)

    alicePayoff1 = 0
    alicePayoff2 = 1 * 444
    bobPayoff = 3 * (500 - 444)

    cost = (
        scale * lmsr([1 * 300 + 3 * 500, 3 * 500, 3 * 500, 0, 1 * 600], 1200)
        + 0.8 * 3 * 300 * percent
        + 0.8 * 3 * 500 * percent
        + 0.8 * 6 * 600 * percent
    )
    lpPayoff = cost - (alicePayoff1 + alicePayoff2 + bobPayoff) * scale

    marketBalance = getBalance(market)
    aliceBalance = getBalance(alice)
    with reverts("Amount out must be > 0"):
        market.sell(PUT, 0, 1 * scale, 0, {"from": alice})

    marketBalance = getBalance(market)
    aliceBalance = getBalance(alice)
    tx = market.sell(COVER, 3, 1 * scale, 0, {"from": alice})
    assert approx(tx.return_value) == alicePayoff2 * scale
    assert approx(marketBalance - getBalance(market)) == alicePayoff2 * scale
    assert approx(getBalance(alice) - aliceBalance) == alicePayoff2 * scale
    assert tx.events["Sell"] == {
        "account": alice,
        "isLongToken": COVER,
        "strikeIndex": 3,
        "optionsIn": 1 * scale,
        "amountOut": tx.return_value,
        "newSupply": 0,
        "isSettled": True,
    }

    # bob withdraws
    balance = getBalance(bob)
    tx = market.withdraw(500 * scale, 0, {"from": bob})
    assert approx(tx.return_value) == lpPayoff * 5.0 / 12.0
    assert approx(getBalance(bob) - balance) == lpPayoff * 5.0 / 12.0
    assert tx.events["Withdraw"] == {
        "account": bob,
        "sharesIn": 500 * scale,
        "amountOut": tx.return_value,
        "newB": 700 * scale,
        "isSettled": True,
    }

    marketBalance = getBalance(market)
    bobBalance = getBalance(bob)
    tx = market.sell(PUT, 2, 3 * scale, 0, {"from": bob})
    assert approx(tx.return_value) == bobPayoff * scale
    assert approx(marketBalance - getBalance(market)) == bobPayoff * scale
    assert approx(getBalance(bob) - bobBalance) == bobPayoff * scale
    assert tx.events["Sell"] == {
        "account": bob,
        "isLongToken": PUT,
        "strikeIndex": 2,
        "optionsIn": 3 * scale,
        "amountOut": tx.return_value,
        "newSupply": 0,
        "isSettled": True,
    }

    # alice withdraws
    balance = getBalance(alice)
    tx = market.withdraw(700 * scale, 0, {"from": alice})
    assert approx(tx.return_value) == lpPayoff * 7.0 / 12.0
    assert approx(getBalance(alice) - balance) == lpPayoff * 7.0 / 12.0
    assert tx.events["Withdraw"] == {
        "account": alice,
        "sharesIn": 700 * scale,
        "amountOut": tx.return_value,
        "newB": 0 * scale,
        "isSettled": True,
    }

    # no tvl left
    assert getBalance(market) == 0


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
        "symbol",
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

    market.deposit(
        0.01 * SCALE,
        0.1 * SCALE,
        {"from": alice, **valueDict},
    )

    # pause and unpause
    with reverts("Ownable: caller is not the owner"):
        market.pause({"from": alice})
    market.pause({"from": deployer})

    with reverts("Paused"):
        market.buy(CALL, 0, 1 * PERCENT, 100 * SCALE, {"from": alice, **valueDict})
    with reverts("Paused"):
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
    assert market.lastPayoff() == market.getCurrentPayoff()
    assert market.isSettled()

    fast_forward(2000000000 + 2400)
    with reverts("Not dispute period"):
        market.disputeExpiryPrice(777 * SCALE, {"from": deployer})

    market.pause({"from": deployer})
    with reverts("Paused"):
        market.sell(CALL, 0, 1 * PERCENT, 0, {"from": alice})

    # can call paused methods from deployer
    market.sell(COVER, 0, 1 * PERCENT, 0, {"from": deployer})

    market.unpause({"from": deployer})
    market.sell(COVER, 0, 1 * PERCENT, 0, {"from": alice})

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
        "symbol",
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
        market.deposit(
            10 * SCALE,
            100 * SCALE,
            {"from": alice, **valueDict},
        )

    # only owner
    with reverts("Ownable: caller is not the owner"):
        market.setBalanceCap(20 * SCALE, {"from": alice})

    # increase cap
    market.setBalanceCap(balanceCap, {"from": deployer})
    assert market.balanceCap() == balanceCap

    # now works
    market.deposit(
        10 * SCALE,
        100 * SCALE,
        {"from": alice, **valueDict},
    )


@pytest.mark.parametrize("isEth", [False, True])
@pytest.mark.parametrize("balanceCap", [0, 40])
@pytest.mark.parametrize("baseDecimals", [6, 18])
@pytest.mark.parametrize("depositFirst", [False, True])
def test_liquidity_manipulation_attack(
    a,
    OptionMarket,
    MockToken,
    MockOracle,
    OptionToken,
    fast_forward,
    isEth,
    balanceCap,
    baseDecimals,
    depositFirst,
):

    # setup args
    deployer, alice = a[:2]
    oracle = deployer.deploy(MockOracle)
    longTokens = [deployer.deploy(OptionToken) for _ in range(4)]
    shortTokens = [deployer.deploy(OptionToken) for _ in range(4)]

    if isEth:
        scale = 1e18
        baseToken = ZERO_ADDRESS
    else:
        scale = 10 ** baseDecimals
        baseToken = deployer.deploy(MockToken)
        baseToken.setDecimals(baseDecimals)
    percent = scale // 100

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
        balanceCap * scale,
        3600,  # dispute period = 1 hour
        "symbol",
    )
    for token in longTokens + shortTokens:
        token.initialize(market, "name", "symbol", 18)

    # give users base tokens
    if not isEth:
        for user in [deployer, alice]:
            baseToken.mint(user, 100 * scale, {"from": deployer})
            baseToken.approve(market, 100 * scale, {"from": user})
    valueDict = {"value": 50 * scale} if isEth else {}

    # deployers deposits 1
    market.deposit(
        1 * scale,
        100 * scale,
        {"from": deployer, **valueDict},
    )
    balance = getBalance(alice)

    if depositFirst:

        # alice deposits 10
        market.deposit(
            10 * scale,
            100 * scale,
            {"from": alice, **valueDict},
        )

        # alice buys 1
        market.buy(CALL, 0, 1 * scale, 100 * scale, {"from": alice, **valueDict})

        # alice withdraws 10
        market.withdraw(
            10 * scale,
            0,
            {"from": alice},
        )

        # alice sells 1
        market.sell(CALL, 0, 1 * scale, 0, {"from": alice})

    else:

        # alice buys 1
        market.buy(CALL, 0, 1 * scale, 100 * scale, {"from": alice, **valueDict})

        # alice deposits 10
        market.deposit(
            10 * scale,
            100 * scale,
            {"from": alice, **valueDict},
        )

        # alice sells 1
        market.sell(CALL, 0, 1 * scale, 0, {"from": alice})

        # alice withdraws 10
        market.withdraw(
            10 * scale,
            0,
            {"from": alice},
        )

    assert getBalance(alice) >= balance
