import Std

namespace FrameAllocator

inductive Frame where
  | free
  | reserved
  | zeroed
  | owned (slot : Nat)
  deriving DecidableEq, Repr

def counts : Frame → Nat × Nat × Nat
  | .free => (1, 0, 0)
  | .reserved | .zeroed => (0, 1, 0)
  | .owned _ => (0, 0, 1)

def tally : List Frame → Nat × Nat × Nat
  | [] => (0, 0, 0)
  | frame :: rest =>
    let (free, reserved, owned) := tally rest
    let (f, r, o) := counts frame
    (free + f, reserved + r, owned + o)

theorem conservation (frames : List Frame) :
    (tally frames).1 + (tally frames).2.1 + (tally frames).2.2 = frames.length := by
  induction frames with
  | nil => rfl
  | cons frame rest ih =>
    generalize h : tally rest = countsRest at *
    rcases countsRest with ⟨free, reserved, owned⟩
    cases frame <;> simp [tally, h, counts] at * <;> omega

inductive Transition : Frame → Frame → Prop where
  | reserve : Transition .free .reserved
  | scrub : Transition .reserved .zeroed
  | publish : Transition .zeroed (.owned slot)
  | abortDirty : Transition .reserved .free
  | abortZeroed : Transition .zeroed .free
  | release : Transition (.owned slot) .free

theorem publication_requires_zero (before : Frame) (slot : Nat)
    (step : Transition before (.owned slot)) : before = .zeroed := by
  cases step
  rfl

theorem no_double_allocation (slot : Nat) (step : Transition (.owned slot) after) :
    after = .free := by
  cases step
  rfl

theorem both_abort_points_restore_free :
    Transition .reserved .free ∧ Transition .zeroed .free :=
  ⟨.abortDirty, .abortZeroed⟩

theorem unique_owner (frame : Frame) (first second : Nat)
    (h₁ : frame = .owned first) (h₂ : frame = .owned second) : first = second := by
  exact Frame.owned.inj (h₁.symm.trans h₂)

#print axioms conservation
#print axioms publication_requires_zero
#print axioms no_double_allocation
#print axioms both_abort_points_restore_free
#print axioms unique_owner

end FrameAllocator
