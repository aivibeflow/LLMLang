import unittest

from rt03_actor_model import ActorModel, Message, Producer
from rt03_typed_calls import (
    Execution,
    FragmentError,
    Function,
    RejectedWrite,
    StateWrite,
    project_program,
    run_program,
)
from rt04_model import check_program


def increment():
    return Function((("n", "Int"),), "Int", {"add": [{"var": "n"}, {"literal": 1}]})

def handle_state(initializer, body, *, observe_writes=False, reject_negative=False):
    return {"handle_state": [initializer, observe_writes, reject_negative, body]}


class TypedCallsExperiment(unittest.TestCase):
    def test_four_profiles_agree_on_scalar_result_for_the_same_workload(self):
        # A conditional update followed by an unconditional update, called twice.
        params = (("take_extra", "Bool"), ("start", "Int"))
        step = {"call": ["increment", [{"var": "total"}]]}
        first = {"if": [{"var": "take_extra"}, step, {"var": "total"}]}
        functional = {"let": ["total", {"var": "start"}, {"let": ["total", first, step]}]}
        imperative = {"local": ["total", {"var": "start"}, {
            "sequence": [{"set": ["total", first]}, {"set": ["total", step]}, {"var": "total"}],
        }]}
        get = {"state_get": None}
        handled_step = {"call": ["increment", [get]]}
        handled = handle_state({"var": "start"}, {"sequence": [
            {"state_put": {"if": [{"var": "take_extra"}, handled_step, get]}},
            {"state_put": handled_step},
            get,
        ]})
        attempt = {"call": ["adjust", [{"var": "take_extra"}, {"var": "start"}]]}
        entry = Function(params, "Int", {"add": [attempt, attempt]})

        def program(body):
            return {"entry": entry, "adjust": Function(params, "Int", body), "increment": increment()}

        for take_extra in (False, True):
            called_by_adjust = ("adjust",) + ("increment",) * (1 + take_extra)
            for start in range(-3, 4):
                with self.subTest(take_extra=take_extra, start=start):
                    expected = Execution(2 * (start + 1 + take_extra), ("entry",) + called_by_adjust * 2)
                    self.assertEqual(run_program(program(functional), "entry", (take_extra, start),
                                                 "A", checker="A"), expected)
                    self.assertEqual(run_program(program(imperative), "entry", (take_extra, start),
                                                 "B", checker="B"), expected)
                    self.assertEqual(run_program(program(handled), "entry", (take_extra, start),
                                                 "D", checker="B"), expected)
                    messages = (Message("add", start),) + (Message("add", 1),) * (1 + take_extra)
                    concurrent = ActorModel({"left": Producer(messages), "right": Producer(messages)})
                    self.assertEqual({outcome.result for outcome in concurrent.explore()}, {expected.result})
        with self.assertRaisesRegex(FragmentError, "unsupported.*local"):
            run_program(program(imperative), "entry", (True, 0), "A", checker="B")
        # The RT-04 declaration checker vector and the RT-03 semantics are independent axes.
        self.assertEqual(run_program(program(imperative), "entry", (True, 0), "B", checker="A").result, 4)

    def test_call_sites_include_both_branches_before_any_execution(self):
        program = {
            "entry": Function((), "Int", {"if": [
                {"literal": True}, {"literal": 4},
                {"call": ["increment", [{"literal": False}]]},
            ]}),
            "increment": increment(),
        }
        projected = project_program(program, "A")
        self.assertEqual(projected["functions"]["entry"]["call_sites"],
                         [{"target": "increment", "args": ["Bool"]}])
        for checker in ("A", "B"):
            self.assertEqual(check_program(projected, checker).codes(), {"CALL_ARGUMENT_TYPE_MISMATCH"})
            with self.assertRaisesRegex(FragmentError, "RT-04 REJECTED: CALL_ARGUMENT_TYPE_MISMATCH"):
                run_program(program, "entry", (), "A", checker=checker)

    def test_actual_values_and_call_order_follow_parameter_order(self):
        program = {
            "entry": Function((), "Int", {"call": ["select", [
                {"call": ["flag", []]}, {"call": ["number", []]},
            ]]}),
            "select": Function((("flag", "Bool"), ("value", "Int")), "Int",
                               {"if": [{"var": "flag"}, {"var": "value"}, {"literal": 0}]}),
            "flag": Function((), "Bool", {"literal": True}),
            "number": Function((), "Int", {"literal": 6}),
        }
        expected = Execution(6, ("entry", "flag", "number", "select"))
        for semantics in ("A", "B"):
            self.assertEqual(run_program(program, "entry", (), semantics, checker="B"), expected)

    def test_inner_cell_and_callee_cannot_modify_the_same_named_outer_cell(self):
        inner = {"local": ["n", {"literal": 0}, {"set": ["n", {"literal": 99}]}]}
        program = {
            "entry": Function((), "Int", {"local": ["n", {"literal": 5}, {"sequence": [
                inner, {"call": ["update", [{"var": "n"}]]}, {"var": "n"},
            ]}]}),
            "update": Function((("n", "Int"),), "Unit", inner),
        }
        self.assertEqual(run_program(program, "entry", (), "B", checker="B"),
                         Execution(5, ("entry", "update")))

    def test_update_order_matters_even_when_the_call_graph_is_identical(self):
        reset = {"set": ["n", {"literal": 1}]}
        bump = {"set": ["n", {"call": ["increment", [{"var": "n"}]]}]}

        def program(first, second):
            body = {"local": ["n", {"literal": 0}, {"sequence": [first, second, {"var": "n"}]}]}
            return {"entry": Function((), "Int", body), "increment": increment()}

        ordered = program(reset, bump)
        reordered = program(bump, reset)
        self.assertEqual(project_program(ordered, "B"), project_program(reordered, "B"))
        self.assertEqual(run_program(ordered, "entry", (), "B", checker="B"),
                         Execution(2, ("entry", "increment")))
        self.assertEqual(run_program(reordered, "entry", (), "B", checker="B"),
                         Execution(1, ("entry", "increment")))

    def test_write_requires_mutability_and_the_declared_local_type(self):
        cases = (
            ({"let": ["n", {"literal": 1}, {"set": ["n", {"literal": 2}]}]}, "requires a mutable local"),
            ({"local": ["n", {"literal": 1}, {"set": ["n", {"literal": False}]}]}, "expected Int, got Bool"),
            ({"set": ["n", {"literal": 2}]}, "requires a mutable local"),
        )
        for body, message in cases:
            with self.subTest(body=body), self.assertRaisesRegex(FragmentError, message):
                run_program({"entry": Function((("n", "Int"),), "Unit", body)}, "entry", (1,), "B", checker="B")

    def test_invalid_input_and_recursive_calls_do_not_reach_execution(self):
        for args, message in (((), "entry argument count"), ((True,), "expected Int, got Bool")):
            with self.subTest(args=args), self.assertRaisesRegex(FragmentError, message):
                run_program({"entry": increment()}, "entry", args, "A", checker="A")
        cyclic = {
            "entry": Function((), "Int", {"call": ["other", []]}),
            "other": Function((), "Int", {"call": ["entry", []]}),
        }
        with self.assertRaisesRegex(FragmentError, "recursive calls"):
            run_program(cyclic, "entry", (), "B", checker="B")


