# SPG relational schema for caller-scoped verification

This is the full logical schema for [ADR-029](adr/029-caller-scoped-verification-obligations.md) on the [ADR-028 baseline](adr/028-structure-relational-projection.md). The green marker 🟩 identifies new or renamed obligation fields. The schema contains twelve tables. PK and FK mean primary and foreign key. Multiple PK labels in one box form a composite key.

```mermaid
erDiagram
    direction LR
    VERSIONS {
        hash version_hash PK
        string version
        hash binding_hash
    }
    INTERFACES {
        hash interface_hash PK
        text name
        hash public_contract_hash FK
    }
    FUNCTIONS {
        hash impl_hash PK
        ir typed_signature "may contain StructImplHash"
        ir canonical_body "holds exact call and structure references"
        hash provided_contract_hash FK
    }
    CONTRACTS {
        hash contract_hash PK
        text contract_kind "function, structure, or domain"
        text profile
        ir typed_signature "function contract"
        ir state_signature "structure or domain contract"
        texts user_request_texts
        records review_records
    }
    CONTRACT_RULES {
        hash contract_hash PK,FK
        hash rule_hash PK
        text kind
        text error_label "for error rules"
        ir predicate "for predicate rules"
        ir check_boundary "for state rules where applicable"
    }
    BINDINGS {
        hash version_hash PK,FK
        hash interface_hash PK,FK
        hash impl_hash FK
    }
    VERIFICATION_OBLIGATIONS {
        hash obligation_hash PK
        text kind "obligation kind"
        hash caller_impl_hash FK "🟩 required function revision"
        hash callee_impl_hash FK "🟩 call compatibility only"
        hash struct_impl_hash FK "🟩 structure contract check only"
        hash public_contract_hash FK "public refinement only"
        hash caller_required_contract_hash FK "🟩 call compatibility only"
        hash verification_context_hash "digest of exact verification context"
    }
    VERIFICATION_RUNS {
        id run_id PK
        hash obligation_hash FK
        text status
        hash toolchain_digest
        text evidence_ref
        timestamp checked_at
    }
    VERSIONS ||--o{ BINDINGS : selects
    INTERFACES ||..o{ BINDINGS : "interface hash"
    FUNCTIONS ||..o{ BINDINGS : "selected implementation"
    CONTRACTS ||--o{ CONTRACT_RULES : contains
    CONTRACTS ||..o{ INTERFACES : public
    CONTRACTS ||..o{ FUNCTIONS : provided
    FUNCTIONS ||..o{ VERIFICATION_OBLIGATIONS : "🟩 caller_impl_hash"
    FUNCTIONS |o..o{ VERIFICATION_OBLIGATIONS : "🟩 callee_impl_hash"
    STRUCTURES |o..o{ VERIFICATION_OBLIGATIONS : "🟩 struct_impl_hash"
    CONTRACTS |o..o{ VERIFICATION_OBLIGATIONS : public
    CONTRACTS |o..o{ VERIFICATION_OBLIGATIONS : "🟩 caller_required_contract_hash"
    VERIFICATION_OBLIGATIONS ||..o{ VERIFICATION_RUNS : "checked by"
    STRUCTURES {
        hash struct_impl_hash PK
        hash type_hash FK
        hash contract_hash FK "optional own contract"
        ir canonical_declaration "includes ordered named fields"
    }
    STRUCTURE_TYPES {
        hash type_hash PK
        hash identity_hash
        text aggregate_kind
        list ordered_member_types
        ir representation_requirements
    }
    STRUCTURE_LAYOUTS {
        hash layout_hash PK
        hash type_hash FK
        ir target_abi_profile "includes profile version"
        ir layout_descriptor
    }
    STRUCTURE_BINDINGS {
        hash version_hash PK,FK
        text name PK
        hash struct_impl_hash FK
    }
    VERSIONS ||--o{ STRUCTURE_BINDINGS : selects
    STRUCTURES ||..o{ STRUCTURE_BINDINGS : resolves
    STRUCTURE_TYPES ||..o{ STRUCTURES : describes
    STRUCTURE_TYPES ||..o{ STRUCTURE_LAYOUTS : resolves
    CONTRACTS |o..o{ STRUCTURES : "own contract"
```
