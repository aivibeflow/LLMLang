import Lean

namespace Loop

inductive Event where
  | remaining (value : Nat)
  | accumulator (value : Nat)
  deriving Repr, DecidableEq

structure State where
  remaining : Nat
  accumulator : Nat
  trace : List Event
  deriving Repr, DecidableEq

inductive Action where
  | subtract (amount : Nat)
  | add (amount : Nat)
  | emitRemaining
  | emitAccumulator
  deriving Repr

structure Program where
  initialAccumulator : Nat
  stopAt : Nat
  body : List Action

def start (program : Program) (input : Nat) : State :=
  ⟨input, program.initialAccumulator, []⟩

def perform (s : State) : Action → State
  | .subtract n => { s with remaining := s.remaining - n }
  | .add n => { s with accumulator := s.accumulator + n }
  | .emitRemaining => { s with trace := s.trace ++ [.remaining s.remaining] }
  | .emitAccumulator => { s with trace := s.trace ++ [.accumulator s.accumulator] }

def step (program : Program) (s : State) : State :=
  program.body.foldl perform s

def run (program : Program) : Nat → State → Option State
  | 0, s => if program.stopAt < s.remaining then none else some s
  | fuel + 1, s =>
    if program.stopAt < s.remaining then run program fuel (step program s) else some s

def expectedTrace (input stride : Nat) : Nat → List Event
  | 0 => []
  | completed + 1 => expectedTrace input stride completed ++
    [.remaining (input - completed), .accumulator (stride * (completed + 1))]

structure Obligations (program : Program) (Inv Done : Nat → State → Prop) where
  init : ∀ n, Inv n (start program n)
  preserve : ∀ n s, Inv n s → program.stopAt < s.remaining → Inv n (step program s)
  decrease : ∀ s, program.stopAt < s.remaining → (step program s).remaining < s.remaining
  exit : ∀ n s, Inv n s → ¬program.stopAt < s.remaining → Done n s

theorem runChecked {program Inv Done} (obligations : Obligations program Inv Done)
    (input fuel : Nat) (s : State) (invariant : Inv input s)
    (covered : s.remaining ≤ fuel) :
    ∃ t, run program fuel s = some t ∧ Done input t := by
  induction fuel generalizing s with
  | zero =>
    have stop : ¬program.stopAt < s.remaining := by omega
    exact ⟨s, by simp [run, stop], obligations.exit input s invariant stop⟩
  | succ fuel ih =>
    by_cases go : program.stopAt < s.remaining
    · have smaller := obligations.decrease s go
      obtain ⟨t, outcome, done⟩ :=
        ih (step program s) (obligations.preserve input s invariant go) (by omega)
      exact ⟨t, by simpa [run, go] using outcome, done⟩
    · exact ⟨s, by simp [run, go], obligations.exit input s invariant go⟩

theorem total {program Inv Done} (obligations : Obligations program Inv Done) (input : Nat) :
    ∃ t, run program input (start program input) = some t ∧ Done input t :=
  runChecked obligations input input (start program input) (obligations.init input) (by simp [start])

end Loop
