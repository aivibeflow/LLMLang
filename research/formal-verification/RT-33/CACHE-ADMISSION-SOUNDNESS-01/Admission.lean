namespace CacheAdmission

structure Query where
  observed : Nat
  required : Nat
  bound : Nat
deriving DecidableEq

def Counterexample (query : Query) (value : Nat) : Prop :=
  value ≤ query.bound ∧ value = query.observed ∧ value ≠ query.required

def FoldedCounterexample (query : Query) (value : Nat) : Prop :=
  query.observed ≤ query.bound ∧ value = query.observed ∧ value ≠ query.required

theorem foldCorrespondence (query : Query) (value : Nat) :
    Counterexample query value ↔ FoldedCounterexample query value :=
  ⟨fun condition => ⟨condition.2.1 ▸ condition.1, condition.2⟩,
   fun condition => ⟨condition.2.1.symm ▸ condition.1, condition.2⟩⟩

inductive Certificate
  | equalValues
  | outsideScope
  | unsupported

def Check (query : Query) : Certificate → Prop
  | .equalValues => query.observed = query.required
  | .outsideScope => query.bound < query.observed
  | .unsupported => False

theorem checkerSound (query : Query) (certificate : Certificate)
    (checked : Check query certificate) :
    ∀ value, ¬ Counterexample query value := by
  intro value witness
  cases certificate with
  | equalValues =>
    exact witness.2.2 (witness.2.1.trans checked)
  | outsideScope =>
    exact Nat.not_lt_of_ge (witness.2.1 ▸ witness.1) checked
  | unsupported =>
    exact checked

structure Task where
  runValue : Nat
  expected : Nat
  scopeBound : Nat
  revision : Nat
  semantics : Nat
  dependencies : List (Nat × Nat)
  premise : Nat

def lower (task : Task) : Query :=
  ⟨task.runValue, task.expected, task.scopeBound⟩

def SourceHolds (task : Task) : Prop :=
  task.runValue ≤ task.scopeBound ∧ task.runValue = task.expected

structure Receipt where
  query : Query
  revision : Nat
  semantics : Nat
  dependencies : List (Nat × Nat)
  policyEpoch : Nat
  certificate : Certificate

structure Current where
  policyEpoch : Nat
  approvedPremise : Option Nat

structure Admitted (task : Task) (receipt : Receipt) (current : Current) : Prop where
  exactQuery : receipt.query = lower task
  exactRevision : receipt.revision = task.revision
  exactSemantics : receipt.semantics = task.semantics
  exactInventory : receipt.dependencies = task.dependencies
  coversSource : task.runValue ≤ task.scopeBound
  currentEpoch : receipt.policyEpoch = current.policyEpoch
  currentPremise : current.approvedPremise = some task.premise
  checked : Check receipt.query receipt.certificate

theorem admittedSource (task : Task) (receipt : Receipt) (current : Current)
    (accepted : Admitted task receipt current) : SourceHolds task := by
  refine ⟨accepted.coversSource, ?_⟩
  by_cases same : task.runValue = task.expected
  · exact same
  · have impossible := checkerSound receipt.query receipt.certificate accepted.checked
    rw [accepted.exactQuery] at impossible
    exact False.elim (impossible task.runValue ⟨accepted.coversSource, rfl, same⟩)

theorem changedEpochRefuses (task : Task) (receipt : Receipt) (current : Current)
    (different : receipt.policyEpoch ≠ current.policyEpoch) :
    ¬ Admitted task receipt current :=
  fun accepted => different accepted.currentEpoch

theorem revokedPremiseRefuses (task : Task) (receipt : Receipt) (current : Current)
    (revoked : current.approvedPremise = none) :
    ¬ Admitted task receipt current := by
  intro accepted
  have impossible : none = some task.premise := revoked.symm.trans accepted.currentPremise
  cases impossible

theorem differentInventoryRefuses (task : Task) (receipt : Receipt) (current : Current)
    (mismatch : receipt.dependencies ≠ task.dependencies) :
    ¬ Admitted task receipt current :=
  fun accepted => mismatch accepted.exactInventory

theorem unsupportedRefuses (task : Task) (receipt : Receipt) (current : Current)
    (kind : receipt.certificate = .unsupported) :
    ¬ Admitted task receipt current := by
  intro accepted
  have verdict := accepted.checked
  rw [kind] at verdict
  exact verdict

theorem scopedUnsatCanMissSource :
    Check ⟨7, 3, 4⟩ .outsideScope ∧ 7 ≠ 3 :=
  ⟨by change 4 < 7; decide, by decide⟩

end CacheAdmission

#print axioms CacheAdmission.checkerSound
#print axioms CacheAdmission.foldCorrespondence
#print axioms CacheAdmission.admittedSource
#print axioms CacheAdmission.changedEpochRefuses
#print axioms CacheAdmission.revokedPremiseRefuses
#print axioms CacheAdmission.differentInventoryRefuses
#print axioms CacheAdmission.unsupportedRefuses
#print axioms CacheAdmission.scopedUnsatCanMissSource
