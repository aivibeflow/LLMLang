theorem exact_prefix_resume (bytes : List UInt8) (progress : Nat) :
    bytes.take progress ++ bytes.drop progress = bytes :=
  List.take_append_drop progress bytes

theorem full_reissue_length (bytes : List UInt8) (progress : Nat)
    (positive : 0 < progress) (valid : progress ≤ bytes.length) :
    bytes.length < (bytes.take progress ++ bytes).length := by
  simp [List.length_take, Nat.min_eq_left valid]
  omega

#print axioms exact_prefix_resume
#print axioms full_reissue_length
