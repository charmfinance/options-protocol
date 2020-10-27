# Charm Finance

Charm Finance is an AMM (automated market-maker) for options on Ethereum

It uses an LS-LMSR (Othman et al., 2013) to price the options. In short, it acts like token bonding curve, minting/burning option tokens as users buy/sell them.

At expiration, the settlement price is fetched from a Uniswap V2 oracle. Users can them redeem their options for the settlement value

This repo also includes an ERC20 governance token and staking reward pools


## Owner privileges

Please note the owner of the options market is highly privileged and has the permissions below. These are only intended to be used in an emergency situation. These permissions will be removed in future versions.

- Pause the contract indefinitely. This includes preventing users from buying, selling, and redeeming their options.

- Change the contract’s oracle. If an invalid or malicious oracle is provided, users can potentially lose funds.

- Change the contract’s expiry date.

- Prematurely settle the contract before its expiry date.


## Repo

The main contract is `OptionsMarketMaker.sol`. This contains methods `buy` and `sell` that let users mint/burn options. Calling `settle` after expiration fetches the settlement price from the oracle and users can call `redeem` to redeem their options for the settlement value.

`OptionsToken.sol` is an ERC20 token representing ownership of an option.

`UniswapOracle.sol` is used by `OptionsMarketMaker.sol` to fetch the TWAP price at expiration from a Uniswap market.

`CharmToken.sol` is an ERC20 token that will be distributed as incentives/rewards and used for governance

`rewards/StakingRewards.sol` let users stake an ERC20 token to receive Charm tokens. It's based on `https://github.com/Synthetixio/synthetix/blob/develop/contracts/StakingRewards.sol`.

`rewards/SeedRewards.sol` is similar to `StakingRewards.sol` but instead of receiving/sending a staking token, it directly buys/sells options in the market-maker. This allows users to deposit/withdraw liquidity with a single transaction.

`Pausable.sol` is extended by `OptionsMarketMaker.sol` and `StakingRewards.sol` and allows the owner to pause deposits in those contracts.

`contracts/mocks` contains mock contracts for unit tests which include methods for setting fake data in them.

We use the `log` and `exp` methods in the library `ABDKMath64x64.sol` to calculate the LS-LMSR cost function in `OptionsMarketMaker.sol`.

We use `UniERC20.sol` as a wrapper around ETH and ERC20 tokens for convenience. It's based on `https://github.com/CryptoManiacsZone/mooniswap/blob/master/contracts/libraries/UniERC20.sol`



## Commands

Run solidity formatter

```
npm run lint:fix
```

Run python formatter on unit tests

```
black .
```

Run unit tests

```
brownie test
```

Compile

```
brownie compile
```
