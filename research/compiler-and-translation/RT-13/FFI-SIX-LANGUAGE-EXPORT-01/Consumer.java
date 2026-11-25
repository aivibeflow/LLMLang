import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.SymbolLookup;
import java.nio.file.Path;

import static java.lang.foreign.ValueLayout.ADDRESS;
import static java.lang.foreign.ValueLayout.JAVA_INT;
import static java.lang.foreign.ValueLayout.JAVA_LONG;

class Consumer {
    public static void main(String[] args) throws Throwable {
        try (var arena = Arena.ofConfined();
             var input = new BufferedReader(new InputStreamReader(System.in))) {
            var library = SymbolLookup.libraryLookup(Path.of(args[0]), arena);
            var function = Linker.nativeLinker().downcallHandle(
                library.find("checked_add").orElseThrow(),
                FunctionDescriptor.of(JAVA_INT, JAVA_LONG, JAVA_INT, ADDRESS));
            var slot = arena.allocate(JAVA_LONG);
            for (String row; (row = input.readLine()) != null; ) {
                var pieces = row.split(" ");
                long word = Long.parseUnsignedLong(pieces[0]);
                int enabled = Integer.parseUnsignedInt(pieces[1]);
                slot.set(JAVA_LONG, 0, 0xabad1234abcdef01L);
                int status = (int) function.invokeExact(word, enabled, slot);
                System.out.println(status + " " + Long.toUnsignedString(slot.get(JAVA_LONG, 0)));
            }
        }
    }
}
