theory LookupControls
  imports Main
begin

datatype outcome = Found nat nat | Absent | WrongFault

definition reference :: "nat list \<Rightarrow> nat \<Rightarrow> bool \<Rightarrow> outcome \<times> bool" where
  "reference slots idx state =
     (if idx < length slots then Found (slots ! idx) idx else Absent, state)"

definition candidate :: "nat list \<Rightarrow> nat \<Rightarrow> bool \<Rightarrow> outcome \<times> bool" where
  "candidate slots idx state =
     (let permitted = (idx < length slots);
          value = (if permitted then Found (slots ! idx) idx else Absent)
      in (value, state))"

definition bad_fault :: "nat list \<Rightarrow> nat \<Rightarrow> bool \<Rightarrow> outcome \<times> bool" where
  "bad_fault slots idx state =
     (if idx < length slots then Found (slots ! idx) idx else WrongFault, state)"

definition bad_slot :: "nat list \<Rightarrow> nat \<Rightarrow> bool \<Rightarrow> outcome \<times> bool" where
  "bad_slot slots idx state =
     (if idx < length slots then Found (slots ! idx) (Suc idx) else Absent, state)"

definition bad_state :: "nat list \<Rightarrow> nat \<Rightarrow> bool \<Rightarrow> outcome \<times> bool" where
  "bad_state slots idx state = (fst (reference slots idx state), \<not> state)"

lemma candidate_agrees: "candidate slots idx state = reference slots idx state"
  by (simp add: candidate_def reference_def Let_def)

lemma reachable_fault:
  "bad_fault [] 0 False = (WrongFault, False) \<and> reference [] 0 False = (Absent, False)"
  by (simp add: bad_fault_def reference_def)

lemma reachable_slot:
  "bad_slot [7] 0 False = (Found 7 1, False) \<and> reference [7] 0 False = (Found 7 0, False)"
  by (simp add: bad_slot_def reference_def)

lemma reachable_state:
  "bad_state [7] 0 False = (Found 7 0, True) \<and> reference [7] 0 False = (Found 7 0, False)"
  by (simp add: bad_state_def reference_def)

lemma "bad_fault slots idx state = reference slots idx state"
  quickcheck [tester = exhaustive, size = 4, expect = counterexample]
  oops

lemma "bad_slot slots idx state = reference slots idx state"
  quickcheck [tester = exhaustive, size = 4, expect = counterexample]
  oops

lemma "bad_state slots idx state = reference slots idx state"
  quickcheck [tester = exhaustive, size = 4, expect = counterexample]
  oops

lemma "bad_state slots idx state = reference slots idx state"
  nitpick [timeout = 10, expect = genuine]
  oops

end
