from itertools import combinations, permutations
import unittest

from rt03_actor_model import Action, ActorModel, Delivered, Failed, Message, Observation, Producer


class ActorModelExperiment(unittest.TestCase):
    def test_fifo_contains_every_interleaving_of_the_two_workload_producers(self):
        for take_extra in (False, True):
            for start in range(-3, 4):
                with self.subTest(take_extra=take_extra, start=start):
                    script = (Message("add", start),) + (Message("add", 1),) * (1 + take_extra)
                    producers = {"right": Producer(script), "left": Producer(script)}
                    model = ActorModel(producers)
                    outcomes = model.explore()

                    # Independent shuffle oracle: choose the positions of one sender's messages.
                    expected = set()
                    for left_positions in combinations(range(2 * len(script)), len(script)):
                        events = []
                        value = 0
                        left = iter(script)
                        right = iter(script)
                        for index in range(2 * len(script)):
                            sender, message = ("left", next(left)) if index in left_positions else ("right", next(right))
                            value += message.value
                            events.append(Delivered(sender, message, value))
                        expected.add(Observation("returned", 2 * (start + 1 + take_extra), tuple(events)))
                    self.assertEqual(set(outcomes), expected)
                    self.assertEqual(len(outcomes), 20 if take_extra else 6)
                    for observation, witness in outcomes.items():
                        self.assertEqual(model.replay(witness), observation)

                    batch = ActorModel(producers, delivery="sorted-batch")
                    outcomes = batch.explore()
                    self.assertEqual(len(outcomes), 1)
                    observation, witness = next(iter(outcomes.items()))
                    self.assertEqual(observation.result, 2 * (start + 1 + take_extra))
                    self.assertEqual(tuple(event.sender for event in observation.events),
                                     ("left",) * len(script) + ("right",) * len(script))
                    self.assertEqual(batch.replay(witness), observation)

    def test_noncommuting_updates_and_sender_renaming_distinguish_ordering_policies(self):
        update = Producer((Message("set", 1), Message("add", 1)))
        reset = Producer((Message("set", 9),))
        for first_name, batch_result in (("a", 9), ("z", 2)):
            producers = {first_name: update, "b": reset}
            self.assertEqual({outcome.result for outcome in ActorModel(producers).explore()}, {2, 9, 10})
            batch = ActorModel(producers, delivery="sorted-batch")
            self.assertEqual({outcome.result for outcome in batch.explore()}, {batch_result})
            explicit = ActorModel(producers, delivery="sorted-batch", batch_order=(first_name, "b"))
            self.assertEqual({outcome.result for outcome in explicit.explore()}, {9})
        for order in (("a",), ("a", "a"), ("a", "unknown")):
            with self.subTest(order=order), self.assertRaisesRegex(ValueError, "must list each producer once"):
                ActorModel({"a": update, "b": reset}, delivery="sorted-batch", batch_order=order)

    def test_isolation_keeps_sent_work_and_abort_keeps_only_the_observed_prefix(self):
        producers = {
            "a": Producer((Message("add", 1),), fails=True),
            "b": Producer((Message("add", 2),)),
        }
        for policy in ("isolate", "abort"):
            model = ActorModel(producers, failure=policy)
            expected = set()
            for order in permutations(("a", "b", "failure")):
                events = []
                value = 0
                for item in order:
                    if item == "failure":
                        events.append(Failed("a"))
                        if policy == "abort":
                            break
                    else:
                        message = producers[item].messages[0]
                        value += message.value
                        events.append(Delivered(item, message, value))
                if policy == "isolate":
                    expected.add(Observation("returned", 3, tuple(events)))
                else:
                    expected.add(Observation("aborted", None, tuple(events)))
            observed = model.explore()
            self.assertEqual(set(observed), expected)
            self.assertEqual(len(observed), 6 if policy == "isolate" else 5)
            for observation, witness in observed.items():
                self.assertEqual(model.replay(witness), observation)

    def test_batch_makes_the_failure_boundary_precede_all_deliveries(self):
        producers = {
            "a": Producer((Message("add", 1),), fails=True),
            "b": Producer((Message("add", 2),)),
        }
        isolated = ActorModel(producers, delivery="sorted-batch", failure="isolate")
        self.assertEqual(set(isolated.explore()), {Observation("returned", 3, (
            Failed("a"), Delivered("a", Message("add", 1), 1), Delivered("b", Message("add", 2), 3),
        ))})
        aborted = ActorModel(producers, delivery="sorted-batch", failure="abort")
        self.assertEqual(set(aborted.explore()), {Observation("aborted", None, (Failed("a"),))})

    def test_replay_rejects_unsent_delivery_incomplete_and_post_abort_schedules(self):
        model = ActorModel({"a": Producer((Message("add", 1),), fails=True)}, failure="abort")
        with self.assertRaisesRegex(ValueError, "step 0 is not enabled"):
            model.replay((Action("deliver", "a"),))
        with self.assertRaisesRegex(ValueError, "incomplete schedule"):
            model.replay((Action("send", "a"),))
        with self.assertRaisesRegex(ValueError, "step 2 is not enabled"):
            model.replay((Action("send", "a"), Action("fail", "a"), Action("deliver", "a")))


if __name__ == "__main__":
    unittest.main()
