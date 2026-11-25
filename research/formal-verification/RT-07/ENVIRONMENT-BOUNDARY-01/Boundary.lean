namespace EnvironmentBoundary

inductive Input where
  | absent | malformed | offset (value : Nat)

inductive Observation where
  | success (value : Nat) (read : Bool)
  | missing | rejected

def observe (enabled : Bool) (input : Nat) (environment : Input) : Observation :=
  if enabled then
    match environment with
    | .absent => .missing
    | .malformed => .rejected
    | .offset value => .success ((input + value) % 256) true
  else
    .success input false

theorem disabledIsIndependent (input : Nat) (old new : Input) :
    observe false input old = observe false input new := rfl

theorem enabledValidObservation (input value : Nat) :
    observe true input (.offset value) = .success ((input + value) % 256) true := rfl

theorem absenceAndMalformationDiffer (input : Nat) :
    observe true input .absent ≠ observe true input .malformed :=
  fun equality => Observation.noConfusion equality

theorem conditionalValidCaseDoesNotCoverAbsence (input : Nat) :
    observe true input (.offset 0) ≠ observe true input .absent :=
  fun equality => Observation.noConfusion equality

#print axioms disabledIsIndependent
#print axioms enabledValidObservation
#print axioms absenceAndMalformationDiffer
#print axioms conditionalValidCaseDoesNotCoverAbsence

end EnvironmentBoundary
