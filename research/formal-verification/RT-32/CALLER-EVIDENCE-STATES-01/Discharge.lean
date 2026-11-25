inductive Disposition where
  | checked | pending | unknown | unsupported | rejected | refuted
  deriving DecidableEq

structure Key where
  subject : Nat
  contract : Nat
  version : Nat
  imports : Nat

structure Evidence where
  key : Key
  disposition : Disposition

def Discharged (expected : Key) (actual : Evidence) : Prop :=
  actual.key = expected ∧ actual.disposition = .checked

theorem changed_version_refuses_old_evidence (expected : Key) (actual : Evidence)
    (changed : expected.version ≠ actual.key.version) :
    ¬ Discharged expected actual := by
  intro accepted
  exact changed (congrArg Key.version accepted.1).symm

theorem missing_import_correspondence_refuses (expected : Key) (actual : Evidence)
    (changed : expected.imports ≠ actual.key.imports) :
    ¬ Discharged expected actual := by
  intro accepted
  exact changed (congrArg Key.imports accepted.1).symm

theorem one_way_composition (providerContract callerContract : α → Prop) (provider : α)
    (conditional : ∀ implementation, providerContract implementation →
      callerContract implementation)
    (certificate : providerContract provider) : callerContract provider :=
  conditional provider certificate

theorem unknown_cannot_discharge (expected : Key) (actual : Evidence)
    (unknown : actual.disposition = .unknown) : ¬ Discharged expected actual := by
  intro accepted
  have impossible : Disposition.unknown = .checked := unknown.symm.trans accepted.2
  cases impossible

#print axioms changed_version_refuses_old_evidence
#print axioms missing_import_correspondence_refuses
#print axioms one_way_composition
#print axioms unknown_cannot_discharge
