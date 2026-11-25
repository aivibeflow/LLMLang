structure Handle where
  owner : Nat
  generation : Nat
  deriving DecidableEq

inductive Phase where
  | reserved | scrubbed | installed | published | revoking | quiescent
  deriving DecidableEq

inductive Frame where
  | free (generation : Nat)
  | owned (lease : Handle) (phase : Phase)
  deriving DecidableEq

inductive Action where
  | allocate (owner : Nat)
  | scrub (lease : Handle)
  | install (lease : Handle)
  | publish (lease : Handle) (visible : Bool)
  | detach (lease : Handle)
  | acknowledge (lease : Handle) (translationQuiescent : Bool)
  | release (lease : Handle)
  | cancel (lease : Handle)

def operate (frame : Frame) (action : Action) : Frame :=
  match frame, action with
  | .free generation, .allocate owner => .owned ⟨owner, generation + 1⟩ .reserved
  | .owned lease .reserved, .scrub presented =>
    if presented = lease then .owned lease .scrubbed else frame
  | .owned lease .scrubbed, .install presented =>
    if presented = lease then .owned lease .installed else frame
  | .owned lease .installed, .publish presented visible =>
    if presented = lease ∧ visible = true then .owned lease .published else frame
  | .owned lease .published, .detach presented =>
    if presented = lease then .owned lease .revoking else frame
  | .owned lease .revoking, .acknowledge presented translationQuiescent =>
    if presented = lease ∧ translationQuiescent = true then .owned lease .quiescent else frame
  | .owned lease .quiescent, .release presented =>
    if presented = lease then .free lease.generation else frame
  | .owned lease .reserved, .cancel presented | .owned lease .scrubbed, .cancel presented =>
    if presented = lease then .free lease.generation else frame
  | _, _ => frame

def canStart (frame : Frame) (presented : Handle) : Prop :=
  frame = .owned presented .published

def mayUseCachedTranslation (frame : Frame) (presented : Handle) : Prop :=
  canStart frame presented ∨ frame = .owned presented .revoking

theorem absent_acknowledgment_keeps_ownership (lease : Handle) :
    operate (.owned lease .revoking) (.acknowledge lease false) = .owned lease .revoking := by
  simp [operate]

theorem outstanding_translation_blocks_reuse (lease : Handle) (nextOwner : Nat) :
    operate (operate (.owned lease .revoking) (.release lease)) (.allocate nextOwner) =
      .owned lease .revoking := by
  rfl

theorem publishing_requires_visibility (lease : Handle) :
    ¬ canStart (operate (.owned lease .installed) (.publish lease false)) lease := by
  simp [canStart, operate]

theorem retirement_stops_new_calls_but_retains_old_lease (lease : Handle) :
    ¬ canStart (operate (.owned lease .published) (.detach lease)) lease ∧
      mayUseCachedTranslation (operate (.owned lease .published) (.detach lease)) lease := by
  simp [canStart, mayUseCachedTranslation, operate]

theorem acknowledged_reuse_advances_generation (lease : Handle) (nextOwner : Nat) :
    let acknowledged := operate (.owned lease .revoking) (.acknowledge lease true)
    let next := operate (operate acknowledged (.release lease)) (.allocate nextOwner)
    next = .owned ⟨nextOwner, lease.generation + 1⟩ .reserved ∧
      ¬ mayUseCachedTranslation next lease := by
  simp [operate, canStart, mayUseCachedTranslation]

#print axioms absent_acknowledgment_keeps_ownership
#print axioms outstanding_translation_blocks_reuse
#print axioms publishing_requires_visibility
#print axioms retirement_stops_new_calls_but_retains_old_lease
#print axioms acknowledged_reuse_advances_generation
