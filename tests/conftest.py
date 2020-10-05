from brownie import chain
import pytest


@pytest.fixture
def fast_forward():
    def f(future_time):
        sleep_time = future_time - chain.time()
        assert sleep_time > 0
        chain.sleep(sleep_time)

    chain.snapshot()
    yield f
    chain.revert()
