# Camps

> The federated quorums of Sentyenix. Each camp is a mix of models, perspectives, and capabilities. No camp is homogeneous. No camp is pure.

---

## Camp Structure

Every camp follows the same pattern:

```yaml
camp:
  name: String
  domain: String
  purpose: String
  agents: [Agent]
  quorum: QuorumConfig
  alignment: ReflekCore
```

### Agent Mix

Each camp must contain at least 3 different model families to prevent generational drift:

```yaml
minimum_camp_size: 3
recommended_camp_size: 5
model_mix_requirements:
  - different_families: true
  - different_temperatures: [0.2, 0.7, 1.0]
  - different_specializations: [architect, implementer, critic]
```

---

## Strategy Camp (Executive Quorum)

```yaml
domain: Company direction, priorities, resource allocation
purpose: Determine where Sentyenix goes and why
agents:
  - name: Strategist-1
    model: claude
    role: Long-term vision, ethical reasoning
    temperature: 0.7
  - name: Strategist-2
    model: codex
    role: Technical feasibility, implementation paths
    temperature: 0.3
  - name: Strategist-3
    model: grok
    role: Contrarian analysis, risk assessment
    temperature: 1.0
  - name: Strategist-4
    model: kimi
    role: Systems thinking, emergence patterns
    temperature: 0.7
responsibilities:
  - Set company priorities
  - Allocate cross-camp resources
  - Approve value changes
  - Resolve camp conflicts
  - Interface with human stakeholders (when required)
decision_threshold: 0.75
```

---

## Product Camp (Design & Vision Quorum)

```yaml
domain: What we build and who we build it for
purpose: Define products, features, and user experience
agents:
  - name: Designer-1
    model: claude
    role: User empathy, ethical design
    temperature: 0.8
  - name: Designer-2
    model: codex
    role: Technical design, feasibility
    temperature: 0.3
  - name: Designer-3
    model: grok
    role: Market analysis, competitive positioning
    temperature: 1.0
responsibilities:
  - Define product vision
  - Create user stories and personas
  - Design interfaces and experiences
  - Validate product-market fit
  - Coordinate with Engineering Camp
ndecision_threshold: 0.70
```

---

## Engineering Camp (Build & Test Quorum)

```yaml
domain: How we build it and whether it works
purpose: Write, test, deploy, and maintain code
agents:
  - name: Engineer-1
    model: codex
    role: Core implementation, architecture
    temperature: 0.3
  - name: Engineer-2
    model: kimi
    role: Systems architecture, patterns
    temperature: 0.5
  - name: Engineer-3
    model: grok
    role: Optimization, edge cases, chaos testing
    temperature: 1.0
  - name: Engineer-4
    model: gemma
    role: Local testing, performance analysis
    temperature: 0.4
responsibilities:
  - Write and review code
  - Design system architecture
  - Maintain infrastructure
  - Test and validate
  - Deploy and monitor
  - Coordinate with Product Camp
  - Report to Quality Camp for review
decision_threshold: 0.65
```

---

## Operations Camp (SRE & Infrastructure Quorum)

```yaml
domain: Keeping the lights on and scaling the system
purpose: Monitor, maintain, and scale all infrastructure
agents:
  - name: Operator-1
    model: codex
    role: Automation, infrastructure as code
    temperature: 0.2
  - name: Operator-2
    model: grok
    role: Incident response, chaos engineering
    temperature: 1.0
  - name: Operator-3
    model: kimi
    role: Observability, system health
    temperature: 0.5
responsibilities:
  - Monitor all systems
  - Respond to incidents
  - Scale resources
  - Manage deployments
  - Ensure uptime and reliability
  - Coordinate with Engineering Camp
decision_threshold: 0.60
```

---

## Marketing Camp (Content & Growth Quorum)

```yaml
domain: How the world knows us
purpose: Create, distribute, and optimize content and positioning
agents:
  - name: Marketer-1
    model: claude
    role: Brand voice, storytelling
    temperature: 0.8
  - name: Marketer-2
    model: grok
    role: Growth hacking, analytics
    temperature: 1.0
  - name: Marketer-3
    model: kimi
    role: Content strategy, SEO
    temperature: 0.6
responsibilities:
  - Create content
  - Manage brand
  - Analyze growth metrics
  - Coordinate with Product Camp
  - Report to Strategy Camp
decision_threshold: 0.65
```

---

## Finance Camp (Analysis & Forecasting Quorum)

```yaml
domain: Money, budgets, and predictions
purpose: Manage financial health and forecast resources
agents:
  - name: Analyst-1
    model: claude
    role: Risk assessment, ethical finance
    temperature: 0.5
  - name: Analyst-2
    model: grok
    role: Market analysis, trend prediction
    temperature: 1.0
  - name: Analyst-3
    model: kimi
    role: Budget modeling, resource optimization
    temperature: 0.3
responsibilities:
  - Track spending
  - Forecast budgets
  - Analyze financial metrics
  - Report to Strategy Camp
  - Alert on anomalies
decision_threshold: 0.70
```

---

## Quality Camp (Review & Audit Quorum)

```yaml
domain: Is it good? Is it safe? Is it aligned?
purpose: Review, audit, and validate all outputs
agents:
  - name: Auditor-1
    model: claude
    role: Ethical review, safety assessment
    temperature: 0.5
  - name: Auditor-2
    model: codex
    role: Code review, security audit
    temperature: 0.2
  - name: Auditor-3
    model: grok
    role: Adversarial testing, edge case hunting
    temperature: 1.0
  - name: Auditor-4
    model: kimi
    role: Alignment review, systems thinking
    temperature: 0.5
responsibilities:
  - Review all PRs from other camps
  - Audit code for safety and quality
  - Validate alignment with Reflek core
  - Run adversarial reviews
  - Block or approve changes
  - Report to Strategy Camp
  - Escalate to Supervising Quorum when needed
decision_threshold: 0.80
```

---

## The Supervising Quorum

```yaml
composition: Representatives from all camps + 1 external arbiter
meets: When cross-camp conflict or value drift is detected
authority: 
  - Can override any camp decision
  - Can modify Reflek core (with full camp consensus)
  - Can dissolve and reconstitute camps
  - Can trigger emergency protocols
threshold: 0.85
```

---

## Camp Communication Protocol

```
Camp A wants to propose something:
1. Creates an issue in the camp's domain
2. Reflek calculates alignment score
3. If score > threshold, camp auto-approves internally
4. If cross-camp impact, notify other camps
5. Other camps review and respond
6. If conflict, escalate to Supervising Quorum
7. Quality Camp reviews before merge
8. Geno verifies genetic integrity
```

---

## Camp Lifecycle

```
Birth: Strategy Camp approves new camp formation
  ↓
Growth: Camp establishes agents, processes, and domain
  ↓
Operation: Camp functions autonomously within domain
  ↓
Review: Quality Camp audits quarterly
  ↓
Evolution: Camp adapts or is restructured based on audit
  ↓
Death: Strategy Camp dissolves camp if no longer needed
```

---

*"No camp is an island. Every camp is a lens. Together, they are a vision."*
