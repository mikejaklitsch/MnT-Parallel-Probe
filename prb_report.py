#!/usr/bin/env python3
"""Turn a PRB_TEST run into a verdict, confound-free edition.

The country pulse no longer writes any shared state, so there is no per-country
marker to bracket the parallel burn. Instead every month leaves one weather-pulse
marker after its work is done (QUIET, PARALLEL, or SERIAL_END), and we read the
month-to-month cadence. The quiet months are the baseline with no burn; subtract
that from the parallel and serial months to isolate each burn's wall time:

    burn(phase) = median month cadence in that phase - median quiet cadence

The serial arm also brackets itself tightly with SERIAL_START/END (one scope, no
shared write), which is the authoritative serial number and a cross-check on the
cadence method. If the isolated parallel burn is much smaller than the serial
burn, the dispatch runs countries concurrently; if they match, it is serial.

Usage: ./prb_report.py [debug.log] [cpu_probe.csv]
"""
import re
import sys
import statistics
from pathlib import Path

DEFAULT_LOG = Path(
    "/mnt/c/Users/Mjaklitsch/Documents/Paradox Interactive/"
    "Europa Universalis V/logs/debug.log"
)

TS = re.compile(r"\[(\d{2}):(\d{2}):(\d{2})\]")
EVT = re.compile(
    r"PRB_TEST\s+(\w+)"
    r"(?:.*?phase=(\d+))?"
    r"(?:.*?month=(\d+))?"
    r"(?:.*?countries=(\d+))?"
)
# One marker per finished month, logged after that month's work.
MONTH_END = {"QUIET", "PARALLEL", "SERIAL_END"}


def secs(h, m, s):
    return int(h) * 3600 + int(m) * 60 + int(s)


def span(a, b):
    d = b - a
    return d + 86400 if d < 0 else d


def load_events(path):
    out = []
    for line in Path(path).read_text(errors="replace").splitlines():
        if "PRB_TEST" not in line:
            continue
        t, e = TS.search(line), EVT.search(line)
        if not (t and e):
            continue
        kind, phase, month, countries = e.groups()
        out.append({
            "t": secs(*t.groups()), "kind": kind,
            "phase": int(phase) if phase else None,
            "month": int(month) if month else None,
            "countries": int(countries) if countries else None,
        })
    return out


def med(xs):
    return statistics.median(xs) if xs else None


def main():
    log = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LOG
    if not log.exists():
        sys.exit(f"debug.log not found: {log}")
    events = load_events(log)
    if not events:
        sys.exit("No PRB_TEST lines found. Run the probe first.")

    # month-end markers in time order -> cadence tagged by the finishing month's phase
    marks = sorted((e for e in events if e["kind"] in MONTH_END), key=lambda e: e["t"])
    cad = {0: [], 1: [], 2: []}   # phase -> list of month cadences
    print(f"{'month':>8} {'phase':>5} {'cadence(s)':>11}")
    for i in range(1, len(marks)):
        prev, cur = marks[i - 1], marks[i]
        d = span(prev["t"], cur["t"])
        if cur["phase"] in cad:
            cad[cur["phase"]].append(d)
        print(f"{str(cur['month']):>8} {str(cur['phase']):>5} {d:>11}")

    # tight serial bracket: SERIAL_START -> SERIAL_END per month
    starts = {e["month"]: e["t"] for e in events if e["kind"] == "SERIAL_START"}
    ends = {e["month"]: e["t"] for e in events if e["kind"] == "SERIAL_END"}
    tight = [span(starts[m], ends[m]) for m in starts if m in ends]

    base = med(cad[0])
    par_month, ser_month = med(cad[1]), med(cad[2])
    ser_tight = med(tight)

    print()
    print(f"quiet baseline / month : {base} s   ({len(cad[0])} months)")
    print(f"parallel month cadence : {par_month} s   ({len(cad[1])} months)")
    print(f"serial   month cadence : {ser_month} s   ({len(cad[2])} months)")
    if ser_tight is not None:
        print(f"serial burn (tight)    : {ser_tight} s   ({len(tight)} months)")

    if base is None or par_month is None or ser_tight is None:
        print("\nNeed a quiet burst, a parallel burst, and a serial burst to compare.")
        return

    par_burn = par_month - base
    ser_burn = ser_tight               # authoritative serial burn
    print()
    print(f"parallel burn (cadence - baseline): {par_burn:.0f} s")
    print(f"serial   burn (tight bracket)     : {ser_burn:.0f} s")
    if par_burn > 0:
        ratio = ser_burn / par_burn
        print(f"serial / parallel                 : {ratio:.1f}x")
        if ratio >= 2:
            print(f"VERDICT: the pulse runs countries concurrently across ~{ratio:.0f} cores.")
        else:
            print("VERDICT: no speedup. The dispatch is serial even with no shared writes.")
    else:
        print("Parallel burn is at or below the noise floor; raise @prb_test_burn_outer.")


if __name__ == "__main__":
    main()
