from brownie import reverts
import pytest


SCALE = 10 ** 18


@pytest.mark.parametrize("is_eth", [False, True])
@pytest.mark.parametrize("is_put", [False, True])
def test_options_factory(
    OptionsFactory,
    OptionsMarketMaker,
    OptionsToken,
    MockToken,
    MockOracle,
    accounts,
    is_eth,
    is_put,
):
    deployer = accounts[0]
    marketLibrary = deployer.deploy(OptionsMarketMaker)
    optionsTokenLibrary = deployer.deploy(OptionsToken)

    factory = deployer.deploy(OptionsFactory, marketLibrary, optionsTokenLibrary)
    assert factory.numMarkets() == 0

    if is_eth:
        base_token = "0x0000000000000000000000000000000000000000"
    else:
        base_token = deployer.deploy(MockToken)
        base_token.setDecimals(12)

    quote_token = deployer.deploy(MockToken)
    quote_token.setDecimals(6)

    oracle = deployer.deploy(MockOracle)
    strike_price = 100 * SCALE
    alpha = SCALE // 10
    expiry = 2 * 10 ** 9
    tx = factory.createMarket(
        base_token,
        quote_token,
        oracle,
        is_put,
        strike_price,
        alpha,
        expiry,
    )

    mm = OptionsMarketMaker.at(tx.return_value)
    assert mm.baseToken() == quote_token if is_put else base_token
    assert mm.oracle() == oracle
    assert mm.isPutMarket() == is_put
    assert mm.strikePrice() == strike_price
    assert mm.alpha() == alpha
    assert mm.expiryTime() == expiry

    suffix = "P" if is_put else "C"
    suffix2 = "SP" if is_put else "SC"
    symbol = "ETH" if is_eth else "MOCK"
    if is_put:
        decimals = 6
    else:
        decimals = 18 if is_eth else 12

    longToken = OptionsToken.at(mm.longToken())
    shortToken = OptionsToken.at(mm.shortToken())
    assert longToken.name() == f"{symbol} 18MAY2033 100 {suffix}"
    assert longToken.symbol() == f"{symbol} 18MAY2033 100 {suffix}"
    assert longToken.decimals() == decimals
    assert shortToken.name() == f"{symbol} 18MAY2033 100 {suffix2}"
    assert shortToken.symbol() == f"{symbol} 18MAY2033 100 {suffix2}"
    assert shortToken.decimals() == decimals

    assert factory.numMarkets() == 1
    assert factory.markets(0) == mm
