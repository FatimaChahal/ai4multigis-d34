// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title GISIndexRegistry
 * @dev Manages the lifecycle of MASTER_GRID analytical index versions
 * for the AI4MultiGIS project.
 */
contract GISIndexRegistry {

    address public administrator;
    mapping(address => bool) public dataProviders;
    mapping(address => bool) public analysts;

    struct IndexVersion {
        uint256 versionId;
        string  dataHash;
        string  layerName;
        string  actor;
        string  metadataRef;
        uint256 timestamp;
        bool    validated;
        bool    exists;
    }

    mapping(uint256 => IndexVersion) public indexVersions;
    uint256 public latestVersionId;

    event IndexVersionRegistered(uint256 indexed versionId, string dataHash, string layerName, string actor, uint256 timestamp);
    event IndexVersionValidated(uint256 indexed versionId, string dataHash, uint256 timestamp);
    event IndexVersionRejected(uint256 indexed versionId, string reason, uint256 timestamp);
    event DataProviderAdded(address indexed provider);
    event AnalystAdded(address indexed analyst);

    modifier onlyAdministrator() {
        require(msg.sender == administrator, "AccessControl: caller is not administrator");
        _;
    }

    modifier onlyDataProvider() {
        require(dataProviders[msg.sender], "AccessControl: caller is not a data provider");
        _;
    }

    constructor() {
        administrator = msg.sender;
        dataProviders[msg.sender] = true;
        analysts[msg.sender] = true;
    }

    function addDataProvider(address _provider) external onlyAdministrator {
        dataProviders[_provider] = true;
        emit DataProviderAdded(_provider);
    }

    function addAnalyst(address _analyst) external onlyAdministrator {
        analysts[_analyst] = true;
        emit AnalystAdded(_analyst);
    }

    function registerIndexVersion(
        string memory _dataHash,
        string memory _layerName,
        string memory _actor,
        string memory _metadataRef
    ) external onlyDataProvider returns (uint256) {
        require(bytes(_dataHash).length > 0, "Validation: dataHash cannot be empty");
        require(bytes(_layerName).length > 0, "Validation: layerName cannot be empty");
        require(bytes(_actor).length > 0, "Validation: actor cannot be empty");

        latestVersionId += 1;
        uint256 newVersionId = latestVersionId;

        indexVersions[newVersionId] = IndexVersion({
            versionId:   newVersionId,
            dataHash:    _dataHash,
            layerName:   _layerName,
            actor:       _actor,
            metadataRef: _metadataRef,
            timestamp:   block.timestamp,
            validated:   false,
            exists:      true
        });

        emit IndexVersionRegistered(newVersionId, _dataHash, _layerName, _actor, block.timestamp);
        return newVersionId;
    }

    function validateIndexVersion(uint256 _versionId) external onlyAdministrator {
        require(indexVersions[_versionId].exists, "Registry: version does not exist");
        require(!indexVersions[_versionId].validated, "Registry: version already validated");
        indexVersions[_versionId].validated = true;
        emit IndexVersionValidated(_versionId, indexVersions[_versionId].dataHash, block.timestamp);
    }

    function rejectIndexVersion(uint256 _versionId, string memory _reason) external onlyAdministrator {
        require(indexVersions[_versionId].exists, "Registry: version does not exist");
        emit IndexVersionRejected(_versionId, _reason, block.timestamp);
    }

    function verifyIndexHash(uint256 _versionId, string memory _dataHash) external view returns (bool) {
        require(indexVersions[_versionId].exists, "Registry: version does not exist");
        return (
            keccak256(bytes(indexVersions[_versionId].dataHash)) ==
            keccak256(bytes(_dataHash)) &&
            indexVersions[_versionId].validated
        );
    }

    function getIndexVersion(uint256 _versionId) external view returns (
        string memory dataHash,
        string memory layerName,
        string memory actor,
        uint256 timestamp,
        bool validated
    ) {
        require(indexVersions[_versionId].exists, "Registry: version does not exist");
        IndexVersion memory v = indexVersions[_versionId];
        return (v.dataHash, v.layerName, v.actor, v.timestamp, v.validated);
    }
}
