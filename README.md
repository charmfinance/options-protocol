# Charm Finance

Charm Finance is an AMM (automated market-maker) for options on Ethereum

It uses an LS-LMSR (Othman et al., 2013) to price the options. In short, it acts like token bonding curve, minting/burning option tokens as users buy/sell them.

At expiration, the settlement price is fetched from a Chainlink or Uniswap V2 oracle. Users can them redeem their options for the settlement value


## Owner privileges

Please note the owner of the options market is highly privileged and has the permissions below. These are only intended to be used in an emergency situation. These permissions will be removed in future versions.

- Pause the contract indefinitely. This includes preventing users from buying, selling, and redeeming their options.

- Change the contract’s oracle. If an invalid or malicious oracle is provided, users can potentially lose funds.

- Change the contract’s expiry date.

- Dispute the settlement price


## Repo

The main contract is `OptionMarket.sol`. This contains methods `buy` and `sell` that let users mint/burn options. Calling `settle` after expiration fetches the settlement price from the oracle and users can call `redeem` to redeem their options for the settlement value.

`OptionToken.sol` is an ERC20 token representing ownership of an option.

`UniswapOracle.sol` is used by `OptionMarket.sol` to fetch the TWAP price at expiration from a Uniswap market.

`contracts/mocks` contains mock contracts for unit tests which include methods for setting fake data in them.

We use the `log` and `exp` methods in the library `ABDKMath64x64.sol` to calculate the LS-LMSR cost function in `OptionMarket.sol`.

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
