"""Collect new FR guidance candidates. No training, SQL or market returns."""
import argparse
from pathlib import Path

from service.fr.guidance_corpus_11d import collect, pdf_stage, review_stage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("metadata", "pdf", "review"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--identities", type=Path, default=Path("artifacts/fr/sprint6c_reference/identities.jsonl.gz"))
    parser.add_argument("--prior", type=Path, default=Path("artifacts/research/fr_guidance_feasibility/pilot-20260917-124430"))
    parser.add_argument("--review", type=Path, default=Path("config/research_fr/guidance_review_11d_v1.json"))
    args = parser.parse_args()
    if args.stage == "metadata":
        result = collect(args.output, args.identities, args.prior)
    elif args.stage == "pdf":
        result = pdf_stage(args.output)
    else:
        result = review_stage(args.output, args.review)
    print(result["status"], flush=True)


if __name__ == "__main__":
    main()
