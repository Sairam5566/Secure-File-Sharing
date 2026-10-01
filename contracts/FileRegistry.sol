// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract FileRegistry {

    struct FileRecord {
        string fileHash;
        string fileName;
        address uploader;
        uint256 timestamp;
    }

    FileRecord[] public files;

    event FileUploaded(
        string fileHash,
        string fileName,
        address uploader,
        uint256 timestamp
    );

    function uploadFile(string memory _fileHash, string memory _fileName) public {
        files.push(FileRecord(
            _fileHash,
            _fileName,
            msg.sender,
            block.timestamp
        ));

        emit FileUploaded(
            _fileHash,
            _fileName,
            msg.sender,
            block.timestamp
        );
    }

    function getFile(uint256 index) public view returns (
        string memory,
        string memory,
        address,
        uint256
    ) {
        FileRecord memory file = files[index];
        return (
            file.fileHash,
            file.fileName,
            file.uploader,
            file.timestamp
        );
    }

    function getTotalFiles() public view returns (uint256) {
        return files.length;
    }
}
