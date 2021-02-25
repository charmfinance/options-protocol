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
@pytest.mark.parametrize("baseDecimals", [6, 18])
def test_option_vault(
    a,
    OptionVault,
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
        OptionVault, baseToken, optionViews, "vault name", "vault symbol"
    )

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
            for contract in [vault, market1]:
                baseToken.approve(contract, 100 * scale, {"from": user})
    valueDict = {"value": 50 * scale} if isEth else {}

    # test set strategy
    with reverts("Ownable: caller is not the owner"):
        vault.setStrategy(strategy, {"from": strategy})
    vault.setStrategy(strategy, {"from": deployer})

    vault.addMarket(market1, {"from": strategy})

    # test deposit
    with reverts("Max slippage exceeded"):
        tx = vault.deposit(10 * scale, 9 * scale, {"from": alice, **valueDict})

    with reverts("Shares out must be > 0"):
        tx = vault.deposit(0, 15 * scale, {"from": alice, **valueDict})

    assert vault.totalAssets() == 0

    balance = getBalance(alice)
    tx = vault.deposit(10 * scale, 15 * scale, {"from": alice, **valueDict})
    assert tx.return_value == 10 * scale
    assert balance - getBalance(alice) == 10 * scale
    assert getBalance(vault) == 10 * scale
    assert vault.balanceOf(alice) == 10 * scale
    assert vault.totalSupply() == 10 * scale
    assert vault.totalAssets() == 10 * scale

    # test buy
    with reverts("!strategy"):
        vault.buy(
            market1,
            [0, 0, 0, 1 * scale, 0, 0],
            [2 * scale, 0, 0, 0, 0, 0],
            2 * scale,
            5 * scale,
            {"from": alice},
        )

    with reverts("Market not found"):
        vault.buy(
            deployer.deploy(OptionMarket),
            [0, 0, 0, 1 * scale, 0, 0],
            [2 * scale, 0, 0, 0, 0, 0],
            2 * scale,
            5 * scale,
            {"from": strategy},
        )

    with reverts("Max slippage exceeded"):
        vault.buy(
            market1,
            [0, 0, 0, 1 * scale, 0, 0],
            [2 * scale, 0, 0, 0, 0, 0],
            2 * scale,
            4 * scale,
            {"from": strategy},
        )

    balance = getBalance(vault)
    dcost = optionViews.getBuyCost(
        market1, [0, 0, 0, 1 * scale, 0, 0], [2 * scale, 0, 0, 0, 0, 0], 2 * scale
    )
    tx = vault.buy(
        market1,
        [0, 0, 0, 1 * scale, 0, 0],
        [2 * scale, 0, 0, 0, 0, 0],
        2 * scale,
        5 * scale,
        {"from": strategy},
    )
    cost1 = scale * lmsr([0, 0, 0, 0, 0, 0, 0], 0)
    cost2 = scale * lmsr([2, 0, 0, 0, 1, 1, 1], 2) + 3 * scale // 100
    assert approx(tx.return_value) == dcost
    assert approx(tx.return_value) == cost2 - cost1
    assert approx(balance - getBalance(vault)) == cost2 - cost1
    assert market1.balanceOf(vault) == 2 * scale
    assert OptionToken.at(market1.longTokens(3)).balanceOf(vault) == 1 * scale
    assert OptionToken.at(market1.shortTokens(0)).balanceOf(vault) == 2 * scale
    assert approx(market1.poolValue(), abs=1) == 3 * scale // 100
    assert vault.totalAssets() == 10 * scale

    # test deposit
    bobBalance = getBalance(bob)
    vaultBalance = getBalance(vault)
    vault.deposit(5 * scale, 15 * scale, {"from": bob, **valueDict})
    assert approx(bobBalance - getBalance(bob)) == 5 * scale + 1.5 * scale // 100
    assert vault.balanceOf(bob) == 5 * scale
    assert vault.totalSupply() == 15 * scale
    assert approx(market1.balanceOf(vault)) == 3 * scale
    assert approx(OptionToken.at(market1.longTokens(3)).balanceOf(vault)) == 1.5 * scale
    assert approx(OptionToken.at(market1.shortTokens(0)).balanceOf(vault)) == 3 * scale
    assert approx(market1.poolValue(), abs=1) == 6 * scale // 100
    assert approx(vault.totalAssets()) == 15 * scale + 1.5 * scale // 100

    # test sell
    with reverts("!strategy"):
        tx = vault.sell(
            market1,
            [0, 0, 0, 1.5 * scale, 0, 0],
            [1 * scale, 0, 0, 0, 0, 0],
            1 * scale,
            1 * scale,
            {"from": alice},
        )

    with reverts("Market not found"):
        tx = vault.sell(
            deployer.deploy(OptionMarket),
            [0, 0, 0, 1.5 * scale, 0, 0],
            [1 * scale, 0, 0, 0, 0, 0],
            1 * scale,
            1 * scale,
            {"from": strategy},
        )

    with reverts("Max slippage exceeded"):
        tx = vault.sell(
            market1,
            [0, 0, 0, 1.5 * scale, 0, 0],
            [1 * scale, 0, 0, 0, 0, 0],
            1 * scale,
            3 * scale,
            {"from": strategy},
        )

    balance = getBalance(vault)
    dcost = optionViews.getSellCost(
        market1, [0, 0, 0, 1.5 * scale, 0, 0], [1 * scale, 0, 0, 0, 0, 0], 1 * scale
    )
    tx = vault.sell(
        market1,
        [0, 0, 0, 1.5 * scale, 0, 0],
        [1 * scale, 0, 0, 0, 0, 0],
        1 * scale,
        1 * scale,
        {"from": strategy},
    )
    cost1 = scale * lmsr([3, 0, 0, 0, 1.5, 1.5, 1.5], 3) + 6 * scale // 100
    cost2 = scale * lmsr([2, 0, 0, 0, 0, 0, 0], 2) + 4 * scale // 100
    assert approx(getBalance(vault) - balance) == cost1 - cost2
    assert approx(tx.return_value) == cost1 - cost2
    assert approx(tx.return_value) == dcost
    assert approx(market1.balanceOf(vault)) == 2 * scale
    assert approx(OptionToken.at(market1.longTokens(3)).balanceOf(vault)) == 0
    assert approx(OptionToken.at(market1.shortTokens(0)).balanceOf(vault)) == 2 * scale
    assert approx(market1.poolValue(), abs=1) == 4 * scale // 100
    assert approx(vault.totalAssets()) == 15 * scale + 1.5 * scale // 100

    # test withdraw
    with reverts("Max slippage exceeded"):
        vault.withdraw(10 * scale, 20 * scale, {"from": alice})

    with reverts("Shares in must be > 0"):
        vault.withdraw(0, 20 * scale, {"from": alice})

    balance = getBalance(vault)
    tx = vault.withdraw(10 * scale, 10 * scale, {"from": alice})
    cost = scale * lmsr([2, 0, 0, 0, 0, 0, 0], 2) + 4 * scale // 100
    assert approx(balance - getBalance(vault)) == balance * 2.0 / 3
    assert approx(tx.return_value) == (cost + balance) * 2.0 / 3
    assert approx(market1.balanceOf(vault), rel=1e-5, abs=1) == 2.0 / 3 * scale
    assert approx(OptionToken.at(market1.longTokens(3)).balanceOf(vault), abs=1) == 0
    assert (
        approx(OptionToken.at(market1.shortTokens(0)).balanceOf(vault), rel=1e-5, abs=1)
        == 2.0 / 3 * scale
    )
    assert approx(market1.poolValue(), rel=1e-5, abs=1) == 4.0 / 3 * scale // 100
    assert approx(vault.totalAssets()) == 5 * scale + 0.5 * scale // 100

    balance = getBalance(vault)
    tx = vault.withdraw(5 * scale, 5 * scale, {"from": bob})
    cost = scale * lmsr([2.0 / 3, 0, 0, 0, 0, 0, 0], 2.0 / 3) + 4.0 / 3 * scale // 100
    assert getBalance(vault) == 0
    assert approx(tx.return_value) == cost + balance
    assert approx(market1.balanceOf(vault)) == 0
    assert approx(OptionToken.at(market1.longTokens(3)).balanceOf(vault), abs=1) == 0
    assert approx(OptionToken.at(market1.shortTokens(0)).balanceOf(vault), abs=1) == 0
    assert approx(market1.poolValue()) == 0
    assert vault.totalAssets() == 0

    # test add new markets
    market2 = deployMarket(baseToken)
    market3 = deployMarket(baseToken)
    market4 = deployMarket(deployer.deploy(MockToken))

    assert vault.numMarkets() == 1
    assert vault.allMarkets() == [market1]

    with reverts("!strategy"):
        vault.addMarket(market2, {"from": deployer})

    vault.addMarket(market2, {"from": strategy})
    vault.addMarket(market3, {"from": strategy})
    assert vault.numMarkets() == 3
    assert vault.allMarkets() == [market1, market2, market3]

    with reverts("!strategy"):
        vault.removeMarket(market2, {"from": alice})

    with reverts("Market not found"):
        vault.removeMarket(market4, {"from": strategy})

    vault.removeMarket(market2, {"from": strategy})
    assert vault.numMarkets() == 2
    assert vault.allMarkets() == [market1, market3]

    with reverts("Base tokens don't match"):
        vault.addMarket(market4, {"from": strategy})

    # test pause and unpause
    with reverts("Ownable: caller is not the owner"):
        vault.pause({"from": strategy})

    vault.pause({"from": deployer})
    vault.pause({"from": deployer})
    with reverts("Paused"):
        vault.deposit(10 * scale, 15 * scale, {"from": alice, **valueDict})

    with reverts("Ownable: caller is not the owner"):
        vault.unpause({"from": strategy})

    vault.unpause({"from": deployer})
    vault.unpause({"from": deployer})
    vault.deposit(10 * scale, 15 * scale, {"from": alice, **valueDict})
    vault.buy(
        market1,
        [0, 0, 0, 1 * scale, 0, 0],
        [2 * scale, 0, 0, 0, 0, 0],
        2 * scale,
        5 * scale,
        {"from": strategy},
    )

    with reverts("Ownable: caller is not the owner"):
        vault.emergencyWithdraw(vault.baseToken(), {"from": strategy})

    balance = getBalance(deployer)
    assert approx(getBalance(vault)) == 5.236170 * scale
    vault.emergencyWithdraw(vault.baseToken(), {"from": deployer})
    assert approx(getBalance(deployer) - balance) == 5.236170 * scale
    assert getBalance(vault) == 0

    longToken = OptionToken.at(market1.longTokens(3))
    assert longToken.balanceOf(deployer) == 0
    assert longToken.balanceOf(vault) == 1 * scale
    vault.emergencyWithdraw(market1.longTokens(3), {"from": deployer})
    assert longToken.balanceOf(deployer) == 1 * scale
    assert longToken.balanceOf(vault) == 0
