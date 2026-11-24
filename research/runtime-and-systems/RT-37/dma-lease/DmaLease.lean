import Std

namespace DmaLease

structure Endpoint where
  channel : Nat
  buffer : Nat
deriving DecidableEq, Repr

structure Lease where
  endpoint : Endpoint
  generation : Nat
deriving DecidableEq, Repr

structure Config where
  endpoint : Endpoint
  capacity : Nat
  maxGeneration : Option Nat
deriving Repr

inductive Outcome where
  | completed | cancelled
deriving DecidableEq, Repr

inductive Phase where
  | cpu (next : Nat)
  | running (lease : Lease)
  | cancelling (lease : Lease)
  | ready (lease : Lease) (outcome : Outcome)
  | retired
deriving DecidableEq, Repr

inductive Event where
  | submit
  | cancel (lease : Lease)
  | complete (lease : Lease)
  | quiesced (lease : Lease)
  | acquire (lease : Lease) (cacheSynchronized : Bool)
  | cpuUse
  | deviceWrite (lease : Lease) (offset bytes : Nat)
deriving DecidableEq, Repr

def cpuOwns : Phase → Bool
  | .cpu _ | .retired => true
  | _ => false

def reclaim (limit : Option Nat) (generation : Nat) : Phase :=
  if limit.any (fun maximum => maximum ≤ generation) then .retired else .cpu (generation + 1)

def inRange (config : Config) (offset bytes : Nat) : Prop :=
  0 < bytes ∧ offset + bytes ≤ config.capacity

instance (config : Config) (offset bytes : Nat) : Decidable (inRange config offset bytes) :=
  inferInstanceAs (Decidable (0 < bytes ∧ offset + bytes ≤ config.capacity))

def step (config : Config) (phase : Phase) (event : Event) : Option Phase :=
  match phase, event with
  | .cpu next, .submit =>
      if config.maxGeneration.any (fun maximum => maximum < next) then none
      else some (.running ⟨config.endpoint, next⟩)
  | .running active, .cancel reported =>
      if active = reported then some (.cancelling active) else none
  | .running active, .complete reported =>
      if active = reported then some (.ready active .completed) else none
  | .cancelling active, .quiesced reported =>
      if active = reported then some (.ready active .cancelled) else none
  | .ready active _, .acquire reported synchronized =>
      if active = reported ∧ synchronized = true then some (reclaim config.maxGeneration active.generation)
      else none
  | phase, .cpuUse => if cpuOwns phase then some phase else none
  | .running active, .deviceWrite reported offset bytes =>
      if active = reported ∧ inRange config offset bytes then some (.running active) else none
  | .cancelling active, .deviceWrite reported offset bytes =>
      if active = reported ∧ inRange config offset bytes then some (.cancelling active) else none
  | _, _ => none

theorem unrelatedCompletion (config : Config) {active reported : Lease} (different : active ≠ reported) :
    step config (.running active) (.complete reported) = none := by
  simp [step, different]

theorem unrelatedQuiescence (config : Config) {active reported : Lease} (different : active ≠ reported) :
    step config (.cancelling active) (.quiesced reported) = none := by
  simp [step, different]

theorem earlierGenerationCannotComplete (config : Config) {active reported : Lease}
    (earlier : reported.generation < active.generation) :
    step config (.running active) (.complete reported) = none := by
  apply unrelatedCompletion config
  intro equal
  rw [equal] at earlier
  exact (Nat.lt_irrefl _) earlier

theorem cancelNeedsQuiescence (config : Config) (active : Lease) :
    step config (.running active) (.cancel active) = some (.cancelling active) ∧
    step config (.cancelling active) (.cpuUse) = none ∧
    step config (.cancelling active) (.acquire active true) = none ∧
    step config (.cancelling active) (.complete active) = none := by
  simp [step, cpuOwns]

theorem cpuUseRequiresOwnership (config : Config) {before after : Phase}
    (admitted : step config before .cpuUse = some after) : cpuOwns before = true ∧ before = after := by
  cases before <;> simp_all [step, cpuOwns]

theorem deviceWriteRequiresLeaseAndRange (config : Config) {before after : Phase}
    {lease : Lease} {offset bytes : Nat}
    (admitted : step config before (.deviceWrite lease offset bytes) = some after) :
    (before = .running lease ∨ before = .cancelling lease) ∧ inRange config offset bytes ∧ before = after := by
  cases before <;> simp_all [step] <;> split at admitted <;> simp_all

theorem ownershipExcludesConcurrentWrite (config : Config) {phase after : Phase}
    (cpu : step config phase .cpuUse = some after) (lease : Lease) (offset bytes : Nat) :
    step config phase (.deviceWrite lease offset bytes) = none := by
  have owned := (cpuUseRequiresOwnership config cpu).1
  cases phase <;> simp_all [cpuOwns, step]

theorem acquireChecksCompletionAndSynchronization (config : Config) {before after : Phase}
    {lease : Lease} {cacheSynchronized : Bool}
    (admitted : step config before (.acquire lease cacheSynchronized) = some after) :
    (∃ outcome, before = .ready lease outcome) ∧ cacheSynchronized = true ∧
      after = reclaim config.maxGeneration lease.generation := by
  cases before <;> simp_all [step] <;> split at admitted <;> simp_all

theorem handbackRequiresAcquire (config : Config) {before after : Phase} {event : Event}
    (unowned : cpuOwns before = false) (owned : cpuOwns after = true)
    (admitted : step config before event = some after) :
    ∃ lease outcome, before = .ready lease outcome ∧ event = .acquire lease true := by
  cases before <;> cases event <;> simp_all [step, cpuOwns] <;>
    (obtain ⟨_, rfl⟩ := admitted; simp at owned)

theorem acquireAdvancesOrRetires (limit : Option Nat) (generation : Nat) :
    reclaim limit generation = .cpu (generation + 1) ∨ reclaim limit generation = .retired := by
  unfold reclaim
  split <;> simp

theorem finalGenerationRetires (maximum : Nat) : reclaim (some maximum) maximum = .retired := by
  simp [reclaim]

theorem retiredCannotSubmit (config : Config) : step config .retired .submit = none := by
  rfl

#print axioms unrelatedCompletion
#print axioms unrelatedQuiescence
#print axioms earlierGenerationCannotComplete
#print axioms cancelNeedsQuiescence
#print axioms cpuUseRequiresOwnership
#print axioms deviceWriteRequiresLeaseAndRange
#print axioms ownershipExcludesConcurrentWrite
#print axioms acquireChecksCompletionAndSynchronization
#print axioms handbackRequiresAcquire
#print axioms acquireAdvancesOrRetires
#print axioms finalGenerationRetires
#print axioms retiredCannotSubmit

end DmaLease
