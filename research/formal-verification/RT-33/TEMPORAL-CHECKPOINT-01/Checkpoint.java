import java.io.PrintStream;
import tlc2.TLC;
import tlc2.TLCGlobals;
import util.ToolIO;

public final class Checkpoint {
    public static void main(String[] arguments) {
        ToolIO.out = new PrintStream(System.out, true) {
            @Override public void println(String message) {
                super.println(message);
                if (message.contains("Checkpointing completed")) {
                    Runtime.getRuntime().halt(73);
                }
                if (message.startsWith("Finished computing initial states:")) {
                    var modelChecker = TLCGlobals.mainChecker;
                    var wake = new Thread(() -> {
                        try {
                            while (true) {
                                synchronized (modelChecker) {
                                    modelChecker.notifyAll();
                                }
                                Thread.sleep(2);
                            }
                        } catch (InterruptedException interrupted) {
                            Thread.currentThread().interrupt();
                        }
                    }, "checkpoint-test-wakeup");
                    wake.setDaemon(true);
                    wake.start();
                }
            }
        };
        TLC checker = new TLC();
        if (!checker.handleParameters(arguments)) {
            System.exit(64);
        }
        TLCGlobals.forceChkpt();
        System.exit(checker.process());
    }
}
