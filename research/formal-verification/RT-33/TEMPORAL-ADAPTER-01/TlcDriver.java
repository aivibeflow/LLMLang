import tlc2.TLC;
import tlc2.output.EC;

public final class TlcDriver {
    public static void main(String[] args) {
        TLC checker = new TLC();
        if (!checker.handleParameters(args)) {
            System.exit(64);
        }
        int outcome = checker.process();
        System.out.println("TLC_DRIVER_RESULT " + outcome);
        System.exit(EC.ExitStatus.errorConstantToExitStatus(outcome));
    }
}
