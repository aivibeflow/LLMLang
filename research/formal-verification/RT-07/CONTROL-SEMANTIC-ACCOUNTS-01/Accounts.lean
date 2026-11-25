inductive Observation where
  | returned | error | deadlock | unfinished
  deriving DecidableEq

inductive Unfolding where
  | stop (result : Observation)
  | choose (left right : Unfolding)

inductive Reaches : Unfolding → Observation → Prop where
  | stop : Reaches (.stop result) result
  | left : Reaches left result → Reaches (.choose left right) result
  | right : Reaches right result → Reaches (.choose left right) result

def backwards (post : Observation → Prop) : Unfolding → Prop
  | .stop result => post result
  | .choose left right => backwards post left ∧ backwards post right

theorem backwards_iff_all (post : Observation → Prop) (tree : Unfolding) :
    backwards post tree ↔ ∀ result, Reaches tree result → post result := by
  induction tree with
  | stop terminal =>
    constructor
    · intro holds result path
      cases path
      exact holds
    · intro holds
      exact holds terminal .stop
  | choose left right leftIH rightIH =>
    constructor
    · intro holds result path
      cases path with
      | left step => exact leftIH.mp holds.1 result step
      | right step => exact rightIH.mp holds.2 result step
    · intro holds
      exact ⟨leftIH.mpr (fun result path => holds result (.left path)),
        rightIH.mpr (fun result path => holds result (.right path))⟩

def totalPost (post : Observation → Prop) (result : Observation) : Prop :=
  result ≠ .unfinished ∧ post result

def liberalPost (post : Observation → Prop) (result : Observation) : Prop :=
  result ≠ .unfinished → post result

theorem total_iff_liberal_and_complete (post : Observation → Prop) (tree : Unfolding) :
    backwards (totalPost post) tree ↔
      backwards (liberalPost post) tree ∧ ¬ Reaches tree .unfinished := by
  constructor
  · intro total
    have holds := (backwards_iff_all (totalPost post) tree).mp total
    exact ⟨(backwards_iff_all (liberalPost post) tree).mpr
        (fun result path _ => (holds result path).2),
      fun path => (holds .unfinished path).1 rfl⟩
  · intro ⟨liberal, complete⟩
    apply (backwards_iff_all (totalPost post) tree).mpr
    intro result path
    have finished : result ≠ .unfinished := fun equal => complete (equal ▸ path)
    exact ⟨finished, (backwards_iff_all (liberalPost post) tree).mp liberal result path finished⟩

#print axioms backwards_iff_all
#print axioms total_iff_liberal_and_complete
