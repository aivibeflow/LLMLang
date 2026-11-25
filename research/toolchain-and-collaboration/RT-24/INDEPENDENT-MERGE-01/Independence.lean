import Lean

namespace MergeFixture

abbrev Store (Key Value : Type) := Key → Value

structure Patch (Key Value : Type) where
  target : Key
  reads : List Key
  result : Store Key Value → Value
  supported : ∀ left right, (∀ key ∈ reads, left key = right key) → result left = result right

def write [DecidableEq Key] (s : Store Key Value) (target : Key) (value : Value) : Store Key Value :=
  fun key => if key = target then value else s key

def apply [DecidableEq Key] (p : Patch Key Value) (s : Store Key Value) : Store Key Value :=
  write s p.target (p.result s)

theorem resultUnaffected [DecidableEq Key] (p q : Patch Key Value) (s : Store Key Value)
    (disjoint : q.target ∉ p.reads) : p.result (apply q s) = p.result s := by
  apply p.supported
  intro key read
  have neq : key ≠ q.target := fun equal => disjoint (equal ▸ read)
  simp [apply, write, neq]

theorem independentEditsCommute [DecidableEq Key] (left right : Patch Key Value) (s : Store Key Value)
    (writes : left.target ≠ right.target) (leftReads : right.target ∉ left.reads)
    (rightReads : left.target ∉ right.reads) :
    apply left (apply right s) = apply right (apply left s) := by
  have unchangedLeft := resultUnaffected left right s leftReads
  have unchangedRight := resultUnaffected right left s rightReads
  change write (apply right s) left.target (left.result (apply right s)) =
    write (apply left s) right.target (right.result (apply left s))
  rw [unchangedLeft, unchangedRight]
  funext key
  by_cases hitLeft : key = left.target
  · simp [apply, write, hitLeft, writes]
  · by_cases hitRight : key = right.target
    · simp [apply, write, hitRight, Ne.symm writes]
    · simp [apply, write, hitLeft, hitRight]

def capacity (s : Store Bool Nat) : Prop := s false + s true ≤ 1

def allocate (key : Bool) : Patch Bool Nat :=
  ⟨key, [], fun _ => 1, by intro _ _ _; rfl⟩

theorem passingParentsCanFail (s : Store Bool Nat) (zero : ∀ key, s key = 0) :
    capacity (apply (allocate false) s) ∧
    capacity (apply (allocate true) s) ∧
    ¬ capacity (apply (allocate true) (apply (allocate false) s)) := by
  simp [capacity, apply, write, allocate, zero]

#print axioms resultUnaffected
#print axioms independentEditsCommute
#print axioms passingParentsCanFail

end MergeFixture
