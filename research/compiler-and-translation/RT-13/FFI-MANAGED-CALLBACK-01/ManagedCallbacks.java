import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.SymbolLookup;
import java.lang.invoke.MethodHandle;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.nio.file.Path;

import static java.lang.foreign.ValueLayout.ADDRESS;
import static java.lang.foreign.ValueLayout.JAVA_INT;
import static java.lang.foreign.ValueLayout.JAVA_LONG;

public final class ManagedCallbacks {
    private static final Linker LINKER = Linker.nativeLinker();
    private static volatile MethodHandle thread;
    private static volatile MethodHandle retire;
    private static volatile MethodHandle finish;
    private static volatile long owner;
    private static volatile boolean uncaught;

    private static final class FixtureFailure extends RuntimeException {}

    private static int callback(MemorySegment session, long ticket, int value, MemorySegment context) {
        if (uncaught && value == -7) {
            throw new FixtureFailure();
        }
        try (Arena scratch = Arena.ofConfined()) {
            MemorySegment kind = scratch.allocate(JAVA_INT);
            MemorySegment ignored = scratch.allocate(JAVA_INT);
            if ((int) thread.invokeExact(session, ticket, kind) != 0 ||
                (int) retire.invokeExact(session, ticket) != 2 ||
                (int) finish.invokeExact(session, ticket, ignored) != 2) {
                return -88;
            }
            int nativeClass = kind.get(JAVA_INT, 0);
            int expected = Thread.currentThread().threadId() == owner ? 1 : 2;
            if (nativeClass != expected) {
                return -88;
            }
            if (value == -7) {
                throw new FixtureFailure();
            }
            int offset = context.reinterpret(JAVA_INT.byteSize()).get(JAVA_INT, 0);
            return nativeClass * 1000 + value * 3 + offset;
        } catch (FixtureFailure expected) {
            return -77;
        } catch (Throwable unexpected) {
            return -88;
        }
    }

    private static MethodHandle handle(SymbolLookup lookup, String name, FunctionDescriptor signature) {
        return LINKER.downcallHandle(lookup.find(name).orElseThrow(), signature);
    }

    public static void main(String[] arguments) throws Throwable {
        owner = Thread.currentThread().threadId();
        uncaught = Boolean.parseBoolean(arguments[1]);
        try (Arena lifetime = Arena.ofShared()) {
            SymbolLookup lookup = SymbolLookup.libraryLookup(Path.of(arguments[0]), lifetime);
            FunctionDescriptor scopedResult = FunctionDescriptor.of(JAVA_INT, ADDRESS, JAVA_LONG, ADDRESS);
            thread = handle(lookup, "fixture_thread", scopedResult);
            retire = handle(lookup, "fixture_retire", FunctionDescriptor.of(JAVA_INT, ADDRESS, JAVA_LONG));
            finish = handle(lookup, "fixture_finish", scopedResult);
            MethodHandle drive = handle(lookup, "fixture_drive",
                FunctionDescriptor.of(JAVA_INT, ADDRESS, ADDRESS, ADDRESS, JAVA_INT, JAVA_INT));
            MethodType type = MethodType.methodType(int.class, MemorySegment.class,
                long.class, int.class, MemorySegment.class);
            MethodHandle target = MethodHandles.lookup().findStatic(ManagedCallbacks.class, "callback", type);
            MemorySegment upcall = LINKER.upcallStub(target,
                FunctionDescriptor.of(JAVA_INT, ADDRESS, JAVA_LONG, JAVA_INT, ADDRESS), lifetime);
            MemorySegment first = lifetime.allocate(JAVA_INT);
            MemorySegment second = lifetime.allocate(JAVA_INT);
            for (int i = 2; i < arguments.length; i += 3) {
                int payload = Integer.parseInt(arguments[i]);
                int profile = Integer.parseInt(arguments[i + 1]);
                int offset = Integer.parseInt(arguments[i + 2]);
                first.set(JAVA_INT, 0, offset);
                second.set(JAVA_INT, 0, offset + 7);
                int status = (int) drive.invokeExact(upcall, first, second, payload, profile);
                if (status != 0) {
                    throw new IllegalStateException("fixture driver status " + status);
                }
            }
        }
    }
}
