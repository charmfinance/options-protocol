from brownie import reverts
import pytest


SCALE = 10 ** 18


@pytest.mark.parametrize("isEth", [False, True])
@pytest.mark.parametrize("isPut", [False, True])
def test_option_factory(
    a,
    OptionFactory,
    OptionMarket,
    OptionToken,
    MockToken,
    MockOracle,
    isEth,
    isPut,
):
    deployer = a[0]
    optionMarketLibrary = deployer.deploy(OptionMarket)
    optionTokenLibrary = deployer.deploy(OptionToken)

    factory = deployer.deploy(OptionFactory, optionMarketLibrary, optionTokenLibrary)
    assert factory.numMarkets() == 0

    if isEth:
        baseToken = "0x0000000000000000000000000000000000000000"
    else:
        baseToken = deployer.deploy(MockToken)
        baseToken.setDecimals(12)

    quoteToken = deployer.deploy(MockToken)
    quoteToken.setDecimals(6)

    oracle = deployer.deploy(MockOracle)
    tx = factory.createMarket(
        baseToken,
        quoteToken,
        oracle,
        [300 * SCALE, 400 * SCALE, 500 * SCALE],  # strikes
        2000000000,  # expiry
        isPut,
        SCALE // 100,  # trading fee
        40 * SCALE,  # balance limit
    )

    market = OptionMarket.at(tx.return_value)
    assert market.baseToken() == quoteToken if isPut else baseToken
    assert market.oracle() == oracle
    assert market.isPut() == isPut
    assert market.numStrikes() == 3
    assert market.strikePrices(0) == 300 * SCALE
    assert market.strikePrices(1) == 400 * SCALE
    assert market.strikePrices(2) == 500 * SCALE
    assert market.expiryTime() == 2000000000
    assert market.balanceLimit() == 40 * SCALE
    assert market.b() == 0

    suffix = "P" if isPut else "C"
    suffix2 = "SP" if isPut else "SC"
    symbol = "ETH" if isEth else "MOCK"
    if isPut:
        decimals = 6
    else:
        decimals = 18 if isEth else 12

    for i, strike in enumerate([300, 400, 500]):
        longToken = OptionToken.at(market.longTokens(i))
        shortToken = OptionToken.at(market.shortTokens(i))
        assert longToken.name() == f"{symbol} 18MAY2033 {strike} {suffix}"
        assert longToken.symbol() == f"{symbol} 18MAY2033 {strike} {suffix}"
        assert longToken.decimals() == decimals
        assert shortToken.name() == f"{symbol} 18MAY2033 {strike} {suffix2}"
        assert shortToken.symbol() == f"{symbol} 18MAY2033 {strike} {suffix2}"
        assert shortToken.decimals() == decimals

    assert factory.numMarkets() == 1
    assert factory.markets(0) == market
