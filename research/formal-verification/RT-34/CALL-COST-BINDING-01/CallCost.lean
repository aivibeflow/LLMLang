import Std.Tactic

namespace CallCost

structure Affine where
  rate : Nat
  fixed : Nat
  deriving Repr, DecidableEq

structure Provider where
  reads : Affine
  callbacks : Affine
  deriving Repr

structure Weights where
  read : Nat
  callback : Nat
  deriving Repr

def evaluate (effect : Affine) (size : Nat) : Nat :=
  effect.rate * size + effect.fixed

def concrete (effect : Provider) (weights : Weights) (size : Nat) : Nat :=
  weights.read * evaluate effect.reads size + weights.callback * evaluate effect.callbacks size

def summarize (effect : Provider) (weights : Weights) : Affine :=
  ⟨weights.read * effect.reads.rate + weights.callback * effect.callbacks.rate,
    weights.read * effect.reads.fixed + weights.callback * effect.callbacks.fixed⟩

theorem concrete_summary (effect : Provider) (weights : Weights) (size : Nat) :
    concrete effect weights size = evaluate (summarize effect weights) size := by
  simp only [concrete, summarize, evaluate, Nat.add_mul, Nat.mul_add, Nat.mul_assoc]
  omega

def fits (provider budget : Affine) : Prop :=
  provider.rate ≤ budget.rate ∧ provider.fixed ≤ budget.fixed

instance (provider budget : Affine) : Decidable (fits provider budget) :=
  inferInstanceAs (Decidable (_ ∧ _))

theorem within_budget {provider budget : Affine} (proof : fits provider budget) :
    ∀ size, evaluate provider size ≤ evaluate budget size := by
  intro size
  exact Nat.add_le_add (Nat.mul_le_mul_right size proof.1) proof.2

theorem fixed_counterexample {provider budget : Affine} (excess : budget.fixed < provider.fixed) :
    evaluate budget 0 < evaluate provider 0 := by simpa [evaluate] using excess

theorem slope_counterexample {provider budget : Affine} (excess : budget.rate < provider.rate) :
    evaluate budget (budget.fixed + 1) < evaluate provider (budget.fixed + 1) := by
  have atLeast := Nat.mul_le_mul_right (budget.fixed + 1) (Nat.succ_le_of_lt excess)
  simp only [Nat.succ_mul] at atLeast
  simp only [evaluate]
  omega

theorem exact_condition (provider budget : Affine) :
    fits provider budget ↔ ∀ size, evaluate provider size ≤ evaluate budget size := by
  constructor
  · exact within_budget
  · intro covers
    constructor
    · apply Nat.le_of_not_lt
      intro excess
      have witness := slope_counterexample excess
      have bounded := covers (budget.fixed + 1)
      omega
    · apply Nat.le_of_not_lt
      intro excess
      have witness := fixed_counterexample excess
      have bounded := covers 0
      omega

theorem scoped_call {effect : Provider} {weights : Weights} {budget : Affine}
    (checked : fits (summarize effect weights) budget) (size : Nat) :
    concrete effect weights size ≤ evaluate budget size := by
  rw [concrete_summary]
  exact within_budget checked size

#print axioms exact_condition
#print axioms scoped_call

end CallCost
