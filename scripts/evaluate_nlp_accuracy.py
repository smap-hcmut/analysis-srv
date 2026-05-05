#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from internal.evaluation.usecase.evaluate_nlp import (
    build_eval_logger,
    build_nlp_evaluator,
    evaluate_samples,
    load_eval_samples,
    load_eval_config,
    summary_to_dict,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate SMAP NLP accuracy against a golden set.",
    )
    parser.add_argument(
        "--dataset",
        default="scripts/fixtures/nlp_eval_golden_ahamova.json",
        help="Path to evaluation dataset JSON",
    )
    parser.add_argument(
        "--output-details",
        action="store_true",
        help="Include per-sample predictions in output",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_eval_config()
    logger = build_eval_logger(level="ERROR")
    samples = load_eval_samples(args.dataset)
    evaluators = build_nlp_evaluator(config, logger)
    results, summary = evaluate_samples(samples, evaluators)

    payload: dict[str, object] = {
        "dataset": args.dataset,
        "summary": summary_to_dict(summary),
    }
    if args.output_details:
        payload["results"] = [
            {
                "sample_id": result.sample_id,
                "expected": {
                    "intent": result.expected.intent,
                    "sentiment": result.expected.sentiment,
                    "keywords": result.expected.keywords,
                    "aspects": result.expected.aspects,
                },
                "predicted": {
                    "intent": result.predicted.intent,
                    "intent_confidence": result.predicted.intent_confidence,
                    "sentiment": result.predicted.sentiment,
                    "sentiment_confidence": result.predicted.sentiment_confidence,
                    "keywords": result.predicted.keywords,
                    "aspects": result.predicted.aspects,
                    "clean_text": result.predicted.clean_text,
                    "is_spam": result.predicted.is_spam,
                    "spam_reasons": result.predicted.spam_reasons,
                },
            }
            for result in results
        ]

    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
