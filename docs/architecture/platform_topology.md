# Platform Topology

PlatformManifest describes platform topology and entity relationships. It is
not a runtime registry and not a protocol-schema repository.

## Topology Roles

| Component | Role |
| --- | --- |
| PlatformManifest | Topology, visibility, entity ontology, projection policy. |
| CxRP | Execution/routing contracts and vocabulary. |
| RxP | Runtime invocation and return contracts. |
| OperationsCenter | Governance, validation, orchestration, enforcement. |
| SwitchBoard | Lane and runtime recommendation. |
| ExecutorRuntime | Runtime backend/driver used by OperationsCenter. |
| WorkStation | Deployment and hosting layer for runtime environments. |
| VideoFoundry | Managed project, artifact producer, and reference testbed. |
| SourceFoundry | Source/corpus producer. |
| Intelligencer | Signal interpretation and proposals. |
| Custodian | Privacy and hygiene detectors. |

## Repo Topology Diagram

```mermaid
graph TD
    PM[PlatformManifest\nTopology + Visibility + Entity Ontology]
    CX[CxRP\nExecution/Routing Contracts]
    RX[RxP\nRuntime Invocation Contracts]
    OC[OperationsCenter\nGovernance + Orchestration]
    SB[SwitchBoard\nLane/Runtime Recommendation]
    ER[ExecutorRuntime\nOC Backend Runtime Driver]
    WS[WorkStation\nDeployment + Hosting Layer]
    VF[VideoFoundry\nManaged Project + Artifact Producer]
    SF[SourceFoundry\nSource/Corpus Producer]
    INT[Intelligencer\nSignal Interpretation + Proposals]
    CUST[Custodian\nPrivacy + Hygiene Detectors]

    PM -->|declares entities + visibility| OC
    PM -->|visibility policy| CUST
    CUST -->|validates public/private safety| PM

    CX -->|contract schemas| OC
    CX -->|lane/routing vocabulary| SB
    RX -->|runtime invocation contracts| ER

    INT -->|TaskProposal / SpecProposal| OC
    SB -->|LaneDecision| OC
    OC -->|invokes via| ER
    ER -->|runs targets hosted by| WS

    OC -->|manages as external project| VF
    VF -->|artifact manifests / reports| OC
    SF -->|SourceCorpus / SignalCorpus| VF
    SF -->|SignalCorpus| INT
```

## Execution Timeline

PlatformManifest participates as topology and visibility metadata. It does
not execute work and does not own CxRP or RxP schemas.

```mermaid
sequenceDiagram
    participant INT as Intelligencer
    participant OC as OperationsCenter
    participant PM as PlatformManifest
    participant SB as SwitchBoard
    participant ER as ExecutorRuntime
    participant WS as WorkStation
    participant VF as VideoFoundry
    participant CUST as Custodian

    INT->>OC: TaskProposal / SpecProposal
    OC->>PM: Resolve managed project + visibility/topology metadata
    OC->>OC: Validate proposal against CxRP
    OC->>SB: Request LaneDecision
    SB-->>OC: LaneDecision
    OC->>OC: Bind RuntimeBinding + CapabilitySet
    OC->>ER: Runtime invocation request using RxP semantics
    ER->>WS: Invoke configured runtime target
    WS->>VF: Run audit/workflow command
    VF-->>WS: Artifacts + artifact_manifest.json
    WS-->>ER: Runtime result
    ER-->>OC: Normalized runtime result
    OC->>PM: Index/update manifest references
    PM->>CUST: Validate public/private projection safety
    CUST-->>PM: Pass/fail privacy and hygiene checks
```

## Consumption Rules

OperationsCenter reads PlatformManifest to resolve managed projects,
repositories, topology, and visibility metadata. It can validate proposals
against CxRP and invoke ExecutorRuntime using RxP semantics, but those
contract schemas stay in their owning protocol repositories.

SwitchBoard can consume repo context as input for lane/runtime
recommendation, but it does not own manifest loading, merging, runtime
dispatch, or project wiring.

WorkStation may expose deployment and hosting information such as local
runtime availability or configured target location. It must not own
PlatformManifest, ProjectManifest, or orchestration policy.

VideoFoundry fits as an external managed project and reference testbed for
OperationsCenter contracts. It can demonstrate artifact production, audit
workflows, and manifest consumption without becoming part of the
OperationsCenter codebase.
