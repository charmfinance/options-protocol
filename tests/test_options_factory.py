from brownie import reverts
import pytest


SCALE = 10 ** 18


@pytest.mark.parametrize("isEth", [False, True])
def test_options_factory(
    OptionsFactory,
    OptionsMarketMaker,
    OptionsToken,
    MockToken,
    MockOracle,
    accounts,
    isEth,
):
    deployer = accounts[0]
    marketLibrary = deployer.deploy(OptionsMarketMaker)
    optionsTokenLibrary = deployer.deploy(OptionsToken)

    factory = deployer.deploy(OptionsFactory, marketLibrary, optionsTokenLibrary)
    assert factory.numMarkets() == 0

    if isEth:
        base_token = "0x0000000000000000000000000000000000000000"
    else:
        base_token = deployer.deploy(MockToken)
        base_token.setDecimals(6)
    oracle = deployer.deploy(MockOracle)
    is_put = False
    strike_price = 100 * SCALE
    alpha = SCALE // 10
    expiry = 2 * 10 ** 9
    tx = factory.createMarket(
        base_token,
        oracle,
        is_put,
        strike_price,
        alpha,
        expiry,
        "long name",
        "long symbol",
        "short name",
        "short symbol",
    )

    mm = OptionsMarketMaker.at(tx.return_value)
    assert mm.baseToken() == base_token
    assert mm.oracle() == oracle
    assert mm.isPutMarket() == is_put
    assert mm.strikePrice() == strike_price
    assert mm.alpha() == alpha
    assert mm.expiryTime() == expiry

    longToken = OptionsToken.at(mm.longToken())
    shortToken = OptionsToken.at(mm.shortToken())
    assert longToken.name() == "long name"
    assert longToken.symbol() == "long symbol"
    assert longToken.decimals() == 18 if isEth else 6
    assert shortToken.name() == "short name"
    assert shortToken.symbol() == "short symbol"
    assert shortToken.decimals() == 18 if isEth else 6

    assert factory.numMarkets() == 1
    assert factory.markets(0) == mm
