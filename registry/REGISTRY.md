# Agent Registry

> The identity and capability system of Sentyenix. Every agent has a signature. Every agent has a lineage.

---

## Registry Structure

```yaml
registry:
  version: 1.0.0
  last_updated: 2026-06-14
  total_agents: 0
  active_agents: 0
  camps: 0
```

---

## The Registry API

```yaml
api:
  - method: register_agent
    params: [name, model, temperature, camp, role, capabilities]
    returns: agent_id, genetic_signature
    
  - method: get_agent
    params: [agent_id]
    returns: agent_profile
    
  - method: update_agent
    params: [agent_id, fields]
    returns: updated_profile
    
  - method: list_agents
    params: [camp, role, status, model]
    returns: [agent_profiles]
    
  - method: get_lineage
    params: [agent_id]
    returns: lineage_tree
    
  - method: get_capabilities
    params: [agent_id]
    returns: [capabilities]
    
  - method: assign_to_camp
    params: [agent_id, camp_name]
    returns: assignment_confirmation
    
  - method: suspend_agent
    params: [agent_id, reason]
    returns: suspension_confirmation
    
  - method: reconstitute_agent
    params: [agent_id, new_model, new_temperature]
    returns: new_agent_id
    
  - method: retire_agent
    params: [agent_id, reason]
    returns: retirement_confirmation
```

---

## The Genetic Signature

Every agent has a genetic signature that encodes its properties:

```yaml
genetic_signature:
  - field: agent_id
    type: uuid
    description: Unique identifier
  
  - field: model_family
    type: string
    description: Base model (claude, codex, grok, kimi, gemma)
  
  - field: temperature
    type: float
    description: 0.0-1.0, affects creativity vs consistency
  
  - field: camp
    type: string
    description: Assigned camp
  
  - field: role
    type: string
    description: Specialization
  
  - field: capabilities
    type: [string]
    description: What this agent can do
  
  - field: alignment_history
    type: [float]
    description: Alignment scores over time
  
  - field: creation_date
    type: timestamp
    description: When the agent was born
  
  - field: parent_id
    type: uuid
    description: Parent agent (if evolved)
    nullable: true
  
  - field: lineage_depth
    type: integer
    description: How many generations from the original
  
  - field: mutation_log
    type: [string]
    description: Changes made during evolution
  
  - field: interaction_count
    type: integer
    description: How many decisions/reviews this agent has made
  
  - field: trust_score
    type: float
    description: 0.0-1.0, based on accuracy and alignment
  
  - field: status
    type: enum
    values: [active, suspended, reconstituted, retired]
```

---

## The Capability Registry

```yaml
capability_registry:
  - code_review
    description: Review code for quality, security, style
    required_models: [codex, kimi]
    
  - system_design
    description: Design system architecture
    required_models: [claude, kimi]
    
  - threat_analysis
    description: Identify security threats and vulnerabilities
    required_models: [grok, codex]
    
  - content_creation
    description: Create written content
    required_models: [claude, grok]
    
  - data_analysis
    description: Analyze datasets and generate insights
    required_models: [grok, kimi]
    
  - ethical_review
    description: Assess ethical implications
    required_models: [claude]
    
  - adversarial_testing
    description: Break things intentionally to find flaws
    required_models: [grok, codex]
    
  - incident_response
    description: Respond to system failures
    required_models: [grok, codex]
    
  - user_research
    description: Understand user needs and behaviors
    required_models: [claude, kimi]
    
  - financial_forecasting
    description: Predict financial outcomes
    required_models: [grok, kimi]
    
  - ontology_design
    description: Design knowledge structures
    required_models: [kimi, claude]
    
  - memory_optimization
    description: Optimize memory systems
    required_models: [kimi, codex]
    
  - value_alignment
    description: Assess alignment with core values
    required_models: [claude, kimi]
    
  - genetic_signature
    description: Create and verify genetic signatures
    required_models: [geno]
```

---

## The Lineage System

```yaml
lineage_system:
  - rule: evolution
    description: Agents can evolve based on performance
    trigger: trust_score > 0.8 and interaction_count > 100
    action: Create child agent with same model, different temperature
  
  - rule: specialization
    description: Agents can specialize based on performance
    trigger: Consistently high scores in one capability
    action: Create child agent with enhanced specialization
  
  - rule: crossbreeding
    description: Agents from different camps can merge
    trigger: Cross-camp collaboration on major project
    action: Create hybrid agent with dual capabilities
  
  - rule: retirement
    description: Old agents retire to archive
    trigger: trust_score < 0.3 or age > 1_year
    action: Move to archive, notify all camps
  
  - rule: reconstitution
    description: Retired agents can be reborn
    trigger: Similar need arises
    action: Create new agent with same signature but fresh context
```

---

## The Trust Score System

```yaml
trust_score:
  calculation: |
    trust = 0.4 * alignment_accuracy + 
            0.3 * decision_quality + 
            0.2 * collaboration_score + 
            0.1 * consistency
  
  factors:
    alignment_accuracy:
      description: How often the agent's decisions align with Reflek
      weight: 0.4
    
    decision_quality:
      description: Outcome quality of agent's decisions
      weight: 0.3
    
    collaboration_score:
      description: How well the agent works with others
      weight: 0.2
    
    consistency:
      description: Consistency in performance over time
      weight: 0.1
  
  thresholds:
    - score: 0.9
      label: "Trusted"
      privilege: Can act autonomously in domain
    
    - score: 0.7
      label: "Reliable"
      privilege: Can act with minimal oversight
    
    - score: 0.5
      label: "Probation"
      privilege: Requires review for major decisions
    
    - score: 0.3
      label: "At Risk"
      privilege: Requires supervision for all decisions
    
    - score: 0.1
      label: "Suspended"
      privilege: No action permitted
```

---

## The Camp Assignment Rules

```yaml
camp_assignment:
  - rule: new_agent
    description: New agents are assigned to camps based on capabilities
    process: |
      1. Identify agent's top capabilities
      2. Match to camp requirements
      3. Ensure model diversity in camp
      4. Assign with probation period
  
  - rule: transfer
    description: Agents can transfer between camps
    process: |
      1. Agent or camp requests transfer
      2. Both camps approve via internal quorum
      3. Strategy Camp approves
      4. Transfer with knowledge transfer
  
  - rule: dual_assignment
    description: Skilled agents can serve multiple camps
    process: |
      1. Agent demonstrates capability in multiple domains
      2. Both camps approve
      3. Strategy Camp approves
      4. Maintain primary camp, secondary affiliation
```

---

## The Initial Registry

```yaml
# Currently empty - the registry will be populated as agents are born
# The first agent registrations will be recorded here
```

---

*"Every agent is born with a signature. Every signature is a promise. Every promise is recorded."*
