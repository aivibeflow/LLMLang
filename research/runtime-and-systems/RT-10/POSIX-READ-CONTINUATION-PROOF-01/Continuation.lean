namespace ReadContinuation

structure Cursor (α : Type) where
  recorded : List α
  remaining : List α

def combined (state : Cursor α) : List α := state.recorded ++ state.remaining

def advance (state : Cursor α) (reported : Nat) (bytes : List α) : Cursor α :=
  ⟨state.recorded ++ bytes, state.remaining.drop reported⟩

theorem stepConserves (state : Cursor α) (reported : Nat) (bytes : List α)
    (suppliedPrefix : bytes = state.remaining.take reported) :
    combined (advance state reported bytes) = combined state := by
  simp [combined, advance, suppliedPrefix, List.append_assoc, List.take_append_drop]

inductive History : Cursor α → Cursor α → Prop
  | finished (state : Cursor α) : History state state
  | read (state last : Cursor α) (reported : Nat) (bytes : List α) :
      reported ≤ state.remaining.length →
      bytes = state.remaining.take reported →
      History (advance state reported bytes) last →
      History state last

theorem historyConserves {start last : Cursor α} (trace : History start last) :
    combined last = combined start := by
  induction trace with
  | finished => rfl
  | read state _last reported bytes _bound sourcePrefix _tail inductionHypothesis =>
    exact inductionHypothesis.trans (stepConserves state reported bytes sourcePrefix)

theorem completeRecovers {start last : Cursor α} (trace : History start last)
    (empty : last.remaining = []) :
    last.recorded = combined start := by
  have conserved := historyConserves trace
  simpa [combined, empty] using conserved

theorem zeroProgress (state : Cursor α) : advance state 0 [] = state := by
  cases state
  simp [advance]

theorem countAloneCanDisagree :
    let start : Cursor Nat := ⟨[], [1, 2, 3]⟩
    ([9] : List Nat).length = 1 ∧ combined (advance start 1 [9]) ≠ combined start := by
  decide

#print axioms stepConserves
#print axioms historyConserves
#print axioms completeRecovers
#print axioms zeroProgress
#print axioms countAloneCanDisagree

end ReadContinuation
