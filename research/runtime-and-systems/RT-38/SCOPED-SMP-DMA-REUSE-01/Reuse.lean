inductive Kind
  | localHart | remoteHart | dmaDrain | deviceVisibility
  deriving DecidableEq

structure Scope where
  frame : Nat
  generation : Nat
  epoch : Nat
  deriving DecidableEq

structure Receipt where
  kind : Kind
  scope : Scope
  afterDetach : Bool

def covers (target : Scope) (kind : Kind) (receipt : Receipt) : Prop :=
  receipt.kind = kind ∧ receipt.scope = target ∧ receipt.afterDetach = true

def witnessed (target : Scope) (kind : Kind) (ledger : List Receipt) : Prop :=
  ∃ receipt, receipt ∈ ledger ∧ covers target kind receipt

def allowed (target : Scope) (detached deviceRequired : Bool) (ledger : List Receipt) : Prop :=
  detached = true ∧
    witnessed target .localHart ledger ∧ witnessed target .remoteHart ledger ∧
    (deviceRequired = true → witnessed target .dmaDrain ledger ∧
                            witnessed target .deviceVisibility ledger)

theorem admittedRequiresBothHarts (target : Scope) (detached dma : Bool) (ledger : List Receipt)
    (h : allowed target detached dma ledger) :
    witnessed target .localHart ledger ∧ witnessed target .remoteHart ledger :=
  ⟨h.2.1, h.2.2.1⟩

theorem admittedDeviceRequiresDrainAndVisibility (target : Scope) (detached : Bool)
    (ledger : List Receipt) (h : allowed target detached true ledger) :
    witnessed target .dmaDrain ledger ∧ witnessed target .deviceVisibility ledger :=
  h.2.2.2 rfl

theorem wrongEpochRefused (target : Scope) (kind : Kind) (receipt : Receipt)
    (h : receipt.scope.epoch ≠ target.epoch) : ¬ covers target kind receipt :=
  fun admitted => h (congrArg Scope.epoch admitted.2.1)

theorem wrongGenerationRefused (target : Scope) (kind : Kind) (receipt : Receipt)
    (h : receipt.scope.generation ≠ target.generation) : ¬ covers target kind receipt :=
  fun admitted => h (congrArg Scope.generation admitted.2.1)

theorem earlyReceiptRefused (target : Scope) (kind : Kind) (receipt : Receipt)
    (h : receipt.afterDetach = false) : ¬ covers target kind receipt :=
  fun admitted => Bool.noConfusion (h.symm.trans admitted.2.2)

theorem beforeDetachRefused (target : Scope) (deviceRequired : Bool) (ledger : List Receipt) :
    ¬ allowed target false deviceRequired ledger :=
  fun admitted => Bool.noConfusion admitted.1

theorem cpuOnlyAllows (target : Scope) (ledger : List Receipt)
    (lh : witnessed target .localHart ledger) (rh : witnessed target .remoteHart ledger) :
    allowed target true false ledger :=
  ⟨rfl, lh, rh, fun impossible => Bool.noConfusion impossible⟩

#print axioms admittedRequiresBothHarts
#print axioms admittedDeviceRequiresDrainAndVisibility
#print axioms wrongEpochRefused
#print axioms wrongGenerationRefused
#print axioms earlyReceiptRefused
#print axioms beforeDetachRefused
#print axioms cpuOnlyAllows
