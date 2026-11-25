structure Request where
  operation : Nat
  contract : Nat
  deriving DecidableEq

structure Descriptor where
  request : Request
  artifact : Nat
  deriving DecidableEq

structure Snapshot where
  root : Nat
  descriptors : List Descriptor

structure Discovery where
  root : Nat
  request : Request
  candidates : List Descriptor
  deriving DecidableEq

structure TargetReceipt where
  artifact : Nat
  target : Nat
  checked : Bool
  materialized : Bool

def discover (request : Request) (snapshot : Snapshot) : Discovery :=
  ⟨snapshot.root, request, snapshot.descriptors.filter fun descriptor =>
    decide (descriptor.request = request)⟩

def bindArtifact (request : Request) (snapshot : Snapshot) (prior : Discovery)
    (candidate : Descriptor) (target : Nat) (receipt : TargetReceipt) : Option Nat :=
  if prior = discover request snapshot ∧ candidate ∈ prior.candidates ∧
    receipt.artifact = candidate.artifact ∧ receipt.target = target ∧
    receipt.checked = true ∧ receipt.materialized = true then
    some candidate.artifact
  else none

theorem discovery_membership (request : Request) (snapshot : Snapshot) (candidate : Descriptor) :
    candidate ∈ (discover request snapshot).candidates ↔
      candidate ∈ snapshot.descriptors ∧ candidate.request = request := by
  simp [discover, List.mem_filter]

theorem bind_requires_current_catalog (request : Request) (snapshot : Snapshot) (prior : Discovery)
    (candidate : Descriptor) (target artifact : Nat) (receipt : TargetReceipt)
    (bound : bindArtifact request snapshot prior candidate target receipt = some artifact) :
    prior = discover request snapshot ∧ candidate ∈ snapshot.descriptors ∧
      candidate.request = request ∧ artifact = candidate.artifact ∧
      receipt.artifact = artifact ∧ receipt.target = target ∧
      receipt.checked = true ∧ receipt.materialized = true := by
  unfold bindArtifact at bound
  split at bound
  next eligible =>
    obtain ⟨fresh, member, routedArtifact, routedTarget, checked, materialized⟩ := eligible
    have compatible := (discovery_membership request snapshot candidate).1 (fresh ▸ member)
    have chosen : candidate.artifact = artifact := Option.some.inj bound
    exact ⟨fresh, compatible.1, compatible.2, chosen.symm, routedArtifact.trans chosen,
      routedTarget, checked, materialized⟩
  next => contradiction

theorem bind_succeeds_for_admissible (request : Request) (snapshot : Snapshot)
    (candidate : Descriptor) (target : Nat) (receipt : TargetReceipt)
    (member : candidate ∈ snapshot.descriptors) (compatible : candidate.request = request)
    (artifactMatches : receipt.artifact = candidate.artifact) (targetMatches : receipt.target = target)
    (checked : receipt.checked = true) (materialized : receipt.materialized = true) :
    bindArtifact request snapshot (discover request snapshot) candidate target receipt = some candidate.artifact := by
  have discovered := (discovery_membership request snapshot candidate).2 ⟨member, compatible⟩
  simp [bindArtifact, discovered, artifactMatches, targetMatches, checked, materialized]

#print axioms discovery_membership
#print axioms bind_requires_current_catalog
#print axioms bind_succeeds_for_admissible
