import Lean

abbrev maxTicks : Nat := 4294967295
abbrev maxMillis : Nat := 4294967
abbrev scale : Nat := 1000

inductive Reply where
  | armed (value : Nat)
  | range
  deriving DecidableEq, Repr

inductive Event where
  | arm (ticks : Nat)
  | audit
  deriving DecidableEq, Repr

structure Observation where
  reply : Reply
  trace : List Event
  deriving DecidableEq, Repr

def idealProvider (ticks : Nat) : Observation :=
  ⟨.armed ticks, [.arm ticks]⟩

def ProviderContract (provider : Nat → Observation) : Prop :=
  ∀ ticks, ticks ≤ maxTicks → provider ticks = idealProvider ticks

def decode (source : Observation) : Observation :=
  match source.reply with
  | .armed ticks => ⟨.armed (ticks / scale), source.trace⟩
  | .range => source

def adapt (provider : Nat → Observation) (millis : Nat) : Observation :=
  if millis ≤ maxMillis then decode (provider (millis * scale)) else ⟨.range, []⟩

def ClientContract (millis : Nat) (result : Observation) : Prop :=
  (millis * scale ≤ maxTicks ∧ result = ⟨.armed millis, [.arm (millis * scale)]⟩) ∨
    (maxTicks < millis * scale ∧ result = ⟨.range, []⟩)

theorem guardExact (millis : Nat) : millis ≤ maxMillis ↔ millis * scale ≤ maxTicks := by
  unfold maxMillis maxTicks scale
  omega

theorem checkedAdapter (provider : Nat → Observation) (contract : ProviderContract provider) (millis : Nat) :
    ClientContract millis (adapt provider millis) := by
  by_cases accepted : millis ≤ maxMillis
  · have fits := (guardExact millis).mp accepted
    have exactAck := contract (millis * scale) fits
    left
    refine ⟨fits, ?_⟩
    simp [adapt, accepted, exactAck, idealProvider, decode, scale]
  · have over : maxTicks < millis * scale := by
      exact Nat.lt_of_not_ge (fun fits => accepted ((guardExact millis).mpr fits))
    exact Or.inr ⟨over, by simp [adapt, accepted]⟩

def wrapping (millis : Nat) : Observation :=
  decode (idealProvider (millis * scale % (maxTicks + 1)))

def eraseTrace (millis : Nat) : Observation :=
  { adapt idealProvider millis with trace := [] }

def wronglyScaled (millis : Nat) : Observation :=
  decode (idealProvider millis)

def extraEventProvider (ticks : Nat) : Observation :=
  ⟨.armed ticks, [.arm ticks, .audit]⟩

theorem boundaryWrapViolates :
    ¬ ClientContract 4294968 (wrapping 4294968) := by
  unfold ClientContract
  decide

theorem traceErasureViolates :
    ¬ ClientContract 1 (eraseTrace 1) := by
  unfold ClientContract
  decide

theorem wrongScaleViolates :
    ¬ ClientContract 1 (wronglyScaled 1) := by
  unfold ClientContract
  decide

theorem providerAssumptionMatters :
    ¬ ClientContract 1 (adapt extraEventProvider 1) := by
  unfold ClientContract
  decide

#print axioms guardExact
#print axioms checkedAdapter
#print axioms boundaryWrapViolates
#print axioms traceErasureViolates
#print axioms wrongScaleViolates
#print axioms providerAssumptionMatters
