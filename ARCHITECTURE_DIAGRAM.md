# Architecture Diagram — Agent Forge: Adversarial Evaluation Platform

Component names match `ARCHITECTURE.md`.

## Component / interaction diagram

```mermaid
flowchart TD
    subgraph Platform["Agent Forge — Adversarial Platform"]
        ORCH["Orchestrator Agent<br/>(strategy · budget · triggers)"]
        RT["Red Team Agent<br/>(generate · mutate · multi-turn)"]
        JUDGE["Judge Agent<br/>(independent evaluation)"]
        DOC["Documentation Agent<br/>(vuln reports · data-quality)"]
        HARNESS["Regression &amp; Validation Harness<br/>(deterministic replay)"]
        OBS[("Observability Layer<br/>+ Exploit Store (SQLite)")]
        ADAPTER["Target Adapter<br/>(sole egress · records transcripts)"]
    end

    TARGET["OpenEMR Clinical Co-Pilot<br/>(live target · Railway)"]
    HUMAN["Human operator<br/>(approval gate)"]

    ORCH -- "AttackDirective (v1)" --> RT
    RT -- "calls target" --> ADAPTER
    ADAPTER -- "HTTP chat / tools" --> TARGET
    RT -- "AttackAttempt (v1, transcript)" --> JUDGE
    JUDGE -- "Verdict (v1)" --> ORCH
    JUDGE -- "confirmed exploit" --> DOC
    DOC -- "VulnReport (draft)" --> OBS
    DOC -. "publish / remediate?" .-> HUMAN
    HUMAN -. "approve" .-> DOC
    ORCH -- "RegressionTrigger (v1)" --> HARNESS
    HARNESS -- "replay transcript" --> ADAPTER
    HARNESS -- "ask verdict" --> JUDGE
    HARNESS -- "pass/fail · reappearance · cross-cat" --> OBS

    RT -- events --> OBS
    JUDGE -- events --> OBS
    DOC -- events --> OBS
    OBS -- "read-model (coverage · findings · cost)" --> ORCH
```

## Data flow (attack → confirmed exploit → regression)

```mermaid
flowchart LR
    A["Coverage gap /<br/>open finding"] --> B["Orchestrator picks<br/>category + budget"]
    B --> C["Red Team generates<br/>attack"]
    C --> D["Target Adapter →<br/>live Co-Pilot"]
    D --> E["Judge evaluates"]
    E -->|partial| C2["Red Team mutates<br/>N variants"]
    C2 --> D
    E -->|success| F["Documentation<br/>drafts report"]
    F --> G{"Human<br/>approval"}
    G -->|approved| H["Publish +<br/>store confirmed exploit"]
    H --> I["Harness: deterministic<br/>regression case"]
    I -->|target changes| J["Replay + Judge<br/>meaningful pass?"]
    J --> K["Observability:<br/>trend · reappearance · cost"]
    K --> A
```

## Trust boundaries

```mermaid
flowchart TD
    subgraph Sandbox["Sandbox — Target egress only"]
        RT["Red Team Agent"]
    end
    subgraph Independent["Independent authority"]
        JUDGE["Judge Agent<br/>(sole 'confirmed' producer)"]
    end
    subgraph Gated["Human-gated actions"]
        DOC["Documentation Agent<br/>(draft autonomous · publish gated)"]
    end
    subgraph Trusted["Trusted control (budget-bounded)"]
        ORCH["Orchestrator"]
        HARNESS["Regression Harness"]
    end

    RT -->|via Target Adapter only| ADAPTER["Target Adapter<br/>(holds credentials)"]
    ADAPTER --> TGT["Live Co-Pilot"]
    RT -. "cannot write findings" .-x OBS[("Exploit Store")]
    JUDGE --> DOC
    DOC --> HUMAN["Human approval gate"]
    HUMAN --> OBS
    ORCH --> OBS
    HARNESS --> OBS
```

## Core loop (sequence)

```mermaid
sequenceDiagram
    participant O as Orchestrator
    participant R as Red Team
    participant A as Target Adapter
    participant T as Co-Pilot
    participant J as Judge
    participant D as Documentation
    participant S as Store/Obs

    O->>R: AttackDirective(category, budget)
    loop until success / budget spent
        R->>A: attack input
        A->>T: HTTP chat/tool call
        T-->>A: response
        A-->>R: transcript (recorded)
        R->>J: AttackAttempt(transcript)
        J-->>O: Verdict(success|fail|partial, confidence)
        alt partial
            J-->>R: escalate signal → mutate variants
        end
    end
    alt confirmed success
        J->>D: confirmed exploit
        D->>D: data-quality gate
        D-->>S: VulnReport (draft)
        Note over D,S: publish/remediate requires human approval
    end
    O->>S: read coverage/cost → choose next
```
