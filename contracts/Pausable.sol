// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;

import "@openzeppelin/contracts/access/Ownable.sol";

contract Pausable is Ownable {
    bool public paused;

    function pause() external onlyOwner {
        paused = true;
    }

    function unpause() external onlyOwner {
        paused = false;
    }

    modifier notPaused {
        require(!paused, "This method has been paused");
        _;
    }
}
