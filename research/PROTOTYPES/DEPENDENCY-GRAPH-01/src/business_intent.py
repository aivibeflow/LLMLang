"""Small end-to-end business-intent-to-contract experiment.

Research prototype only: it models immutable records and a finite tax example.
It does not parse natural language, infer authority, or prove source-code behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .semantic_graph import ContentStore, Dependency, RelationStore, digest


class IntentModelError(ValueError):
    pass


@dataclass(frozen=True)
class IntentSource:
    source_hash: str
    text: str
    source_kind: str

    @classmethod
    def create(cls, text: str, source_kind: str = "stakeholder_statement") -> "IntentSource":
        if not text.strip():
            raise IntentModelError("intent source must not be empty")
        payload = {"domain": "llmlang.intent-source.v1", "text": text,
                   "source_kind": source_kind}
        return cls(digest(payload), text, source_kind)


@dataclass(frozen=True)
class ClarificationDecision:
    decision_hash: str
    source_hash: str
    question: str
    alternatives: tuple[str, ...]
    selected: str
    authority: str

    @classmethod
    def create(cls, source: IntentSource, question: str,
               alternatives: Iterable[str], selected: str,
               authority: str) -> "ClarificationDecision":
        choices = tuple(alternatives)
        if not question.strip() or len(choices) < 2:
            raise IntentModelError("clarification needs a question and at least two alternatives")
        if selected not in choices:
            raise IntentModelError("selected interpretation must be one of the alternatives")
        if not authority.strip():
            raise IntentModelError("clarification authority must be explicit")
        payload = {"domain": "llmlang.clarification-decision.v1",
                   "source_hash": source.source_hash, "question": question,
                   "alternatives": choices, "selected": selected,
                   "authority": authority}
        return cls(digest(payload), source.source_hash, question, choices,
                   selected, authority)


@dataclass(frozen=True)
class BusinessRule:
    rule_hash: str
    caller: str
    rate_basis_points: int
    effective_from: str
    date_basis: str
    source_hash: str
    decision_hash: str

    @classmethod
    def create(cls, caller: str, rate_basis_points: int, effective_from: str,
               date_basis: str, source: IntentSource,
               decision: ClarificationDecision) -> "BusinessRule":
        if not caller.strip():
            raise IntentModelError("caller scope must not be empty")
        if not 0 <= rate_basis_points <= 10_000:
            raise IntentModelError("rate must be between 0 and 10000 basis points")
        try:
            date.fromisoformat(effective_from)
        except ValueError as exc:
            raise IntentModelError("effective_from must be an ISO date") from exc
        if date_basis not in {"order_date", "invoice_date", "processing_date"}:
            raise IntentModelError("date_basis must be explicit")
        if decision.source_hash != source.source_hash:
            raise IntentModelError("decision must refer to the supplied intent source")
        payload = {"domain": "llmlang.business-rule.v1", "caller": caller,
                   "rate_basis_points": rate_basis_points,
                   "effective_from": effective_from, "date_basis": date_basis,
                   "source_hash": source.source_hash,
                   "decision_hash": decision.decision_hash}
        return cls(digest(payload), caller, rate_basis_points, effective_from,
                   date_basis, source.source_hash, decision.decision_hash)


@dataclass(frozen=True)
class FormalClause:
    clause_hash: str
    clause_id: str
    predicate: str
    explanation: str
    source_refs: tuple[str, ...]
    decision_refs: tuple[str, ...]
    provenance_status: str

    @classmethod
    def create(cls, clause_id: str, predicate: str, explanation: str,
               source_refs: Iterable[str], decision_refs: Iterable[str] = (),
               provenance_status: str = "GROUNDED") -> "FormalClause":
        sources, decisions = tuple(sorted(set(source_refs))), tuple(sorted(set(decision_refs)))
        if not clause_id or not predicate or not explanation:
            raise IntentModelError("clause id, predicate, and explanation are required")
        if provenance_status not in {"GROUNDED", "ASSUMED", "INFERRED", "UNRESOLVED"}:
            raise IntentModelError("unsupported provenance status")
        payload = {"domain": "llmlang.formal-clause.v1", "clause_id": clause_id,
                   "predicate": predicate, "explanation": explanation,
                   "source_refs": sources, "decision_refs": decisions,
                   "provenance_status": provenance_status}
        return cls(digest(payload), clause_id, predicate, explanation,
                   sources, decisions, provenance_status)


@dataclass(frozen=True)
class FormalCandidate:
    candidate_hash: str
    scope: str
    rule_hash: str
    clauses: tuple[FormalClause, ...]
    assumptions: tuple[str, ...]
    unresolved_items: tuple[str, ...]

    @classmethod
    def create(cls, scope: str, rule: BusinessRule,
               clauses: Iterable[FormalClause], assumptions: Iterable[str] = (),
               unresolved_items: Iterable[str] = ()) -> "FormalCandidate":
        clause_rows = tuple(sorted(clauses, key=lambda c: c.clause_id))
        if not scope or not clause_rows:
            raise IntentModelError("candidate needs scope and at least one clause")
        if len({c.clause_id for c in clause_rows}) != len(clause_rows):
            raise IntentModelError("clause ids must be unique")
        assumption_rows = tuple(sorted(set(assumptions)))
        unresolved = tuple(sorted(set(unresolved_items)))
        payload = {"domain": "llmlang.formal-candidate.v1", "scope": scope,
                   "rule_hash": rule.rule_hash,
                   "clauses": [c.clause_hash for c in clause_rows],
                   "assumptions": assumption_rows, "unresolved_items": unresolved}
        return cls(digest(payload), scope, rule.rule_hash, clause_rows,
                   assumption_rows, unresolved)


@dataclass(frozen=True)
class ValidatedContract:
    contract_hash: str
    candidate_hash: str
    scope: str
    assumptions: tuple[str, ...]
    approved_by: str
    approval_hash: str


def accept_candidate(candidate: FormalCandidate, approved_by: str,
                     authorized: bool) -> ValidatedContract:
    """Accept only a grounded, resolved candidate with explicit authority."""
    if not authorized or not approved_by.strip():
        raise IntentModelError("authorized human approval is required")
    if candidate.unresolved_items:
        raise IntentModelError("candidate has unresolved business questions")
    for clause in candidate.clauses:
        if clause.provenance_status != "GROUNDED":
            raise IntentModelError(f"clause {clause.clause_id} is not grounded")
        if not clause.source_refs and not clause.decision_refs:
            raise IntentModelError(f"clause {clause.clause_id} has no provenance")
    contract_hash = digest({"domain": "llmlang.validated-contract.v1",
                            "candidate_hash": candidate.candidate_hash,
                            "scope": candidate.scope,
                            "assumptions": candidate.assumptions})
    approval_hash = digest({"domain": "llmlang.contract-approval.v1",
                            "contract_hash": contract_hash,
                            "approved_by": approved_by})
    return ValidatedContract(contract_hash, candidate.candidate_hash,
                             candidate.scope, candidate.assumptions,
                             approved_by, approval_hash)


def candidate_from_rule(rule: BusinessRule) -> FormalCandidate:
    """Create transparent illustrative predicates; this is not NL translation."""
    clauses = (
        FormalClause.create(
            "applicability",
            f"caller == {rule.caller} AND {rule.date_basis} >= {rule.effective_from}",
            f"Apply this caller's rule to orders whose {rule.date_basis} is on or after {rule.effective_from}.",
            [rule.source_hash], [rule.decision_hash]),
        FormalClause.create(
            "selected-rate",
            f"selected_rate_basis_points == {rule.rate_basis_points}",
            f"The applicable rate for this caller is {rule.rate_basis_points / 100:.2f}%.",
            [rule.source_hash], [rule.decision_hash]),
    )
    return FormalCandidate.create(rule.caller, rule, clauses)


def select_applicable_rate(rules: Iterable[BusinessRule], order_date: str,
                           invoice_date: str) -> int:
    """Resolve a caller's versioned rate using each rule's declared date basis."""
    rows = tuple(rules)
    if not rows:
        raise IntentModelError("at least one business-rule version is required")
    caller = rows[0].caller
    if any(rule.caller != caller for rule in rows):
        raise IntentModelError("cannot resolve rules belonging to different callers")
    eligible = []
    for rule in rows:
        basis_value = order_date if rule.date_basis == "order_date" else invoice_date
        if rule.date_basis == "processing_date":
            raise IntentModelError("processing_date requires an explicit processing-date input")
        if date.fromisoformat(basis_value) >= date.fromisoformat(rule.effective_from):
            eligible.append(rule)
    if not eligible:
        raise IntentModelError("no rule applies to the supplied dates")
    return max(eligible, key=lambda rule: rule.effective_from).rate_basis_points


def calculate_tax(taxable_basis_cents: int, rate_basis_points: int) -> int:
    """Generic calculation: integer cents, basis points, round half up."""
    if taxable_basis_cents < 0:
        raise IntentModelError("taxable basis must not be negative")
    if not 0 <= rate_basis_points <= 10_000:
        raise IntentModelError("rate must be between 0 and 10000 basis points")
    return (taxable_basis_cents * rate_basis_points + 5_000) // 10_000


def build_scenario_snapshot(store: ContentStore, tax_contract_hash: str,
                            caller_rules: dict[str, BusinessRule]) -> tuple[str, dict[str, str]]:
    """Hash a snapshot whose caller selections depend on their own rule values."""
    selections = {"callee:calculate_tax": tax_contract_hash}
    for caller, rule in sorted(caller_rules.items()):
        if caller != rule.caller:
            raise IntentModelError("rule map key must match rule caller")
        rule_value_hash = store.put("business_rule", {
            "caller": caller, "rate_basis_points": rule.rate_basis_points,
            "effective_from": rule.effective_from, "date_basis": rule.date_basis,
            "source_hash": rule.source_hash, "decision_hash": rule.decision_hash,
        })
        value_hash = store.put(
            "caller_policy",
            {"caller": caller, "rate_basis_points": rule.rate_basis_points,
             "effective_from": rule.effective_from, "date_basis": rule.date_basis},
            [Dependency("governed_by", rule_value_hash, "business-rule")],
        )
        selections[f"caller:{caller}"] = value_hash
    from .semantic_graph import make_snapshot
    snapshot = make_snapshot(selections)
    return snapshot.root_hash, selections


def run_two_caller_scenario() -> dict[str, object]:
    """Demonstrate a caller-scoped policy change with an unchanged generic callee."""
    store, relations = ContentStore(), RelationStore()
    original = IntentSource.create(
        "Since 2026-01-01, preferred customers receive a reduced tax rate of 15%.")
    original_decision = ClarificationDecision.create(
        original, "Which date determines applicability?",
        ["order_date", "invoice_date"], "order_date", "Tax policy owner")
    standard_source = IntentSource.create(
        "Since 2026-01-01, standard orders use the standard tax rate of 20%.")
    standard_decision = ClarificationDecision.create(
        standard_source, "Which date determines applicability?",
        ["order_date", "invoice_date"], "order_date", "Tax policy owner")
    # Preserve original source and clarification records as immutable semantic values.
    for source in (original, standard_source):
        store.put("intent_source", {
            "text": source.text, "source_kind": source.source_kind})
    for decision in (original_decision, standard_decision):
        store.put("clarification_decision", {
            "source_hash": decision.source_hash, "question": decision.question,
            "alternatives": list(decision.alternatives), "selected": decision.selected,
            "authority": decision.authority})
    preferred_old = BusinessRule.create("preferred_order", 1500, "2026-01-01",
                                        "order_date", original, original_decision)
    standard = BusinessRule.create("standard_order", 2000, "2026-01-01",
                                   "order_date", standard_source, standard_decision)

    # The shared callee contract is independent of the caller's selected rate.
    tax_contract_hash = store.put("contract", {
        "operation": "calculate_tax",
        "inputs": ["taxable_basis_cents", "rate_basis_points"],
        "result": "integer_tax_cents",
        "rounding": "half_up_to_cent",
        "rate_domain": [0, 10000],
    })
    old_snapshot, old_selections = build_scenario_snapshot(
        store, tax_contract_hash,
        {"preferred_order": preferred_old, "standard_order": standard})

    changed_source = IntentSource.create(
        "Reduce the preferred-customer tax rate to 12% starting next month.")
    date_decision = ClarificationDecision.create(
        changed_source,
        "Does 'starting next month' mean order date or invoice processing date, and what is the effective date?",
        ["order_date from 2026-12-01", "invoice_date from 2026-12-01"],
        "order_date from 2026-12-01", "Tax policy owner")
    store.put("intent_source", {
        "text": changed_source.text, "source_kind": changed_source.source_kind})
    store.put("clarification_decision", {
        "source_hash": date_decision.source_hash, "question": date_decision.question,
        "alternatives": list(date_decision.alternatives), "selected": date_decision.selected,
        "authority": date_decision.authority})
    preferred_new = BusinessRule.create("preferred_order", 1200, "2026-12-01",
                                        "order_date", changed_source, date_decision)
    # Construct an explicitly alternative interpretation for counterexample review only.
    invoice_old_decision = ClarificationDecision.create(
        original, "Which date determines applicability?",
        ["order_date", "invoice_date"], "invoice_date", "Tax policy owner")
    invoice_new_decision = ClarificationDecision.create(
        changed_source, date_decision.question,
        ["order_date from 2026-12-01", "invoice_date from 2026-12-01"],
        "invoice_date from 2026-12-01", "Tax policy owner")
    preferred_old_invoice = BusinessRule.create(
        "preferred_order", 1500, "2026-01-01", "invoice_date", original,
        invoice_old_decision)
    preferred_new_invoice = BusinessRule.create(
        "preferred_order", 1200, "2026-12-01", "invoice_date", changed_source,
        invoice_new_decision)
    candidate = candidate_from_rule(preferred_new)
    accepted = accept_candidate(candidate, "Tax policy owner", authorized=True)

    # Store immutable semantic values and contextual provenance separately.
    rule_value = store.put("business_rule", {
        "caller": preferred_new.caller,
        "rate_basis_points": preferred_new.rate_basis_points,
        "effective_from": preferred_new.effective_from,
        "date_basis": preferred_new.date_basis,
    })
    clause_values = []
    for clause in candidate.clauses:
        clause_values.append(store.put("formal_clause", {
            "clause_id": clause.clause_id, "predicate": clause.predicate,
            "explanation": clause.explanation, "source_refs": list(clause.source_refs),
            "decision_refs": list(clause.decision_refs),
            "provenance_status": clause.provenance_status}))
    candidate_value = store.put("formal_candidate", {
        "candidate_hash": candidate.candidate_hash, "scope": candidate.scope,
        "clause_values": clause_values, "assumptions": list(candidate.assumptions),
    }, [Dependency("formalizes", rule_value, "business-rule")])
    contract_value = store.put("validated_contract", {
        "contract_hash": accepted.contract_hash,
        "candidate_hash": accepted.candidate_hash,
        "scope": accepted.scope,
        "assumptions": list(accepted.assumptions),
        "approval_hash": accepted.approval_hash,
    }, [Dependency("accepts", candidate_value, "formal-candidate")])
    relations.add("scenario-16", contract_value, "derived_from_intent", changed_source.source_hash)
    relations.add("scenario-16", contract_value, "confirmed_by_decision", date_decision.decision_hash)

    new_snapshot, new_selections = build_scenario_snapshot(
        store, tax_contract_hash,
        {"preferred_order": preferred_new, "standard_order": standard})

    changed_keys = sorted(k for k in old_selections
                          if old_selections[k] != new_selections[k])
    return {
        "old_snapshot": old_snapshot,
        "new_snapshot": new_snapshot,
        "changed_selection_keys": changed_keys,
        "tax_contract_unchanged": old_selections["callee:calculate_tax"] ==
                                  new_selections["callee:calculate_tax"],
        "standard_caller_unchanged": old_selections["caller:standard_order"] ==
                                     new_selections["caller:standard_order"],
        "preferred_caller_changed": old_selections["caller:preferred_order"] !=
                                    new_selections["caller:preferred_order"],
        "old_rate_basis_points": preferred_old.rate_basis_points,
        "new_rate_basis_points": preferred_new.rate_basis_points,
        "standard_rate_basis_points": standard.rate_basis_points,
        "accepted_contract_hash": accepted.contract_hash,
        "approval_hash": accepted.approval_hash,
        "formal_candidate_hash": candidate.candidate_hash,
        "old_tax_contract_hash": old_selections["callee:calculate_tax"],
        "new_tax_contract_hash": new_selections["callee:calculate_tax"],
        "tax_10000_cents_at_12_percent": calculate_tax(10_000, 1200),
        "tax_10000_cents_at_20_percent": calculate_tax(10_000, 2000),
        "review_examples": {
            "day_before_effective_date": select_applicable_rate(
                [preferred_old, preferred_new], "2026-11-30", "2026-12-05"),
            "effective_date_boundary": select_applicable_rate(
                [preferred_old, preferred_new], "2026-12-01", "2026-11-30"),
            "counterexample_order_before_invoice_after": {
                "order_date_interpretation": select_applicable_rate(
                    [preferred_old, preferred_new], "2026-11-30", "2026-12-05"),
                "invoice_date_interpretation": select_applicable_rate(
                    [preferred_old_invoice, preferred_new_invoice],
                    "2026-11-30", "2026-12-05"),
            },
            "counterexample_order_after_invoice_before": {
                "order_date_interpretation": select_applicable_rate(
                    [preferred_old, preferred_new], "2026-12-01", "2026-11-30"),
                "invoice_date_interpretation": select_applicable_rate(
                    [preferred_old_invoice, preferred_new_invoice],
                    "2026-12-01", "2026-11-30"),
            },
        },
        "provenance_relations": sorted(relations.for_scope("scenario-16")),
        "semantic_values_stored": len(store),
    }
