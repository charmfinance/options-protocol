"""
Implementation of cost function described in Othman et al., 2013

This script can be used to double check numerical values in OptionsMarketMaker
unit tests

Usage:
>> python calc_lslmsr_cost.py <q1> <q2> <liquidity_param>

liquidity_param describes maximum possible sum of prices - 1. It's equal to alpha * 2 log 2

Answer is multipled by 10^18 and printed as an integer

"""

import mpmath
from mpmath import exp, log, mpf


U = 10 ** 18
mpmath.prec = 300


def cost(q, alpha):
    b = alpha * sum(q)
    if b == 0:
        return 0
    mx = max(q)
    a = sum(exp((x - mx) / b) for x in q)
    return mx + b * log(a)


if __name__ == "__main__":
    import sys

    _, q1, q2, liquidity_param = sys.argv

    q1 = mpf(int(q1))
    q2 = mpf(int(q2))
    liquidity_param = mpf(float(liquidity_param))

    alpha = liquidity_param / 2.0 / log(2.0)
    ans = cost([q1, q2], alpha)
    print(int(ans * U))
