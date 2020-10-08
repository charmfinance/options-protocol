// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;

import "@openzeppelin/contracts/access/Ownable.sol";

contract Pausable is Ownable {
    bool public isPaused;

    function pause() external onlyOwner {
        isPaused = true;
    }

    function unpause() external onlyOwner {
        isPaused = false;
    }

    modifier notPaused {
        require(!isPaused, "This method has been paused");
        _;
    }
}
