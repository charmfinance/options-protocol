from brownie import reverts


def test_option_token(OptionsMarketMaker, OptionsToken, accounts):
    deployer = accounts[0]
    user = accounts[1]
    owner = accounts[2]

    token = OptionsToken.deploy({"from": deployer})
    token.initialize(owner, "NAME", "SYMBOL", 12, {"from": deployer})
    assert token.name() == "NAME"
    assert token.symbol() == "SYMBOL"
    assert token.decimals() == 12
    assert token.totalSupply() == 0
    assert token.marketMaker() == owner

    with reverts("!marketMaker"):
        token.mint(user, 123, {"from": user})
    with reverts("!marketMaker"):
        token.mint(user, 123, {"from": deployer})

    token.mint(user, 123, {"from": owner})
    assert token.totalSupply() == 123
    assert token.balanceOf(user) == 123

    with reverts("!marketMaker"):
        token.burn(user, 100, {"from": user})

    token.burn(user, 100, {"from": owner})
    assert token.totalSupply() == 23
    assert token.balanceOf(user) == 23

    with reverts("ERC20: burn amount exceeds balance"):
        token.burn(user, 100, {"from": owner})
