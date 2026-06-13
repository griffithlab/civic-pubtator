#!/usr/bin/env python3
import argparse, os, subprocess, sys

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR    = os.path.dirname(os.path.dirname(SCRIPTS_DIR))
TMVAR_DIR   = os.path.join(REPO_DIR, "tools", "tmvar")
JAR         = os.path.join(TMVAR_DIR, "tmVar.jar")

def main():
    parser = argparse.ArgumentParser(
        description="Run tmVar3 variant extraction on a folder of BioC XML files."
    )
    parser.add_argument("input_dir",  help="Folder containing BioC XML input files")
    parser.add_argument("output_dir", help="Folder where output files will be written")
    parser.add_argument("--xmx",  default="5G", metavar="SIZE",
                        help="Java max heap size (default: 5G)")
    parser.add_argument("--xms",  default="5G", metavar="SIZE",
                        help="Java initial heap size (default: 5G)")
    parser.add_argument("--train", action="store_true",
                        help="Run in Train mode (default: Test)")
    parser.add_argument("--keep-tmp", action="store_true",
                        help="Keep temporary CRF files (default: deleted)")
    parser.add_argument("--rs-only", action="store_true",
                        help="Suppress CA# output, show RS# only")
    parser.add_argument("--hide-multiple", action="store_true",
                        help="Hide ambiguous/multiple mappings")
    parser.add_argument("--tmp-dir", default=None, metavar="DIR",
                        help="Temporary file directory (default: <output>/tmp)")
    parser.add_argument("--timeout-per-doc", type=int, default=0, metavar="SECONDS",
                        help="Per-document timeout in seconds (0 = no limit)")
    args = parser.parse_args()

    if not os.path.isfile(JAR):
        sys.exit(f"ERROR: tmVar.jar not found at {JAR}")

    input_dir  = os.path.abspath(args.input_dir)
    output_dir = os.path.abspath(args.output_dir)
    tmp_dir    = os.path.abspath(args.tmp_dir) if args.tmp_dir else os.path.join(output_dir, "tmp")

    if not os.path.isdir(input_dir):
        sys.exit(f"ERROR: Input folder not found: {input_dir}")

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(tmp_dir, exist_ok=True)

    # GCS sync doesn't preserve POSIX permissions — ensure CRF binaries are executable.
    for binary in ("CRF/crf_test", "CRF/crf_learn",
                   "CRF/.libs/crf_test", "CRF/.libs/crf_learn"):
        p = os.path.join(TMVAR_DIR, binary)
        if os.path.isfile(p):
            os.chmod(p, os.stat(p).st_mode | 0o111)

    # Smoke-test CRF++ before launching Java — a broken install produces a very
    # cryptic empty-.ME failure deep in the pipeline with no obvious cause.
    crf_test_bin = os.path.join(TMVAR_DIR, "CRF", "crf_test")
    if not os.path.isfile(crf_test_bin):
        sys.exit(f"ERROR: CRF binary not found: {crf_test_bin}\n"
                 f"       Re-build with: cd {TMVAR_DIR}/CRF && ./configure && "
                 f"make CXXFLAGS=\"-std=c++14 -O3 -Wall -fPIE\" crf_test crf_learn")
    probe = subprocess.run(
        [crf_test_bin, "--version"],
        cwd=TMVAR_DIR,
        capture_output=True,
        text=True,
    )
    probe_out = probe.stdout + probe.stderr
    if "CRF++" not in probe_out:
        sys.exit(
            f"ERROR: CRF++ smoke-test failed — '{crf_test_bin} --version' did not print 'CRF++'.\n"
            f"Output: {probe_out.strip()}\n"
            f"Fix: rebuild CRF++ from source:\n"
            f"  cd {TMVAR_DIR}/CRF\n"
            f"  ./configure\n"
            f"  sed -i 's/std::make_pair<int, int>(/std::make_pair(/g' feature_index.cpp\n"
            f"  make clean && make CXXFLAGS=\"-std=c++14 -O3 -Wall -fPIE\" crf_test crf_learn"
        )

    cmd = [
        "java", f"-Xmx{args.xmx}", f"-Xms{args.xms}",
        "-jar", JAR,
        input_dir,
        output_dir,
        "Train" if args.train else "Test",
        "false" if args.keep_tmp else "true",
        "true"  if args.rs_only else "false",
        "true"  if args.hide_multiple else "false",
        tmp_dir,
        str(args.timeout_per_doc),
    ]

    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=TMVAR_DIR)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
