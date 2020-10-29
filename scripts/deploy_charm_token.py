from brownie import accounts, CharmToken


ACCOUNT = "charm"


def main():
    deployer = accounts.load(ACCOUNT)
    charm_token = CharmToken.deploy({"from": deployer})
    charm_token.addMinter(deployer, {"from": deployer})
