import Lean

structure Step where
  destination : Nat
  bound : Int

def stepsHold (valuation : Nat → Int) (origin : Nat) : List Step → Prop
  | [] => True
  | step :: rest =>
    valuation step.destination - valuation origin ≤ step.bound ∧
      stepsHold valuation step.destination rest

def endOf (origin : Nat) : List Step → Nat
  | [] => origin
  | step :: rest => endOf step.destination rest

def boundSum : List Step → Int
  | [] => 0
  | step :: rest => step.bound + boundSum rest

theorem telescopes (valuation : Nat → Int) (steps : List Step) (origin : Nat)
    (valid : stepsHold valuation origin steps) :
    valuation (endOf origin steps) - valuation origin ≤ boundSum steps := by
  induction steps generalizing origin with
  | nil => simp [endOf, boundSum]
  | cons step rest inductionHypothesis =>
    rcases valid with ⟨edge, remaining⟩
    have suffix := inductionHypothesis step.destination remaining
    simp only [endOf, boundSum]
    omega

theorem negativeClosedWalk
    (valuation : Nat → Int) (origin : Nat) (steps : List Step)
    (closed : endOf origin steps = origin) (negative : boundSum steps < 0) :
    ¬ stepsHold valuation origin steps := by
  intro valid
  have limit := telescopes valuation steps origin valid
  rw [closed] at limit
  omega

#print axioms telescopes
#print axioms negativeClosedWalk
