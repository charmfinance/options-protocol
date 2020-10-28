from brownie import reverts


def test_chainlink_oracle(ChainlinkOracle, MockAggregatorV3Interface, accounts):
    deployer = accounts[0]

    priceFeed = deployer.deploy(MockAggregatorV3Interface)
    priceFeed.setDecimals(8)

    oracle = deployer.deploy(ChainlinkOracle, priceFeed)

    with reverts("Round not complete"):
        oracle.getPrice()

    priceFeed.setTimestamp(10000)
    with reverts("Price is not > 0"):
        oracle.getPrice()

    priceFeed.setPrice(123e8)
    assert oracle.getPrice() == 123e18