class HandledStateExperiment(unittest.TestCase):
    def test_scoped_interpretations_of_one_callee_have_same_value_but_distinct_writes(self):
        callee = Function((), "Int", {"sequence": [
            {"state_put": {"add": [{"state_get": None}, {"literal": 1}]}},
            {"state_get": None},
        ]}, requires_state=True)
        call = {"call": ["step", []]}

        def program(observe_writes):
            root = handle_state({"literal": 2}, {"add": [call, call]}, observe_writes=observe_writes)
            return {"entry": Function((), "Int", root), "step": callee}

        self.assertEqual(project_program(program(False), "D"), project_program(program(True), "D"))
        for observe_writes in (False, True):
            writes = (StateWrite(2, 3, True), StateWrite(3, 4, True)) if observe_writes else ()
            with self.subTest(observe_writes=observe_writes):
                self.assertEqual(run_program(program(observe_writes), "entry", (), "D", checker="A"),
                                 Execution(7, ("entry", "step", "step"), writes))

    def test_nested_handler_reads_initializer_from_outer_then_restores_outer_scope(self):
        state = {"state_get": None}
        inner = handle_state(state, {"sequence": [
            {"state_put": {"add": [state, {"literal": 1}]}}, state,
        ]}, observe_writes=True)
        outer = handle_state({"literal": 2}, {"add": [inner, state]}, observe_writes=True)
        functions = {"entry": Function((), "Int", outer)}
        self.assertEqual(run_program(functions, "entry", (), "D", checker="B"),
                         Execution(5, ("entry",), (StateWrite(2, 3, True),)))

    def test_handler_requirement_is_checked_at_call_and_program_entry(self):
        step = Function((), "Int", {"state_get": None}, requires_state=True)
        # The call site is present even when its branch will never execute.
        branch = {"if": [{"literal": False}, {"call": ["read", []]}, {"literal": 4}]}
        functions = {"entry": Function((), "Int", branch), "read": step}
        with self.assertRaisesRegex(FragmentError, "call to 'read' requires state"):
            run_program(functions, "entry", (), "D", checker="B")
        with self.assertRaisesRegex(FragmentError, "entry requires a state handler"):
            run_program({"read": step}, "read", (), "D", checker="B")
        with self.assertRaisesRegex(FragmentError, "operation requires state"):
            run_program({"entry": Function((), "Int", {"state_get": None})},
                        "entry", (), "D", checker="B")
        with self.assertRaisesRegex(FragmentError, "operation requires state"):
            root = handle_state({"state_get": None}, {"literal": 4})
            run_program({"entry": Function((), "Int", root)}, "entry", (), "D", checker="B")

    def test_rejected_write_is_terminal_and_keeps_earlier_observed_writes(self):
        put = Function((("value", "Int"),), "Unit", {"state_put": {"var": "value"}}, requires_state=True)
        body = {"sequence": [
            {"call": ["put", [{"literal": 3}]]},
            {"call": ["put", [{"literal": -1}]]},
            {"call": ["put", [{"literal": 9}]]},
            {"state_get": None},
        ]}
        for observable in (False, True):
            with self.subTest(observable=observable):
                entry = handle_state({"literal": 0}, body,
                                     observe_writes=observable, reject_negative=True)
                writes = (StateWrite(0, 3, True), StateWrite(3, -1, False)) if observable else ()
                self.assertEqual(
                    run_program({"entry": Function((), "Int", entry), "put": put},
                                "entry", (), "D", checker="B"),
                    Execution(None, ("entry", "put", "put"), writes, RejectedWrite(-1)),
                )
        entry = handle_state({"literal": 0}, body, observe_writes=True)
        self.assertEqual(
            run_program({"entry": Function((), "Int", entry), "put": put},
                        "entry", (), "D", checker="B"),
            Execution(9, ("entry", "put", "put", "put"),
                      (StateWrite(0, 3, True), StateWrite(3, -1, True), StateWrite(-1, 9, True))),
        )

    def test_state_initializer_and_put_must_be_int_and_handler_is_specific_to_d(self):
        invalid = (
            (handle_state({"literal": False}, {"literal": None}), "state initializer"),
            (handle_state({"literal": 0}, {"state_put": {"literal": False}}), "state write"),
        )
        for body, operation in invalid:
            with self.subTest(operation=operation), self.assertRaisesRegex(
                FragmentError, f"{operation}: expected Int, got Bool"
            ):
                run_program({"entry": Function((), "Unit", body)}, "entry", (), "D", checker="B")
        handled = handle_state({"literal": 0}, {"state_get": None})
        for semantics in ("A", "B"):
            with self.subTest(semantics=semantics), self.assertRaisesRegex(FragmentError, "unsupported.*handle_state"):
                run_program({"entry": Function((), "Int", handled)}, "entry", (), semantics, checker="B")


if __name__ == "__main__":
    unittest.main()
