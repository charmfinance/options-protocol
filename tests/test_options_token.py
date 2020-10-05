from brownie import reverts


def test_option_token(OptionsToken, accounts):
    owner = accounts[0]
    user = accounts[1]

    token = OptionsToken.deploy("NAME", "SYMBOL", {"from": owner})
    assert token.name() == "NAME"
    assert token.symbol() == "SYMBOL"
    assert token.totalSupply() == 0
    assert token.owner() == owner

    with reverts():
        token.mint(user, 123, {"from": user})

    token.mint(user, 123, {"from": owner})
    assert token.totalSupply() == 123
    assert token.balanceOf(user) == 123

    with reverts():
        token.burn(user, 100, {"from": user})

    token.burn(user, 100, {"from": owner})
    assert token.totalSupply() == 23
    assert token.balanceOf(user) == 23

    with reverts():
        token.burn(user, 100, {"from": owner})
