from brownie import reverts


def test_one_feed(ChainlinkOracle, MockAggregatorV3Interface, accounts):
    deployer = accounts[0]

    priceFeed = deployer.deploy(MockAggregatorV3Interface)
    priceFeed.setDecimals(8)

    zero_address = "0x0000000000000000000000000000000000000000"
    oracle = deployer.deploy(ChainlinkOracle, priceFeed, zero_address)

    with reverts("Round not complete"):
        oracle.getPrice()

    priceFeed.setTimestamp(10000)
    with reverts("Price is not > 0"):
        oracle.getPrice()

    priceFeed.setPrice(111e8)
    assert oracle.getPrice() == 111e18


def test_two_feeds(ChainlinkOracle, MockAggregatorV3Interface, accounts):
    deployer = accounts[0]

    priceFeed1 = deployer.deploy(MockAggregatorV3Interface)
    priceFeed1.setDecimals(8)

    priceFeed2 = deployer.deploy(MockAggregatorV3Interface)
    priceFeed2.setDecimals(5)

    oracle = deployer.deploy(ChainlinkOracle, priceFeed1, priceFeed2)

    with reverts("Round not complete"):
        oracle.getPrice()

    priceFeed1.setTimestamp(10000)
    priceFeed2.setTimestamp(20000)
    with reverts("Price is not > 0"):
        oracle.getPrice()

    priceFeed1.setPrice(111e8)
    priceFeed2.setPrice(2e5)
    assert oracle.getPrice() == 222e18
