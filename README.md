# Charm Options

This repository contains an automated market-maker for options

It implements an AMM that allows an asset to be split up into tokenized payoffs such that
different combinations of payoffs sum up to different call/put option payoffs.
An LMSR (Hanson's market-maker) is used to provide liquidity for the tokenized
payoffs.


## Deployer privileges

Please note the deployer is highly privileged and has the permissions below. These are only intended to be used in an emergency situation and will be removed in future versions.

- Modify parameters of market

- Pause the contract indefinitely. This includes preventing users from buying, selling, and redeeming their options.

- Override the expiry price


## Repository

The main contract that users will interact with is `OptionMarket.sol`, which implements the `buy`, `sell`, `deposit` and `withdraw` methods.

`OptionMath.sol` implements calculation logic for the LMSR cost function and for option payoffs.

`OptionToken.sol` is an ERC-20 token representing a long or short option position.

`ChainlinkOracle.sol` and `UniswapOracle.sol` are price oracles used to retrieve the price of the underlying asset at expiration.

`OptionFactory.sol` is a factory contract. `createMarket` is the intended way to deploy a new market.

`OptionSymbol.sol` is used to build the symbols and names of the option and LP tokens. It's adapted from `https://github.com/opynfinance/GammaProtocol/blob/master/contracts/Otoken.sol`.


## Commands

Run solidity linter

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
