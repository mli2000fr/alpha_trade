"""Lanceur direct : python -m modelFactory.run_train [options]"""
import sys
from modelFactory.cli import main

if __name__ == "__main__":
    main(["--mode", "train"] + sys.argv[1:])



