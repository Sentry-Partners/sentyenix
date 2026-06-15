# Quorum Protocol

> The decision-making physics of Sentyenix. How camps agree, disagree, and converge.

---

## Quorum Types

### 1. Internal Quorum

Within a single camp, for decisions within that camp's domain.

```yaml
type: internal
participants: All agents in the camp
threshold: Varies by camp (see CAMPS.md)
mechanism: 
  - Each agent submits a position
  - Reflek calculates alignment for each position
  - Weighted vote based on agent confidence and alignment score
  - If consensus > threshold: approve
  - If consensus < threshold: debate or escalate
```

### 2. Cross-Camp Quorum

Between camps, for decisions affecting multiple domains.

```yaml
type: cross-camp
participants: Representatives from each affected camp
threshold: 0.75
mechanism:
  - Initiating camp creates cross-camp issue
  - All affected camps review within 24 hours
  - Each camp submits position via internal quorum
  - Reflek calculates cross-camp alignment
  - If consensus > threshold: approve
  - If conflict: Supervising Quorum mediates
```

### 3. Supervising Quorum

For conflicts, value drift, or emergency situations.

```yaml
type: supervising
participants: 1 representative from each camp + 1 external arbiter
threshold: 0.85
mechanism:
  - Any camp or agent can call for Supervising Quorum
  - 48-hour review period for all evidence
  - External arbiter provides neutral perspective
  - Vote by representatives
  - If consensus > threshold: decision is binding
  - If no consensus: human stakeholder breaks tie (last resort)
```

---

## Decision Flow

```
Decision Needed
  ↓
Internal Quorum (single camp domain)
  ↓
  ├─ Approved → Execute → Notify affected camps
  └─ Rejected → Revise or escalate
  ↓
Cross-Camp Quorum (multi-camp domain)
  ↓
  ├─ Approved → Execute → Quality Camp review → Merge
  └─ Rejected → Revise or escalate
  ↓
Supervising Quorum (conflict or emergency)
  ↓
  ├─ Approved → Execute → Full audit
  └─ Rejected → Revise or human review
```

---

## The Debate Protocol

When agents disagree, structured debate is required:

```yaml
phase_1_positioning: 30_minutes
  - Each agent states their position clearly
  - Reflek calculates alignment of each position
  - Positions are recorded in the graph

phase_2_challenging: 1_hour
  - Each agent challenges other positions
  - Must cite evidence, not opinion
  - Must identify alignment concerns
  - Reflek updates scores in real-time

phase_3_synthesis: 30_minutes
  - Agents propose synthesized solutions
  - Must incorporate strongest elements from all positions
  - Must address all alignment concerns
  - Reflek scores synthesis proposals

phase_4_resolution: 15_minutes
  - Vote on synthesis proposals
  - If consensus: approve
  - If no consensus: escalate to Supervising Quorum
```

---

## The Adversarial Review Protocol

Every proposal must undergo adversarial review before final approval:

```yaml
reviewer_assignment:
  - Must come from different camp than proposal
  - Must use different model family than proposer
  - Must have temperature > 0.7 (critical thinking)

review_dimensions:
  - Safety: Could this cause harm?
  - Alignment: Does this serve the core values?
  - Feasibility: Can this actually work?
  - Risk: What could go wrong?
  - Consequence: What are the second-order effects?

review_outcomes:
  - approve: Pass to next stage
  - approve_with_conditions: Pass with required modifications
  - reject: Return to origin camp with feedback
  - escalate: Requires Supervising Quorum
```

---

## The Emergency Protocol

For situations requiring immediate action:

```yaml
triggers:
  - Safety violation detected
  - Value drift exceeds 0.3 in 24 hours
  - Security breach
  - System failure
  - Human stakeholder requests emergency action

emergency_powers:
  - Any agent can declare emergency
  - Operations Camp has immediate response authority
  - Strategy Camp can halt all non-essential activity
  - Geno can quarantine any node or agent
  - Supervising Quorum convenes within 1 hour

emergency_review:
  - After emergency action, full review within 48 hours
  - All emergency actions must be justified
  - If unjustified: agent may be reconstituted or removed
  - If justified: process improvements are implemented
```

---

## The Appeal Protocol

Agents can appeal decisions:

```yaml
grounds_for_appeal:
  - New evidence not available during original decision
  - Reflek alignment calculation error
  - Procedural violation in quorum process
  - Change in context that invalidates original decision

appeal_process:
  - Submit appeal to Supervising Quorum within 48 hours
  - All new evidence must be documented
  - Original quorum must be given chance to respond
  - Supervising Quorum reviews and decides
  - Decision is binding
```

---

*"Disagreement is not failure. It is the friction that polishes the truth."*
