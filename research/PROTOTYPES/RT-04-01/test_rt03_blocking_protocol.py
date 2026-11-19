import unittest

from rt03_blocking_protocol import Action, BlockingProtocol, Outcome


SEND_RECEIVE = ("send", "receive")
RECEIVE_SEND = ("receive", "send")


class BlockingProtocolExperiment(unittest.TestCase):
    def test_mutual_send_blocks_under_rendezvous_but_completes_buffered(self):
        rendezvous = BlockingProtocol(SEND_RECEIVE, SEND_RECEIVE, mode="rendezvous")
        outcomes = rendezvous.explore()
        self.assertEqual(len(outcomes), 1)
        blocked, witness = next(iter(outcomes.items()))
        self.assertEqual(blocked.status, "blocked")
        self.assertEqual(witness, ())
        self.assertEqual(blocked.terminal_state.a_pc, 0)
        self.assertEqual(blocked.terminal_state.b_pc, 0)
        self.assertEqual(rendezvous.replay(witness), blocked)

        buffered = BlockingProtocol(SEND_RECEIVE, SEND_RECEIVE, mode="buffered")
        outcomes = buffered.explore()
        self.assertEqual({outcome.status for outcome in outcomes}, {"completed"})
        # Two send orders, then two receive orders: four legal complete traces.
        self.assertEqual(len(outcomes), 4)
        for outcome, witness in outcomes.items():
            self.assertEqual(buffered.replay(witness), outcome)

    def test_crossed_request_reply_completes_under_rendezvous(self):
        model = BlockingProtocol(SEND_RECEIVE, RECEIVE_SEND, mode="rendezvous")
        outcomes = model.explore()
        self.assertEqual(len(outcomes), 1)
        outcome, witness = next(iter(outcomes.items()))
        self.assertEqual(outcome.status, "completed")
        self.assertEqual(witness, (
            Action("a", "send"),
            Action("b", "send"),
        ))
        self.assertEqual(model.replay(witness), outcome)

    def test_replay_rejects_disabled_or_incomplete_traces(self):
        model = BlockingProtocol(SEND_RECEIVE, SEND_RECEIVE, mode="rendezvous")
        with self.assertRaisesRegex(ValueError, "not enabled"):
            model.replay((Action("a", "send"),))
        buffered = BlockingProtocol(SEND_RECEIVE, SEND_RECEIVE, mode="buffered")
        with self.assertRaisesRegex(ValueError, "incomplete trace"):
            buffered.replay((Action("a", "send"),))


if __name__ == "__main__":
    unittest.main()
