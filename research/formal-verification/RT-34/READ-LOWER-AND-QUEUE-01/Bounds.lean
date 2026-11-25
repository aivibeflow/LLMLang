def zeroInput {n : Nat} (_ : Fin n) : Bool := false

def spike {n : Nat} (i j : Fin n) : Bool := decide (j = i)

def HasTrue {n : Nat} (input : Fin n → Bool) : Prop := ∃ i, input i = true

theorem unread_determines_failure {n : Nat} (read : List (Fin n))
    (eval : (Fin n → Bool) → Bool)
    (correct : ∀ input, eval input = true ↔ HasTrue input)
    (fixedRun : ∀ input, (∀ i ∈ read, input i = zeroInput i) →
      eval input = eval zeroInput)
    (i : Fin n) : i ∈ read := by
  apply Classical.byContradiction
  intro missing
  have same : ∀ j ∈ read, spike i j = zeroInput j := by
    intro j seen
    have distinct : j ≠ i := by
      intro equal
      apply missing
      simpa [equal] using seen
    simp [spike, zeroInput, distinct]
  have accepted : eval (spike i) = true := (correct _).mpr ⟨i, by simp [spike]⟩
  have rejected : ¬ eval zeroInput = true := by
    intro result
    obtain ⟨j, seen⟩ := (correct _).mp result
    simp [zeroInput] at seen
  exact rejected ((fixedRun (spike i) same).symm.trans accepted)

theorem lower_reads {n : Nat} (read : List (Fin n))
    (eval : (Fin n → Bool) → Bool)
    (correct : ∀ input, eval input = true ↔ HasTrue input)
    (fixedRun : ∀ input, (∀ i ∈ read, input i = zeroInput i) →
      eval input = eval zeroInput) : n ≤ read.length := by
  have subset : List.finRange n ⊆ read := by
    intro i _
    exact unread_determines_failure read eval correct fixedRun i
  simpa using (List.nodup_finRange n).length_le_of_subset subset

def scan {n : Nat} (input : Fin n → Bool) : Bool :=
  (List.finRange n).any input

theorem scan_correct {n : Nat} (input : Fin n → Bool) :
    scan input = true ↔ HasTrue input := by
  simp [scan, HasTrue, List.any_eq_true]

theorem scan_reads (n : Nat) : (List.finRange n).length = n := by
  simp

structure QueueModel where
  incoming : Nat
  outgoing : Nat

inductive Step : QueueModel → QueueModel → Nat → Prop where
  | push (a b : Nat) : Step ⟨a, b⟩ ⟨a + 1, b⟩ 1
  | pop (a b : Nat) : Step ⟨a, b + 1⟩ ⟨a, b⟩ 1
  | transfer (a : Nat) : Step ⟨a + 1, 0⟩ ⟨0, a⟩ (1 + 2 * (a + 1))

def potential (s : QueueModel) : Nat := 2 * s.incoming

theorem step_charge {before after : QueueModel} {cost : Nat}
    (transition : Step before after cost) :
    cost + potential after ≤ 3 + potential before := by
  cases transition <;> simp [potential] <;> omega

inductive History : QueueModel → QueueModel → Nat → Nat → Prop where
  | empty (s : QueueModel) : History s s 0 0
  | next {start intermediate finish : QueueModel} {count total cost : Nat}
      (previous : History start intermediate count total)
      (transition : Step intermediate finish cost) :
      History start finish (count + 1) (total + cost)

theorem history_charge {start finish : QueueModel} {count total : Nat}
    (path : History start finish count total) :
    total + potential finish ≤ 3 * count + potential start := by
  induction path with
  | empty => simp
  | next _ transition previous =>
    have localBound := step_charge transition
    omega

def live (incoming outgoing held : Nat) : Nat := incoming + outgoing + held

theorem live_during_move (incoming outgoing : Nat) :
    live (incoming + 1) outgoing 0 = live incoming outgoing 1 ∧
    live incoming outgoing 1 = live incoming (outgoing + 1) 0 := by
  unfold live
  omega

theorem copy_peak_exceeds (n : Nat) (nonempty : 0 < n) : n < 2 * n := by
  omega

#print axioms unread_determines_failure
#print axioms lower_reads
#print axioms scan_correct
#print axioms scan_reads
#print axioms step_charge
#print axioms history_charge
#print axioms live_during_move
#print axioms copy_peak_exceeds
