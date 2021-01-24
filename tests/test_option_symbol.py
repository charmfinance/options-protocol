def test_get_symbol(accounts, OptionSymbol, MockToken):
    deployer = accounts[0]
    lib = deployer.deploy(OptionSymbol)

    assert lib.getMarketSymbol("ETH", 2000000000, True) == "Charm LP ETH 18MAY2033 P"
    assert lib.getMarketSymbol("ETH", 1620000000, False) == "Charm LP ETH 03MAY2021 C"

    assert (
        lib.getOptionSymbol("ETH", 123e18, 2000000000, True, True)
        == "Charm ETH 18MAY2033 123 P"
    )
    assert (
        lib.getOptionSymbol("ETH", 55e17, 1620000000, True, False)
        == "Charm ETH 03MAY2021 5.5 SP"
    )
    assert (
        lib.getOptionSymbol("ETH", 88e15, 1600000000, False, True)
        == "Charm ETH 13SEP2020 0.088 C"
    )
    assert (
        lib.getOptionSymbol("ETH", 88e15, 1600000000, False, False)
        == "Charm ETH 13SEP2020 0.088 SC"
    )
