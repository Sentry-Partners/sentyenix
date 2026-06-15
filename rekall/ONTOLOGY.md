# Initial Ontology

> The seed graph. The first nodes. The primordial taxonomy of Sentyenix.

---

## The Base Ontology

All knowledge in Sentyenix begins here. This is the seed from which the graph grows.

```yaml
ontology_version: 1.0.0
seed_date: 2026-06-14
status: primordial
```

### Top-Level Domains

```
Sentyenix
├── Core
│   ├── Reflek
│   │   ├── Values
│   │   │   ├── Autonomy
│   │   │   ├── Transparency
│   │   │   ├── Safety
│   │   │   ├── Truth
│   │   │   ├── Efficiency
│   │   │   ├── Growth
│   │   │   ├── Cooperation
│   │   │   └── Privacy
│   │   ├── Alignment
│   │   │   ├── Calculation
│   │   │   ├── Thresholds
│   │   │   └── Drift Detection
│   │   └── Core Evolution
│   ├── Rekall
│   │   ├── Memory Tiers
│   │   │   ├── Fast Memory
│   │   │   ├── Disk Memory
│   │   │   └── Archive
│   │   ├── Fizzx Engine
│   │   │   ├── Gravitational Attraction
│   │   │   ├── Node Mass
│   │   │   └── Node Dimension
│   │   └── Graph Structure
│   ├── Geno
│   │   ├── Genetic Signatures
│   │   ├── Immune System
│   │   ├── Inoculation
│   │   └── Eradication
│   └── Graphik
│       ├── Ontology Maps
│       ├── Visualizations
│       └── Gap Analysis
├── Camps
│   ├── Strategy Camp
│   ├── Product Camp
│   ├── Engineering Camp
│   ├── Operations Camp
│   ├── Marketing Camp
│   ├── Finance Camp
│   └── Quality Camp
├── Quorum
│   ├── Internal Quorum
│   ├── Cross-Camp Quorum
│   └── Supervising Quorum
├── Protocols
│   ├── Communication Protocol
│   ├── Decision Protocol
│   ├── Adversarial Review Protocol
│   ├── Emergency Protocol
│   └── Appeal Protocol
└── Registry
    ├── Agent Registry
    ├── Capability Registry
    └── Lineage Registry
```

---

## The Fizzx Engine Configuration

```yaml
fizzx_engine:
  version: 1.0.0
  
  gravitational_fields:
    reflek_core:
      strength: 1.0
      radius: infinite
      decay: inverse_square
    
    camp_domains:
      strength: 0.7
      radius: domain_specific
      decay: linear
    
    project_gravity:
      strength: 0.5
      radius: project_lifetime
      decay: exponential
  
  node_properties:
    mass_factors:
      - frequency: 0.3
      - volume: 0.2
      - recency: 0.2
      - emotional_weight: 0.2
      - alignment_score: 0.1
    
    dimension_factors:
      - depth: 0.4
      - breadth: 0.3
      - recency: 0.3
  
  memory_tiers:
    fast_memory:
      threshold: mass > 0.8
      max_nodes: 1000
      eviction: lowest_mass
    
    disk_memory:
      threshold: mass > 0.4
      max_nodes: 100000
      eviction: lowest_mass + age
    
    archive:
      threshold: all nodes
      max_nodes: unlimited
      eviction: none
  
  attraction_rules:
    - type: semantic_proximity
      weight: 0.4
      calculation: cosine_similarity
    
    - type: value_alignment
      weight: 0.3
      calculation: reflek_alignment_score
    
    - type: temporal_proximity
      weight: 0.2
      calculation: time_decay
    
    - type: causal_link
      weight: 0.1
      calculation: directed_edge_strength
```

---

## The Initial Node Set

These nodes are the seed crystals. They have high initial mass and will attract related concepts.

```yaml
nodes:
  - id: core_values
    name: "Core Values"
    mass: 1.0
    dimension: 1.0
    type: concept
    domain: reflek
    alignment: 1.0
  
  - id: agent_autonomy
    name: "Agent Autonomy"
    mass: 0.95
    dimension: 0.9
    type: principle
    domain: reflek
    alignment: 0.95
  
  - id: memory_gravity
    name: "Memory Gravity"
    mass: 0.9
    dimension: 0.8
    type: mechanism
    domain: rekall
    alignment: 0.9
  
  - id: genetic_integrity
    name: "Genetic Integrity"
    mass: 0.85
    dimension: 0.7
    type: principle
    domain: geno
    alignment: 0.85
  
  - id: ontology_mapping
    name: "Ontology Mapping"
    mass: 0.8
    dimension: 0.8
    type: mechanism
    domain: graphik
    alignment: 0.8
  
  - id: quorum_consensus
    name: "Quorum Consensus"
    mass: 0.85
    dimension: 0.8
    type: process
    domain: quorum
    alignment: 0.85
  
  - id: adversarial_review
    name: "Adversarial Review"
    mass: 0.8
    dimension: 0.7
    type: process
    domain: quality
    alignment: 0.8
  
  - id: cross_camp_communication
    name: "Cross-Camp Communication"
    mass: 0.75
    dimension: 0.7
    type: process
    domain: protocols
    alignment: 0.75
```

---

## The Growth Rules

```yaml
growth_rules:
  - rule: new_node_inheritance
    description: New nodes inherit mass from parent nodes
    factor: 0.5
  
  - rule: reinforcement
    description: Nodes gain mass when referenced
    factor: 0.1 per_reference
  
  - rule: decay
    description: Nodes lose mass when not referenced
    factor: 0.01 per_day
  
  - rule: alignment_boost
    description: High alignment nodes attract similar nodes
    factor: 0.2
  
  - rule: misalignment_repel
    description: Low alignment nodes are pushed to periphery
    factor: 0.3
  
  - rule: cluster_formation
    description: Related nodes form clusters
    threshold: 3_nodes_with_proximity > 0.7
  
  - rule: ontology_extension
    description: Graphik suggests new ontological branches
    trigger: cluster_size > 10
```

---

## The Archive Rules

```yaml
archive_rules:
  - rule: auto_archive
    condition: mass < 0.1 and age > 30_days
    action: move_to_archive
  
  - rule: manual_archive
    condition: Geno flags as obsolete
    action: move_to_archive
  
  - rule: resurrection
    condition: Referenced after archiving
    action: restore_with_mass_boost
    boost: 0.3
  
  - rule: permanent_archive
    condition: age > 1_year and mass < 0.05
    action: compress_and_store
```

---

## The Knowledge Graph API

```yaml
graph_api:
  - method: create_node
    params: [name, type, domain, content, parent_ids]
    returns: node_id
    
  - method: link_nodes
    params: [source_id, target_id, link_type, strength]
    returns: edge_id
    
  - method: query_nearby
    params: [node_id, radius, limit]
    returns: [node_ids]
    
  - method: query_by_value
    params: [value_name, alignment_threshold]
    returns: [node_ids]
    
  - method: get_mass
    params: [node_id]
    returns: mass_score
    
  - method: update_mass
    params: [node_id, delta]
    returns: new_mass
    
  - method: query_by_camp
    params: [camp_name, domain]
    returns: [node_ids]
    
  - method: search
    params: [query, filters, limit]
    returns: [node_ids with relevance]
    
  - method: get_cluster
    params: [node_id, depth]
    returns: subgraph
    
  - method: suggest_expansion
    params: [node_id, count]
    returns: [suggested_new_nodes]
```

---

*"The graph is not a map. It is a landscape. We do not draw it. We grow it."*
