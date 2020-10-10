from brownie import reverts


def test_charm_token(CharmToken, accounts):
    deployer, user = accounts[:2]
    charm = deployer.deploy(CharmToken)
    assert charm.name() == "Charm"
    assert charm.symbol() == "CHARM"
    assert charm.governance() == deployer

    # check permissions
    with reverts("!governance"):
        charm.setGovernance(user, {"from": user})

    with reverts("!minter"):
        charm.mint(user, 1e18, {"from": user})

    with reverts("!governance"):
        charm.addMinter(user, {"from": user})

    with reverts("!governance"):
        charm.removeMinter(user, {"from": user})

    # add user as minter and mint 1
    charm.addMinter(user, {"from": deployer})
    assert charm.balanceOf(user) == 0
    charm.mint(user, 1e18, {"from": user})
    assert charm.balanceOf(user) == 1e18

    with reverts("!minter"):
        charm.mint(user, 1e18, {"from": deployer})

    # remove user as minter and check they can't mint any more
    charm.removeMinter(user, {"from": deployer})
    with reverts("!minter"):
        charm.mint(user, 1e18, {"from": user})

    # set user as governance
    charm.setGovernance(user, {"from": deployer})
    assert charm.governance() == user
