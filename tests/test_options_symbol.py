def test_get_symbol(accounts, OptionsSymbol, MockToken):
    deployer = accounts[0]
    lib = deployer.deploy(OptionsSymbol)
    assert lib.getSymbol("ETH", 123e18, 2000000000, True, True) == "ETH 18MAY2033 123 P"
    assert (
        lib.getSymbol("ETH", 55e17, 1620000000, True, False) == "ETH 03MAY2021 5.5 SP"
    )
    assert (
        lib.getSymbol("ETH", 88e15, 1600000000, False, True) == "ETH 13SEP2020 0.088 C"
    )
    assert (
        lib.getSymbol("ETH", 88e15, 1600000000, False, False)
        == "ETH 13SEP2020 0.088 CV"
    )
