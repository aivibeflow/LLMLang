theory RefinedLookup
  imports "Refine.Ipc_R" "LLMLang_AbstractLookup.AbstractLookup" "LLMLang_Lookup.Lookup"
begin

text \<open>Transfer the upstream relation to the checked wrappers with the same guards.\<close>

lemma exported_lookup_corresponds:
  assumes "cptr = to_bl cptr'"
  shows
    "corres (lfr \<oplus> (\<lambda>a b. cap_relation (fst a) (fst b) \<and> snd b = cte_map (snd a)))
      (valid_objs and pspace_aligned and tcb_at thread)
      (valid_objs' and pspace_distinct' and pspace_aligned' and tcb_at' thread)
      (candidate_lookup thread cptr) (llmlang_lookup thread cptr')"
  unfolding candidate_lookup_eq lookup_matches_original
  by (rule lookupCapAndSlot_corres[OF assms])

lemma refactored_lookup_corresponds:
  assumes "cptr = to_bl cptr'"
  shows
    "corres (lfr \<oplus> (\<lambda>a b. cap_relation (fst a) (fst b) \<and> snd b = cte_map (snd a)))
      (valid_objs and pspace_aligned and tcb_at thread)
      (valid_objs' and pspace_distinct' and pspace_aligned' and tcb_at' thread)
      (candidate_lookup thread cptr) (llmlang_lookup_refactored thread cptr')"
  unfolding candidate_lookup_eq refactor_matches_original
  by (rule lookupCapAndSlot_corres[OF assms])

end
