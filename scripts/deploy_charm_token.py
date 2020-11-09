from brownie import accounts, CharmToken


ACCOUNT = "deployer"


def main():
    deployer = accounts.load(ACCOUNT)
    charm_token = CharmToken.deploy({"from": deployer})
    charm_token.addMinter(deployer, {"from": deployer})
