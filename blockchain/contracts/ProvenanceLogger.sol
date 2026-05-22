// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title ProvenanceLogger
 * @dev Immutable on-chain provenance log for the AI4MultiGIS pipeline.
 *      Each entry records a pipeline operation with its input/output hashes,
 *      actor, and timestamp — creating a tamper-proof audit trail.
 */
contract ProvenanceLogger {

    address public administrator;

    struct ProvenanceEntry {
        uint256 entryId;
        string  operation;      // e.g. "INGEST", "TRANSFORM", "VALIDATE"
        string  inputHash;      // SHA-256 of input data
        string  outputHash;     // SHA-256 of output data
        string  actor;          // e.g. "fatima@UPPA"
        string  metadataRef;    // e.g. "PostGIS:governance.provenance_log:id=42"
        uint256 timestamp;
        bool    exists;
    }

    mapping(uint256 => ProvenanceEntry) public entries;
    uint256 public entryCount;

    event ProvenanceRecorded(
        uint256 indexed entryId,
        string operation,
        string outputHash,
        string actor,
        uint256 timestamp
    );

    modifier onlyAdministrator() {
        require(msg.sender == administrator,
            "ProvenanceLogger: caller is not administrator");
        _;
    }

    constructor() {
        administrator = msg.sender;
    }

    function logOperation(
        string memory operation,
        string memory inputHash,
        string memory outputHash,
        string memory actor,
        string memory metadataRef
    ) external returns (uint256) {
        require(bytes(operation).length > 0,  "ProvenanceLogger: operation required");
        require(bytes(outputHash).length > 0, "ProvenanceLogger: outputHash required");
        require(bytes(actor).length > 0,      "ProvenanceLogger: actor required");

        entryCount += 1;
        uint256 newId = entryCount;

        entries[newId] = ProvenanceEntry({
            entryId:     newId,
            operation:   operation,
            inputHash:   inputHash,
            outputHash:  outputHash,
            actor:       actor,
            metadataRef: metadataRef,
            timestamp:   block.timestamp,
            exists:      true
        });

        emit ProvenanceRecorded(newId, operation, outputHash, actor, block.timestamp);
        return newId;
    }

    function getEntry(uint256 entryId) external view returns (
        string memory operation,
        string memory inputHash,
        string memory outputHash,
        string memory actor,
        uint256 timestamp
    ) {
        require(entries[entryId].exists, "ProvenanceLogger: entry does not exist");
        ProvenanceEntry memory e = entries[entryId];
        return (e.operation, e.inputHash, e.outputHash, e.actor, e.timestamp);
    }

    function verifyOutputHash(uint256 entryId, string memory hash) external view returns (bool) {
        require(entries[entryId].exists, "ProvenanceLogger: entry does not exist");
        return keccak256(bytes(entries[entryId].outputHash)) == keccak256(bytes(hash));
    }
}
