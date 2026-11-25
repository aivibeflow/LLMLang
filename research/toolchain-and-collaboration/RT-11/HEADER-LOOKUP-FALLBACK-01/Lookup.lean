def firstPresent : List (Option α) → Option α
  | [] => none
  | candidate :: remaining => candidate.orElse fun _ => firstPresent remaining

theorem same_prefix_and_winner (earlier : Nat) (value : α) (later : List (Option α)) :
    firstPresent (List.replicate earlier none ++ some value :: later) = some value := by
  induction earlier with
  | zero => rfl
  | succ n induction =>
    simpa only [List.replicate_succ, List.cons_append, firstPresent, Option.orElse] using induction

theorem later_candidate_cannot_change_winner (earlier : Nat) (value : α)
    (old new : List (Option α)) :
    firstPresent (List.replicate earlier none ++ some value :: old) =
      firstPresent (List.replicate earlier none ++ some value :: new) :=
  (same_prefix_and_winner earlier value old).trans (same_prefix_and_winner earlier value new).symm

theorem positive_file_alone_does_not_bind_resolution :
    firstPresent [none, some false] ≠ firstPresent [some true, some false] := by decide

#print axioms same_prefix_and_winner
#print axioms later_candidate_cannot_change_winner
#print axioms positive_file_alone_does_not_bind_resolution
