from brownie import reverts, ZERO_ADDRESS
import pytest
from pytest import approx


SCALE = 10 ** 18


def lmsr(q, b):
    from math import exp, log

    mx = max(q)
    if b == 0:
        return mx

    a = sum(exp((x - mx) / b) for x in q)
    return mx + b * log(a)


@pytest.mark.parametrize("isEth", [False, True])
@pytest.mark.parametrize("baseDecimals", [8, 18])
def test_option_lp_vault(
    a,
    OptionLpVault,
    OptionMarket,
    OptionToken,
    OptionViews,
    MockOracle,
    MockToken,
    isEth,
    baseDecimals,
):

    # set up accounts
    deployer, strategy, alice, bob = a[:4]

    # set up contracts
    if isEth:
        scale = 1e18
        baseToken = ZERO_ADDRESS
    else:
        scale = 10 ** baseDecimals
        baseToken = deployer.deploy(MockToken)
        baseToken.setDecimals(baseDecimals)

    optionViews = deployer.deploy(OptionViews)
    vault = deployer.deploy(
        OptionLpVault, baseToken, optionViews, "vault name", "vault symbol"
    )
    vault.setDepositFee(1e16, {"from": deployer})

    # check vault variables
    assert vault.name() == "vault name"
    assert vault.symbol() == "vault symbol"
    assert vault.decimals() == 18 if isEth else baseDecimals

    def getBalance(wallet):
        return wallet.balance() if isEth else baseToken.balanceOf(wallet)

    def deployMarket(baseToken):
        market = deployer.deploy(OptionMarket)
        longTokens = [deployer.deploy(OptionToken) for _ in range(6)]
        shortTokens = [deployer.deploy(OptionToken) for _ in range(6)]
        market.initialize(
            baseToken,
            deployer.deploy(MockOracle),
            longTokens,
            shortTokens,
            [
                300 * SCALE,
                400 * SCALE,
                500 * SCALE,
                600 * SCALE,
                700 * SCALE,
                800 * SCALE,
            ],
            2000000000,  # expiry = 18 May 2033
            False,
            SCALE // 100,
            "symbol",
        )
        for token in longTokens + shortTokens:
            token.initialize(market, "name", "symbol", baseDecimals)
        return market

    market1 = deployMarket(baseToken)

    # give users base tokens
    if not isEth:
        for user in [deployer, alice, bob]:
            baseToken.mint(user, 100 * scale, {"from": deployer})
            baseToken.approve(vault, 100 * scale, {"from": user})
            baseToken.approve(market1, 100 * scale, {"from": user})
    valueDict = {"value": 50 * scale} if isEth else {}

    # alice deposits 10
    bobBalance = getBalance(bob)
    tx = vault.deposit(10 * scale, alice, {"from": bob, **valueDict})
    assert approx(bobBalance - getBalance(bob)) == 10 * scale
    assert approx(vault.balanceOf(alice)) == 9.9 * scale
    assert approx(tx.return_value) == 9.9 * scale
    assert approx(vault.estimatedTotalAssets()) == 10 * scale
    assert approx(vault.totalAssets()) == 10 * scale

    # add market
    with reverts("!manager"):
        vault.addMarket(market1, {"from": alice})
    vault.addMarket(market1, {"from": deployer})
    assert vault.numMarkets() == 1
    assert vault.markets(0) == market1

    # only manager can buy
    with reverts("!manager"):
        vault.buy(
            market1,
            [0, 0, 0, 0, 0, 1 * scale],
            [3 * scale, 0, 0, 0, 0, 0],
            1 * scale,
            20 * scale,
            {"from": alice},
        )

    with reverts("Max slippage exceeded"):
        vault.buy(
            market1,
            [0, 0, 0, 0, 0, 100 * scale],
            [300 * scale, 0, 0, 0, 0, 0],
            100 * scale,
            20 * scale,
            {"from": deployer},
        )

    with reverts("Max slippage exceeded"):
        vault.buy(
            market1,
            [0, 0, 0, 0, 0, 100 * scale],
            [300 * scale, 0, 0, 0, 0, 0],
            100 * scale,
            2000 * scale,
            {"from": deployer},
        )

    # buy
    vault.buy(
        market1,
        [0, 0, 0, 0, 0, 1 * scale],
        [3 * scale, 0, 0, 0, 0, 0],
        1 * scale,
        20 * scale,
        {"from": deployer},
    )
    cost = (
        optionViews.getSellCost(
            market1,
            [0, 0, 0, 0, 0, 1 * scale // 1000],
            [3 * scale // 1000, 0, 0, 0, 0, 0],
            1 * scale // 1000,
        )
        * 1000
    )
    assert approx(getBalance(vault)) == 10 * scale - cost
    assert market1.balanceOf(vault) == 1 * scale
    assert OptionToken.at(market1.longTokens(5)).balanceOf(vault) == 1 * scale
    assert OptionToken.at(market1.shortTokens(0)).balanceOf(vault) == 3 * scale
    assert approx(vault.estimatedTotalAssets()) == 10 * scale

    # alice buys so total assets will change
    market1.buy(True, 5, 1 * scale, 2 * scale, {"from": alice, **valueDict})
    cost = (
        optionViews.getSellCost(
            market1,
            [0, 0, 0, 0, 0, 1 * scale // 1000],
            [3 * scale // 1000, 0, 0, 0, 0, 0],
            1 * scale // 1000,
        )
        * 1000
    )
    assert approx(vault.estimatedTotalAssets()) == getBalance(vault) + cost

    assert approx(vault.totalAssets()) == 10 * scale
    vault.updateTotalAssets({"from": alice})
    assert approx(vault.totalAssets()) == getBalance(vault) + cost

    # can't withdraw too much because not enough base balance in vault
    aliceShares = vault.balanceOf(alice)
    with reverts("Not enough free balance in vault"):
        vault.withdraw(aliceShares * 0.7, bob, {"from": alice})

    # alice withdraws 20%
    bobBalance = getBalance(bob)
    vaultBalance = getBalance(vault)
    totalAssets = vault.totalAssets()
    tx = vault.withdraw(aliceShares * 0.2, bob, {"from": alice})
    assert approx(getBalance(bob) - bobBalance) == totalAssets * 0.2
    assert approx(vaultBalance - getBalance(vault)) == totalAssets * 0.2
    assert (
        approx(vault.totalAssets())
        == approx(vault.estimatedTotalAssets())
        == totalAssets * 0.8
    )
    assert approx(vault.balanceOf(alice)) == aliceShares * 0.8

    # alice force withdraws 20%
    aliceShares = vault.balanceOf(alice)
    shares = 0.2 * aliceShares
    bobBalance = getBalance(bob)
    vaultBalance = getBalance(vault)
    vaultOptions1 = OptionToken.at(market1.longTokens(5)).balanceOf(vault)
    vaultOptions2 = OptionToken.at(market1.shortTokens(0)).balanceOf(vault)
    vault.withdrawTokens(shares, bob, {"from": alice})
    assert approx(getBalance(vault)) == 0.8 * vaultBalance
    assert OptionToken.at(market1.longTokens(5)).balanceOf(vault) == 0.8 * vaultOptions1
    assert (
        OptionToken.at(market1.shortTokens(0)).balanceOf(vault) == 0.8 * vaultOptions2
    )
    assert approx(getBalance(bob) - bobBalance) == 0.2 * vaultBalance
    assert OptionToken.at(market1.longTokens(5)).balanceOf(bob) == 0.2 * vaultOptions1
    assert OptionToken.at(market1.shortTokens(0)).balanceOf(bob) == 0.2 * vaultOptions2
    assert approx(vault.balanceOf(alice)) == aliceShares * 0.8


def test_governance_methods(
    a,
    OptionLpVault,
    OptionMarket,
    OptionToken,
    OptionViews,
    MockOracle,
    MockToken,
):

    # set up accounts
    deployer, manager, alice = a[:3]

    def deployMarket(baseToken):
        market = deployer.deploy(OptionMarket)
        longTokens = [deployer.deploy(OptionToken) for _ in range(6)]
        shortTokens = [deployer.deploy(OptionToken) for _ in range(6)]
        market.initialize(
            baseToken,
            deployer.deploy(MockOracle),
            longTokens,
            shortTokens,
            [
                300 * SCALE,
                400 * SCALE,
                500 * SCALE,
                600 * SCALE,
                700 * SCALE,
                800 * SCALE,
            ],
            2000000000,  # expiry = 18 May 2033
            False,
            SCALE // 100,
            "symbol",
        )
        for token in longTokens + shortTokens:
            token.initialize(market, "name", "symbol", 18)
        return market

    baseToken = deployer.deploy(MockToken)
    baseToken.setDecimals(18)
    scale = 1e18

    optionViews = deployer.deploy(OptionViews)
    vault = deployer.deploy(
        OptionLpVault, baseToken, optionViews, "vault name", "vault symbol"
    )
    vault.setManager(manager)

    # test add new markets
    market1 = deployMarket(baseToken)
    market2 = deployMarket(baseToken)
    market3 = deployMarket(baseToken)
    market4 = deployMarket(deployer.deploy(MockToken))

    for user in [deployer, alice]:
        baseToken.mint(user, 100 * scale, {"from": deployer})
        baseToken.approve(vault, 100 * scale, {"from": user})
        baseToken.approve(market1, 100 * scale, {"from": user})

    with reverts("!manager"):
        vault.addMarket(market1, {"from": deployer})

    vault.addMarket(market1, {"from": manager})
    assert vault.numMarkets() == 1
    assert vault.markets(0) == market1

    vault.addMarket(market2, {"from": manager})
    assert vault.numMarkets() == 2
    assert vault.markets(0) == market1
    assert vault.markets(1) == market2

    with reverts("!manager"):
        vault.removeMarket(market2, {"from": alice})

    with reverts("Market not found"):
        vault.removeMarket(market4, {"from": manager})

    vault.removeMarket(market1, {"from": manager})
    assert vault.numMarkets() == 1
    assert vault.markets(0) == market2

    vault.addMarket(market1, {"from": manager})
    vault.addMarket(market3, {"from": manager})
    assert vault.numMarkets() == 3
    assert vault.markets(0) == market2
    assert vault.markets(1) == market1
    assert vault.markets(2) == market3

    vault.removeMarket(market2, {"from": manager})
    assert vault.numMarkets() == 2
    assert vault.markets(0) == market1
    assert vault.markets(1) == market3

    with reverts("Base tokens don't match"):
        vault.addMarket(market4, {"from": manager})

    # test pause and unpause
    with reverts("Ownable: caller is not the owner"):
        vault.pause({"from": manager})

    vault.pause({"from": deployer})
    vault.pause({"from": deployer})
    with reverts("Paused"):
        vault.deposit(10 * scale, alice, {"from": alice})

    with reverts("Ownable: caller is not the owner"):
        vault.unpause({"from": manager})

    vault.unpause({"from": deployer})
    vault.unpause({"from": deployer})
    vault.deposit(10 * scale, alice, {"from": alice})
    vault.buy(
        market1,
        [0, 0, 0, 1 * scale, 0, 0],
        [2 * scale, 0, 0, 0, 0, 0],
        2 * scale,
        5 * scale,
        {"from": manager},
    )

    # test emergency withdraw
    with reverts("Ownable: caller is not the owner"):
        vault.emergencyWithdraw(vault.baseToken(), 3 * scale, {"from": manager})

    balance = baseToken.balanceOf(deployer)
    assert approx(baseToken.balanceOf(vault)) == 5.236170 * scale
    vault.emergencyWithdraw(vault.baseToken(), 3 * scale, {"from": deployer})
    assert approx(baseToken.balanceOf(deployer) - balance) == 3 * scale
    assert approx(baseToken.balanceOf(vault)) == 2.236170 * scale

    longToken = OptionToken.at(market1.longTokens(3))
    assert longToken.balanceOf(deployer) == 0
    assert longToken.balanceOf(vault) == 1 * scale
    vault.emergencyWithdraw(market1.longTokens(3), 1 * scale, {"from": deployer})
    assert longToken.balanceOf(deployer) == 1 * scale
    assert longToken.balanceOf(vault) == 0
