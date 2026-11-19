"""Finite Profile C experiment with scripted senders and one stateful receiver."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal


@dataclass(frozen=True)
class Message:
    operation: Literal["add", "set"]
    value: int


@dataclass(frozen=True)
class Producer:
    messages: tuple[Message, ...]
    fails: bool = False


@dataclass(frozen=True)
class Action:
    kind: Literal["send", "deliver", "fail"]
    sender: str


@dataclass(frozen=True)
class Delivered:
    sender: str
    message: Message
    after: int


@dataclass(frozen=True)
class Failed:
    sender: str


@dataclass(frozen=True)
class Observation:
    outcome: Literal["returned", "aborted"]
    result: int | None
    events: tuple[Delivered | Failed, ...]


@dataclass(frozen=True)
class _State:
    sent: tuple[int, ...]
    received: tuple[int, ...]
    value: int
    events: tuple[Delivered | Failed, ...] = ()
    aborted: bool = False


def _advance(cursors: tuple[int, ...], index: int) -> tuple[int, ...]:
    return cursors[:index] + (cursors[index] + 1,) + cursors[index + 1:]


class ActorModel:
    """Explore all enabled schedules of a finite, closed producer group."""

    def __init__(
        self,
        producers: dict[str, Producer],
        *,
        initial: int = 0,
        delivery: Literal["channel-fifo", "sorted-batch"] = "channel-fifo",
        failure: Literal["isolate", "abort"] = "isolate",
        batch_order: tuple[str, ...] | None = None,
    ):
        if delivery not in ("channel-fifo", "sorted-batch") or failure not in ("isolate", "abort"):
            raise ValueError("unsupported delivery or failure policy")
        if type(initial) is not int:
            raise ValueError("receiver must start with Int state")
        for name, producer in producers.items():
            if not isinstance(name, str) or not name or not isinstance(producer, Producer):
                raise ValueError("each producer requires a nonempty name and a script")
            if not isinstance(producer.messages, tuple) or type(producer.fails) is not bool:
                raise ValueError("a script requires a message tuple and a boolean failure flag")
            for message in producer.messages:
                if (not isinstance(message, Message) or message.operation not in ("add", "set")
                        or type(message.value) is not int):
                    raise ValueError("the receiver supports only add and set messages with Int payloads")

        if batch_order is not None and (
            delivery != "sorted-batch"
            or len(batch_order) != len(producers)
            or set(batch_order) != set(producers)
        ):
            raise ValueError("batch_order must list each producer once for sorted-batch delivery")
        order = sorted(producers) if batch_order is None else batch_order
        self._producers = tuple((name, producers[name]) for name in order)
        self._delivery = delivery
        self._failure = failure
        zeros = (0,) * len(producers)
        self._initial = _State(zeros, zeros, initial)

    def _enabled(self, state: _State) -> tuple[tuple[int, Action], ...]:
        if state.aborted:
            return ()
        source_actions = []
        deliveries = []
        for index, (sender, producer) in enumerate(self._producers):
            sent = state.sent[index]
            length = len(producer.messages)
            if sent < length:
                source_actions.append((index, Action("send", sender)))
            elif sent == length and producer.fails:
                source_actions.append((index, Action("fail", sender)))
            # A failure consumes one source step without creating a message.
            if state.received[index] < min(sent, length):
                deliveries.append((index, Action("deliver", sender)))

        if self._delivery == "sorted-batch":
            return tuple(source_actions if source_actions else deliveries[:1])
        return tuple(source_actions + deliveries)

    def _step(self, state: _State, index: int, action: Action) -> _State:
        if action.kind == "send":
            return replace(state, sent=_advance(state.sent, index))
        if action.kind == "fail":
            return replace(
                state,
                sent=_advance(state.sent, index),
                events=state.events + (Failed(action.sender),),
                aborted=self._failure == "abort",
            )
        producer = self._producers[index][1]
        message = producer.messages[state.received[index]]
        value = state.value + message.value if message.operation == "add" else message.value
        return replace(
            state,
            received=_advance(state.received, index),
            value=value,
            events=state.events + (Delivered(action.sender, message, value),),
        )

    def _observe(self, state: _State) -> Observation:
        if state.aborted:
            return Observation("aborted", None, state.events)
        return Observation("returned", state.value, state.events)

    def explore(self) -> dict[Observation, tuple[Action, ...]]:
        """Return every exact observation and one replayable witness per observation."""
        pending: list[tuple[_State, tuple[Action, ...]]] = [(self._initial, ())]
        seen = {self._initial}
        outcomes: dict[Observation, tuple[Action, ...]] = {}
        while pending:
            state, schedule = pending.pop()
            enabled = self._enabled(state)
            if not enabled:
                outcomes.setdefault(self._observe(state), schedule)
                continue
            for index, action in enabled:
                successor = self._step(state, index, action)
                if successor not in seen:
                    seen.add(successor)
                    pending.append((successor, schedule + (action,)))
        return outcomes

    def replay(self, schedule: tuple[Action, ...]) -> Observation:
        """Use an explicit schedule. Reject disabled steps and incomplete witnesses."""
        state = self._initial
        for position, action in enumerate(schedule):
            enabled = {step: index for index, step in self._enabled(state)}
            if action not in enabled:
                raise ValueError(f"step {position} is not enabled: {action}")
            state = self._step(state, enabled[action], action)
        if self._enabled(state):
            raise ValueError("incomplete schedule")
        return self._observe(state)
