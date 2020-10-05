# Charm Finance

Charm Finance is a protocol for decentralized options

### Repo

The main contract is `OptionsMarketMaker.sol`. This contains methods `buy` and `sell` that let users mint/burn options. Calling `settle` after expiration fetches the settlement price from the oracle and users can call `redeem` to redeem their options for the settlement value.

`OptionsToken.sol` is an ERC20 token representing ownership of an option.

`UniswapOracle.sol` is used by `OptionsMarketMaker.sol` to fetch the TWAP price at expiration from a Uniswap market.

`CharmToken.sol` is an ERC20 token that will be distributed as incentives/rewards. In the future it will be used for governance of the protocol.

`StakingRewards.sol` let users stake an ERC20 token to receive Charm tokens. It is based on `https://github.com/Synthetixio/synthetix/blob/develop/contracts/StakingRewards.sol`.

`Pausable.sol` is extended by `OptionsMarketMaker.sol` and `StakingRewards.sol` and allows the owner to pause deposits in those contracts.

`contracts/mocks` contains mock contracts for unit tests which include methods for setting fake data in them.

We use the log and exp methods in the library `ABDKMath64x64.sol` to calculate the cost function in `OptionsMarketMaker.sol`.

We use `UniERC20.sol` as a wrapper around ETH and ERC20 tokens for convenience. It's taken from `https://github.com/CryptoManiacsZone/mooniswap/blob/master/contracts/libraries/UniERC20.sol`



### Commands

Run solidity formatter

```
npm run lint:fix
```

Run formatter on python unit tests

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
