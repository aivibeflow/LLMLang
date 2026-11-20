import unittest

from scheduler_fairness_model import (
    Action,
    State,
    replay_cycle,
    round_robin_first_b,
    strong_fair_cycle,
    weak_fair_cycle,
)


class SchedulerFairnessTests(unittest.TestCase):
    def test_continuously_enabled_task_starvation_violates_weak_and_strong(self):
        states = replay_cycle(State(True), (Action.RUN_A,), intermittent=False)
        self.assertFalse(weak_fair_cycle(states))
        self.assertFalse(strong_fair_cycle(states))

    def test_intermittently_enabled_starvation_satisfies_weak_not_strong(self):
        actions = (Action.ENABLE_B, Action.RUN_A, Action.DISABLE_B)
        states = replay_cycle(State(False), actions, intermittent=True)
        self.assertTrue(weak_fair_cycle(states))
        self.assertFalse(strong_fair_cycle(states))

    def test_starvation_cycles_never_schedule_b(self):
        continuous = replay_cycle(State(True), (Action.RUN_A,), intermittent=False)
        intermittent = replay_cycle(
            State(False),
            (Action.ENABLE_B, Action.RUN_A, Action.DISABLE_B),
            intermittent=True,
        )
        self.assertEqual(continuous[0].b_runs, 0)
        self.assertTrue(all(state.b_runs == 0 for state in intermittent))

    def test_round_robin_bound_for_two_always_runnable_tasks(self):
        self.assertEqual(round_robin_first_b("B"), 0)
        self.assertEqual(round_robin_first_b("A"), 1)

    def test_rejects_noncycle_and_illegal_transition(self):
        with self.assertRaises(ValueError):
            replay_cycle(State(False), (Action.ENABLE_B,), intermittent=True)
        with self.assertRaises(ValueError):
            replay_cycle(State(False), (Action.RUN_B,), intermittent=True)


if __name__ == "__main__":
    unittest.main()
