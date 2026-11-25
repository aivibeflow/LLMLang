structure Platform where
  target : Nat
  abi : Nat
  runtime : Nat
  deployment : Nat

structure Demand where
  scope : Nat
  metric : Nat
  maximum : Nat

structure PerfReceipt where
  artifact : Nat
  scope : Nat
  metric : Nat
  bound : Nat

structure Request where
  platform : Platform
  grantedCapabilities : List Nat
  requiredFeatures : List Nat
  evidenceAuthority : Nat
  performance : Option Demand

structure Candidate where
  artifact : Nat
  platform : Platform
  requiredCapabilities : List Nat
  offeredFeatures : List Nat

structure Evidence where
  artifact : Nat
  authority : Nat
  checked : Bool
  performance : Option PerfReceipt

def included (subset superset : List Nat) : Prop :=
  ∀ value ∈ subset, value ∈ superset

def satisfiesPerformance (artifact : Nat) (request : Option Demand)
    (measurement : Option PerfReceipt) : Prop :=
  match request, measurement with
  | none, _ => True
  | some demand, some evidence =>
    evidence.artifact = artifact ∧ evidence.scope = demand.scope ∧
      evidence.metric = demand.metric ∧ evidence.bound ≤ demand.maximum
  | some _, none => False

def admissible (request : Request) (candidate : Candidate) (evidence : Evidence) : Prop :=
  candidate.platform = request.platform ∧
    included candidate.requiredCapabilities request.grantedCapabilities ∧
    included request.requiredFeatures candidate.offeredFeatures ∧
    evidence.artifact = candidate.artifact ∧ evidence.authority = request.evidenceAuthority ∧
    evidence.checked = true ∧
    satisfiesPerformance candidate.artifact request.performance evidence.performance

theorem capability_grant_widening_preserves_eligibility (request : Request) (candidate : Candidate)
    (evidence : Evidence) (enlarged : List Nat)
    (widening : included request.grantedCapabilities enlarged)
    (eligible : admissible request candidate evidence) :
    admissible { request with grantedCapabilities := enlarged } candidate evidence := by
  obtain ⟨platform, capabilities, features, artifact, authority, checked, performance⟩ := eligible
  exact ⟨platform, fun value mem => widening value (capabilities value mem),
    features, artifact, authority, checked, performance⟩

theorem required_performance_needs_matching_receipt (request : Request) (candidate : Candidate)
    (evidence : Evidence) (demand : Demand) (required : request.performance = some demand)
    (eligible : admissible request candidate evidence) :
    ∃ receipt, evidence.performance = some receipt ∧
      receipt.artifact = candidate.artifact ∧ receipt.scope = demand.scope ∧
      receipt.metric = demand.metric ∧ receipt.bound ≤ demand.maximum := by
  obtain ⟨_, _, _, _, _, _, performance⟩ := eligible
  rw [required] at performance
  cases recorded : evidence.performance with
  | none =>
    simp [satisfiesPerformance, recorded] at performance
  | some receipt =>
    exact ⟨receipt, rfl, by simpa [satisfiesPerformance, recorded] using performance⟩

theorem admitted_constraints_are_conjunctive (request : Request) (candidate : Candidate)
    (evidence : Evidence) (eligible : admissible request candidate evidence) :
    candidate.platform = request.platform ∧
      included candidate.requiredCapabilities request.grantedCapabilities ∧
      included request.requiredFeatures candidate.offeredFeatures ∧
      evidence.artifact = candidate.artifact ∧ evidence.authority = request.evidenceAuthority ∧
      evidence.checked = true := by
  obtain ⟨platform, capabilities, features, artifact, authority, checked, _⟩ := eligible
  exact ⟨platform, capabilities, features, artifact, authority, checked⟩

#print axioms capability_grant_widening_preserves_eligibility
#print axioms required_performance_needs_matching_receipt
#print axioms admitted_constraints_are_conjunctive
