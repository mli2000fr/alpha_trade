"""Lanceur direct : python -m modelFactory.run_predict [options]"""
import sys
from modelFactory.cli import main

if __name__ == "__main__":
    main(["--mode", "predict"] + sys.argv[1:])



