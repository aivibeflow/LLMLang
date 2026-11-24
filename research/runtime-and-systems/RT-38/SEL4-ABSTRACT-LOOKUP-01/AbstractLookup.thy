theory AbstractLookup
  imports "AInvs.Syscall_AI"
begin

definition candidate_lookup ::
  "obj_ref \<Rightarrow> cap_ref \<Rightarrow> (cap \<times> cslot_ptr, 'z::state_ext) lf_monad"
where
  "candidate_lookup thread pointer \<equiv> doE
     (slot, _) \<leftarrow> lookup_slot_for_thread thread pointer;
     capability \<leftarrow> liftE $ get_cap slot;
     returnOk (capability, slot)
   odE"

lemma candidate_lookup_eq:
  "candidate_lookup thread pointer = lookup_cap_and_slot thread pointer"
  by (simp add: candidate_lookup_def lookup_cap_and_slot_def)

lemma candidate_lookup_valid_cap:
  "\<lbrace>invs\<rbrace> candidate_lookup t xs \<lbrace>\<lambda>x s. s \<turnstile> fst x\<rbrace>, -"
  unfolding candidate_lookup_eq
  by (rule lcs_valid)

lemma candidate_lookup_existing_slot:
  "\<lbrace>valid_objs\<rbrace> candidate_lookup t xs \<lbrace>\<lambda>rv. cte_at (snd rv)\<rbrace>, -"
  unfolding candidate_lookup_eq
  by (rule lcs_cte_at)

lemma candidate_lookup_valid_fault:
  "\<lbrace>valid_objs\<rbrace> candidate_lookup thread cptr
   \<lbrace>\<lambda>_. valid_objs\<rbrace>,
   \<lbrace>\<lambda>ft s. valid_fault (ExceptionTypes_A.CapFault (of_bl cptr) rp ft)\<rbrace>"
  unfolding candidate_lookup_eq
  by (rule lookup_cap_and_slot_valid_fault)

end
