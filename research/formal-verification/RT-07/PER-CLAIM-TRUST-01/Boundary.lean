namespace TrustBoundary

def observedInput : Nat := 9
abbrev Claim : Prop := observedInput * 7 = 63

axiom inputIsNine : observedInput = 9
axiom unrelatedAgreement : True

theorem underInputAssumption (input : Nat) (agreement : input = 9) : input * 7 = 63 := by
  cases agreement
  rfl

end TrustBoundary
