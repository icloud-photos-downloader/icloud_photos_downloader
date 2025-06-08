"""takes results of compatibility tests and compile into one file"""

import itertools
import os


def _stats(files):
    """Print statistics"""
    total = len([f for f in files if f[4] != "na"])
    passed = len([f for f in files if f[4] == "pass"])
    print(
        f"Compatibility rate: {round(100 * passed / total, 1) if total > 0 else 0}% ({passed} passed out of {total})"
    )
    print("")


def _matrix(files, special):
    """Prints matrix"""
    archs = [
        k for k, _ in itertools.groupby(sorted(files, key=lambda ft: ft[3]), key=lambda ft: ft[3])
    ]
    # sort by priority of archs
    presort = ["amd64", "arm64", "arm32v7"]
    archs_sorted = sorted(archs, key=lambda k: f"{presort.index(k) if k in presort else 9}{k}")
    # caption
    print("|".join(["OSes and distros"] + archs_sorted))
    print("|".join(["-"] + ["-" for a in archs_sorted]))

    oses = [
        k for k, _ in itertools.groupby(sorted(files, key=lambda ft: ft[2]), key=lambda ft: ft[2])
    ]
    for o in oses:
        results_raw = [
            list(filter(lambda ft: ft[2] == o and ft[3] == a, files)) for a in archs_sorted
        ]
        results = [
            "N/A"
            if len(r) == 0 or r[0][4] == "na"
            else (r[0][4] + ("" if r[0][4] != "pass" or r[0][0] is False else f" {special}"))
            for r in results_raw
        ]
        print("|".join([o] + results))


def print_breakdowns(folder, special_content_checker, special_pair):
    """param: folder"""
    (abbr, description) = special_pair
    files = [f for f in os.listdir(folder) if not os.path.isdir(f)]
    fts = [
        [special_content_checker(os.path.join(folder, f))] + f.split(".")
        for f in files
        if len(f.split(".")) == 4
    ]
    _stats(fts)
    print("Legend:")
    print("- N/A - not applicable/available")
    print("- pass - test pass")
    print("- fail - test fail")
    print(f"- pass {abbr} - {description}")
    print("")
    groups = [
        (k, list(g))
        for k, g in itertools.groupby(sorted(fts, key=lambda ft: ft[1]), key=lambda ft: ft[1])
    ]
    for g, f in groups:
        print(f"### {g}")
        _stats(f)
        _matrix(f, abbr)
