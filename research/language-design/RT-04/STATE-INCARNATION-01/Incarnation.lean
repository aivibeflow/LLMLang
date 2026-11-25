namespace StateIncarnation

inductive Phase
  | retired
  | live
  deriving DecidableEq

structure Handle (phase : Phase) where
  incarnation : Nat

def checkedUse (saved current : Handle .live) : Prop :=
  saved.incarnation = current.incarnation

def wrappedUse (period : Nat) (saved current : Handle .live) : Prop :=
  saved.incarnation % period = current.incarnation % period

theorem sameIsAdmitted (saved : Handle .live) : checkedUse saved saved := rfl

theorem exactRejectsLater (saved : Handle .live) (advance : Nat) (positive : 0 < advance) :
    ¬ checkedUse saved ⟨saved.incarnation + advance⟩ := by
  unfold checkedUse
  change ¬ saved.incarnation = saved.incarnation + advance
  omega

theorem wrappedAdmitsLater (saved : Handle .live) (period : Nat) :
    wrappedUse period saved ⟨saved.incarnation + period⟩ := by
  unfold wrappedUse
  exact (Nat.add_mod_right saved.incarnation period).symm

theorem onePeriodIsStrictlyLater (saved : Handle .live) (period : Nat) (positive : 0 < period) :
    saved.incarnation < saved.incarnation + period := by
  omega

example : True := by
  fail_if_success
    have rejected := checkedUse (⟨0⟩ : Handle .live) (⟨1⟩ : Handle .retired)
  trivial

#print axioms sameIsAdmitted
#print axioms exactRejectsLater
#print axioms wrappedAdmitsLater
#print axioms onePeriodIsStrictlyLater

end StateIncarnation
