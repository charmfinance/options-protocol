from brownie import reverts


def test_option_token(OptionToken, OptionMarket, a):
    deployer, market, alice = a[:3]

    token = OptionToken.deploy({"from": deployer})
    token.initialize(market, "NAME", "SYMBOL", 12, {"from": deployer})
    assert token.name() == "NAME"
    assert token.symbol() == "SYMBOL"
    assert token.decimals() == 12
    assert token.totalSupply() == 0
    assert token.market() == market

    with reverts("!market"):
        token.mint(alice, 123, {"from": alice})
    with reverts("!market"):
        token.mint(alice, 123, {"from": deployer})

    token.mint(alice, 123, {"from": market})
    assert token.totalSupply() == 123
    assert token.balanceOf(alice) == 123

    with reverts("!market"):
        token.burn(alice, 100, {"from": alice})

    token.burn(alice, 100, {"from": market})
    assert token.totalSupply() == 23
    assert token.balanceOf(alice) == 23

    with reverts("ERC20: burn amount exceeds balance"):
        token.burn(alice, 100, {"from": market})
