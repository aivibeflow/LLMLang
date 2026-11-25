import Std.Tactic

namespace LoopCost

inductive InnerBound where
  | outerIndex
  | size

def inner (kind : InnerBound) (size index : Nat) : Nat :=
  match kind with
  | .outerIndex => index
  | .size => size

def countRows (row : Nat → Nat) : Nat → Nat
  | 0 => 0
  | k + 1 => countRows row k + row k

def guardedInRow (index : Nat) : Nat → Nat
  | 0 => 0
  | k + 1 => guardedInRow index k + if index ≤ k then 1 else 0

def hits (kind : InnerBound) (n : Nat) : Nat :=
  countRows (fun index => inner kind n index) n

def guarded (kind : InnerBound) (n : Nat) : Nat :=
  countRows (fun index => guardedInRow index (inner kind n index)) n

def triangle : Nat → Nat
  | 0 => 0
  | k + 1 => triangle k + k

theorem guardedInRow_exact (index bound : Nat) :
    guardedInRow index bound = bound - index := by
  induction bound with
  | zero => simp [guardedInRow]
  | succ bound ih =>
    simp only [guardedInRow, ih]
    split <;> omega

theorem countRows_const (value n : Nat) :
    countRows (fun _ => value) n = n * value := by
  induction n with
  | zero => simp [countRows]
  | succ n ih => simp only [countRows, ih, Nat.succ_mul]

theorem triangle_exact (n : Nat) :
    2 * triangle n = n * (n - 1) := by
  induction n with
  | zero => rfl
  | succ n ih =>
    cases n with
    | zero => rfl
    | succ n =>
      change 2 * (triangle (n + 1) + (n + 1)) = (n + 1 + 1) * (n + 1)
      have last : 2 * triangle (n + 1) = (n + 1) * n := by simpa using ih
      have expand : (n + 1 + 1) * (n + 1) = (n + 1) * n + (n + 1) + (n + 1) := by
        rw [Nat.succ_mul (n + 1) (n + 1), Nat.mul_succ (n + 1) n]
      rw [Nat.mul_add, last, expand]
      omega

theorem triangular_hits (n : Nat) : hits .outerIndex n = triangle n := by
  unfold hits
  induction n with
  | zero => rfl
  | succ n ih => simp only [countRows, triangle, inner] at ih ⊢; rw [ih]

theorem triangular_guarded (n : Nat) : guarded .outerIndex n = 0 := by
  unfold guarded
  induction n with
  | zero => rfl
  | succ n ih =>
    simp only [guardedInRow_exact, inner, Nat.sub_self] at ih ⊢
    simpa only [countRows, Nat.add_zero] using ih

theorem square_hits (n : Nat) : hits .size n = n * n := countRows_const n n

def suffix (bound n : Nat) : Nat := countRows (fun index => bound - index) n

theorem suffix_increment (bound n : Nat) (within : n ≤ bound) :
    suffix (bound + 1) n = suffix bound n + n := by
  unfold suffix
  induction n with
  | zero => rfl
  | succ n ih =>
    simp only [countRows]
    rw [ih (by omega)]
    omega

theorem square_suffix (n : Nat) : suffix n n = triangle (n + 1) := by
  induction n with
  | zero => rfl
  | succ n ih =>
    change suffix (n + 1) n + (n + 1 - n) = triangle (n + 1) + (n + 1)
    rw [suffix_increment n n (Nat.le_refl n), ih]
    omega

theorem square_guarded (n : Nat) : guarded .size n = triangle (n + 1) := by
  simpa only [guarded, inner, guardedInRow_exact, suffix] using square_suffix n

theorem triangle_le_square (n : Nat) : triangle n ≤ n * n := by
  induction n with
  | zero => simp [triangle]
  | succ n ih =>
    simp only [triangle, Nat.succ_mul, Nat.mul_succ]
    omega

theorem square_guard_le_hits (n : Nat) : guarded .size n ≤ hits .size n := by
  rw [square_guarded, square_hits]
  have twice := triangle_exact (n + 1)
  simp only [Nat.add_sub_cancel, Nat.add_mul, Nat.one_mul] at twice
  have h : n ≤ n * n := by
    cases n with
    | zero => simp
    | succ n => simp only [Nat.succ_mul, Nat.le_add_left]
  omega

structure CostProfile where
  body : Nat
  guard : Nat
  extra : Nat

def total (profile : CostProfile) (kind : InnerBound) (extra : Bool) (n : Nat) : Nat :=
  profile.body * hits kind n + profile.guard * guarded kind n +
    if extra then profile.extra * hits kind n else 0

def envelopeWeight (profile : CostProfile) (extra : Bool) : Nat :=
  profile.body + profile.guard + if extra then profile.extra else 0

def dependentEnvelope (profile : CostProfile) (kind : InnerBound) (extra : Bool) (n : Nat) : Nat :=
  envelopeWeight profile extra * hits kind n

def rectangularEnvelope (profile : CostProfile) (extra : Bool) (n : Nat) : Nat :=
  envelopeWeight profile extra * (n * n)

theorem dependent_envelope_sound (profile : CostProfile) (kind : InnerBound)
    (extra : Bool) (n : Nat) : total profile kind extra n ≤ dependentEnvelope profile kind extra n := by
  have guardBound : guarded kind n ≤ hits kind n := by
    cases kind
    · rw [triangular_guarded]
      exact Nat.zero_le _
    · exact square_guard_le_hits n
  have guard := Nat.mul_le_mul_left profile.guard guardBound
  cases extra <;> simp only [total, dependentEnvelope, envelopeWeight, Bool.false_eq_true, ↓reduceIte,
    Nat.add_mul, Nat.add_zero] <;> omega

theorem envelope_sound (profile : CostProfile) (kind : InnerBound) (extra : Bool) (n : Nat) :
    total profile kind extra n ≤ rectangularEnvelope profile extra n := by
  have hitsBound : hits kind n ≤ n * n := by
    cases kind
    · rw [triangular_hits]
      exact triangle_le_square n
    · rw [square_hits]
      exact Nat.le_refl _
  exact Nat.le_trans (dependent_envelope_sound profile kind extra n)
    (Nat.mul_le_mul_left (envelopeWeight profile extra) hitsBound)

theorem lowered_extra_work (profile : CostProfile) (kind : InnerBound) (n : Nat) :
    total profile kind true n = total profile kind false n + profile.extra * hits kind n := by
  simp [total]

#print axioms guardedInRow_exact
#print axioms triangle_exact
#print axioms triangular_hits
#print axioms triangular_guarded
#print axioms square_hits
#print axioms square_guarded
#print axioms dependent_envelope_sound
#print axioms envelope_sound
#print axioms lowered_extra_work

end LoopCost
