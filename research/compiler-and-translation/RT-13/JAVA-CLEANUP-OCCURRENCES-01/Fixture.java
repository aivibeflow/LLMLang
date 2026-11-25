import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.StringJoiner;

public final class Fixture {
    private static final List<String> MODES = List.of("ok", "own", "shared");

    private static final class Failure extends Exception {
        private static final long serialVersionUID = 1L;
        final String tag;

        Failure(String tag) {
            this.tag = tag;
        }
    }

    private static final class Resource implements AutoCloseable {
        final String stage;
        final String mode;
        final Failure shared;
        final List<String> events;

        Resource(String stage, String mode, Failure shared, List<String> events) {
            this.stage = stage;
            this.mode = mode;
            this.shared = shared;
            this.events = events;
        }

        @Override
        public void close() throws Failure {
            events.add(stage);
            trigger(stage, mode, shared);
        }
    }

    private static void trigger(String stage, String mode, Failure shared) throws Failure {
        switch (mode) {
            case "ok" -> { }
            case "own" -> throw new Failure(stage);
            case "shared" -> throw shared;
            default -> throw new AssertionError(mode);
        }
    }

    private static void body(String mode, Failure shared, List<String> events) throws Failure {
        events.add("body");
        trigger("body", mode, shared);
    }

    private static String label(Throwable error) {
        if (error == null)
            return "-";
        if (error instanceof Failure tagged)
            return tagged.tag;
        if (error instanceof IllegalArgumentException && error.getCause() instanceof Failure)
            return "self-suppression";
        throw new AssertionError(error);
    }

    private static String labels(Throwable[] errors) {
        var values = new StringJoiner(",");
        for (Throwable error : errors)
            values.add(label(error));
        return values.toString();
    }

    @SuppressWarnings("try")
    private static String automatic(String body, String inner, String outer) {
        Failure shared = new Failure("shared");
        var events = new ArrayList<String>();
        Throwable primary = null;
        try (Resource one = new Resource("outer", outer, shared, events);
             Resource two = new Resource("inner", inner, shared, events)) {
            body(body, shared, events);
        } catch (Exception failed) {
            primary = failed;
        }
        String suppressed = primary == null ? "" : labels(primary.getSuppressed());
        String cause = primary == null ? "-" : label(primary.getCause());
        return String.join(",", events) + "|" + label(primary) + "|" + suppressed + "|" + cause;
    }

    @FunctionalInterface
    private interface Action {
        void perform() throws Failure;
    }

    private record Occurrence(String stage, String tag) {
        @Override
        public String toString() {
            return stage + ":" + tag;
        }
    }

    private static void capture(String stage, Action action, List<Occurrence> failures) {
        try {
            action.perform();
        } catch (Failure failure) {
            failures.add(new Occurrence(stage, failure.tag));
        }
    }

    private static String explicit(String body, String inner, String outer) {
        Failure shared = new Failure("shared");
        var events = new ArrayList<String>();
        var failures = new ArrayList<Occurrence>();
        var outerResource = new Resource("outer", outer, shared, events);
        var innerResource = new Resource("inner", inner, shared, events);
        capture("body", () -> body(body, shared, events), failures);
        capture("inner", innerResource::close, failures);
        capture("outer", outerResource::close, failures);
        return String.join(",", events) + "|" + String.join(",", failures.stream().map(Occurrence::toString).toList());
    }

    public static void main(String[] args) {
        for (String body : MODES) {
            for (String inner : MODES) {
                for (String outer : MODES) {
                    String scenario = String.join(",", Arrays.asList(body, inner, outer));
                    System.out.println("case=" + scenario + "|" + automatic(body, inner, outer)
                                       + "|" + explicit(body, inner, outer));
                }
            }
        }
    }
}
