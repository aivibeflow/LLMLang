import java.io.BufferedReader;
import java.io.InputStreamReader;

public final class Probe {
    private static double decode(String field) {
        return Double.longBitsToDouble(Long.parseUnsignedLong(field, 16));
    }

    private static String encode(double value) {
        return Long.toUnsignedString(Double.doubleToRawLongBits(value), 16);
    }

    public static void main(String[] args) throws Exception {
        BufferedReader reader = new BufferedReader(new InputStreamReader(System.in));
        StringBuilder output = new StringBuilder();
        for (String row; (row = reader.readLine()) != null;) {
            String[] fields = row.split(" ");
            double a = decode(fields[0]), b = decode(fields[1]), c = decode(fields[2]);
            output.append(encode(a * b + c)).append(' ').append(encode(Math.fma(a, b, c))).append('\n');
        }
        System.out.print(output);
    }
}
