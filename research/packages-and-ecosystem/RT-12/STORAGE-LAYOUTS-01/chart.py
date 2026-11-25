"""Render persisted regular-file byte lengths from the storage comparison."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
STYLES = (
    ("filesystem_cas", "Filesystem CAS", "#2464a5", "o"),
    ("stdlib_dbm_kv", "Stdlib DBM KV", "#9d4b24", "s"),
    ("sqlite_kv", "SQLite KV", "#187340", "D"),
    ("sqlite_with_reverse_index", "SQLite with reverse index", "#7547a7", "^"),
)


def main():
    records = json.loads((HERE / "evidence.json").read_text())["results"]
    counts = [int(count) for count in records]
    plt.rcParams.update({"svg.hashsalt": "llmlang-rt12-layouts", "font.size": 11})
    fig, axis = plt.subplots(figsize=(7.6, 4.5), layout="constrained")
    for key, name, color, marker in STYLES:
        values = [records[str(n)]["layouts"][key]["regular_file_bytes"] / 1024 for n in counts]
        axis.plot(counts, values, label=name, color=color, marker=marker, linewidth=1.8)
    axis.set(xlabel="Content-addressed graph objects", ylabel="Persisted regular-file length (KiB)",
             xscale="log", yscale="log")
    axis.set_xticks(counts, [str(n) for n in counts])
    axis.grid(True, axis="y", which="major", alpha=0.22)
    axis.legend(loc="upper left", frameon=True)
    path = HERE / "persisted-layout-sizes.svg"
    fig.savefig(path, metadata={"Date": None})
    path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
    plt.close(fig)


if __name__ == "__main__":
    main()
