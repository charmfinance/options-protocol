from brownie import reverts
import pytest


SCALE = 10 ** 18
Q112 = 1 << 112


TIME1 = 2500000000  # 18 May 2033, initial time in UniswapOracle
TIME2 = 2510000000
TIME3 = 2600000000  # twap start time
TIME4 = 2610000000


def test_oracle_base_token(
    UniswapOracle, MockUniswapV2Pair, OptionsToken, accounts, fast_forward
):
    address = accounts[0]
    eth = address.deploy(OptionsToken, "Ether", "ETH")
    usd = address.deploy(OptionsToken, "USD Coin", "USD")
    pair = address.deploy(MockUniswapV2Pair, eth, usd)

    multiplier = 10 ** 12

    # can't deploy if pair's reserves are 0
    with reverts("No reserves"):
        oracle = address.deploy(
            UniswapOracle,
            pair,
            TIME3,  # twap start time
            18,  # eth decimals
            6,  # usdc decimals
            False,
        )

    # set spot price of 1 eth = 400 usd
    # set the cumulative price to 100000 * 300, so price has historically been 300 / multiplier
    pair.setPrice0CumulativeLast(100000 * Q112 * 300 // multiplier)
    pair.setPrice1CumulativeLast(100000 * Q112 * multiplier // 300)
    pair.setReserve0(10 * 10 ** 18)  # decimal places = 18
    pair.setReserve1(4000 * 10 ** 6)  # decimal places = 6
    pair.setBlockTimestampLast(TIME1)
    assert pair.getReserves() == (10 * 10 ** 18, 4000 * 10 ** 6, TIME1)

    # we can now deploy an eth/usd and an usd/eth oracle
    fast_forward(TIME1)
    oracle = address.deploy(
        UniswapOracle,
        pair,
        TIME3,  # update time
        18,  # eth decimals
        6,  # usdc decimals
        False,
    )
    assert not oracle.isInverted()
    assert oracle.baseMultiplier() == 10 ** 12
    assert oracle.quoteMultiplier() == 1

    assert oracle.snapshotTimestamp() in [TIME1, TIME1 + 1]

    # uses spot price if no time elapsed
    assert oracle.snapshotSpotPrice() == 400 * SCALE
    assert oracle.getPrice() == 400 * SCALE

    # the test below is commented out because it's flaky
    # takeSnapshot might be in the same block as deploy or the block after

    # oracle.takeSnapshot()
    # assert oracle.snapshotTimestamp() == TIME1
    # assert oracle.fetchSpotAndCumulativePrice() == (10 ** 12 * 400, 100000 * Q112 * 300)

    # move time forward and check price. It hasn't moved in the oracle so should
    # be equal to the spot price of 400
    fast_forward(TIME2)
    assert oracle.getPrice() == 400 * SCALE

    # take snapshot
    oracle.takeSnapshot()
    assert oracle.snapshotTimestamp() in [TIME2, TIME2 + 1]
    assert oracle.getPrice() == 400 * SCALE

    # it should now incorporate the new spot price of 400
    last = 100000 * Q112 * 300 // multiplier
    since_last = (oracle.snapshotTimestamp() - TIME1) * Q112 * 400 // multiplier
    assert oracle.fetchSpotAndCumulativePrice() == (400 * SCALE, last + since_last)

    # move time forward to after window starts so takeSnapshot() can't be called again
    fast_forward(TIME4)
    with reverts("TWAP window already started"):
        oracle.takeSnapshot()

    # set cumulative price to 500
    last = 100000 * Q112 * 300 // multiplier
    since_last = (TIME4 - TIME1) * Q112 * 500 // multiplier
    pair.setPrice0CumulativeLast(last + since_last)

    last2 = 100000 * Q112 * multiplier // 300
    since_last2 = (TIME4 - TIME1) * Q112 * multiplier // 500
    pair.setPrice1CumulativeLast(last2 + since_last2)

    pair.setBlockTimestampLast(TIME4)
    oracle.getPrice() == 500 * SCALE


def test_oracle_quote_token(
    UniswapOracle, MockUniswapV2Pair, OptionsToken, accounts, fast_forward
):
    address = accounts[0]
    eth = address.deploy(OptionsToken, "Ether", "ETH")
    usd = address.deploy(OptionsToken, "USD Coin", "USD")
    pair = address.deploy(MockUniswapV2Pair, eth, usd)

    multiplier = 10 ** 12

    # set spot price of 1 eth = 400 usd
    # set the cumulative price to 100000 * 300, so price has historically been 300
    pair.setPrice0CumulativeLast(100000 * Q112 * 300 // multiplier)
    pair.setPrice1CumulativeLast(100000 * Q112 * multiplier // 300)
    pair.setReserve0(10 * 10 ** 18)  # decimal places = 18
    pair.setReserve1(4000 * 10 ** 6)  # decimal places = 6
    pair.setBlockTimestampLast(TIME1)
    assert pair.getReserves() == (10 * 10 ** 18, 4000 * 10 ** 6, TIME1)

    # we can now deploy an eth/usd and an usd/eth oracle
    fast_forward(TIME1)
    oracle = address.deploy(
        UniswapOracle,
        pair,
        TIME3,  # update time
        18,  # eth decimals
        6,  # usdc decimals
        True,
    )
    assert oracle.isInverted()
    assert oracle.baseMultiplier() == 1
    assert oracle.quoteMultiplier() == 10 ** 12

    assert oracle.snapshotTimestamp() in [TIME1, TIME1 + 1]

    # uses spot price if no time elapsed
    assert oracle.snapshotSpotPrice() == SCALE // 400
    assert oracle.getPrice() == SCALE // 400

    # move time forward and check price. It hasn't moved in the oracle so should
    # be equal to the spot price of 400
    fast_forward(TIME2)
    assert oracle.getPrice() == SCALE // 400

    # take snapshot
    oracle.takeSnapshot()
    assert oracle.snapshotTimestamp() in [TIME2, TIME2 + 1]
    assert oracle.getPrice() == SCALE // 400

    # it should now incorporate the new spot price of 400
    last = 100000 * Q112 * multiplier // 300
    since_last = (oracle.snapshotTimestamp() - TIME1) * Q112 * multiplier // 400
    assert oracle.fetchSpotAndCumulativePrice() == (SCALE // 400, last + since_last)

    # move time forward to after window starts so takeSnapshot() can't be called again
    fast_forward(TIME4)
    with reverts("TWAP window already started"):
        oracle.takeSnapshot()

    # set cumulative price to 500
    last = 100000 * Q112 * 300 // multiplier
    since_last = (TIME4 - TIME1) * Q112 * 500 // multiplier
    pair.setPrice0CumulativeLast(last + since_last)

    last2 = 100000 * Q112 * multiplier // 300
    since_last2 = (TIME4 - TIME1) * Q112 * multiplier // 500
    pair.setPrice1CumulativeLast(last2 + since_last2)

    pair.setBlockTimestampLast(TIME4)
    oracle.getPrice() == SCALE // 500
