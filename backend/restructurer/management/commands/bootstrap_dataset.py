"""Bootstrap a mixed-domain restructuring dataset from raw text files.

This command helps you create a starter `original` / `restructured` pair file
when you do not yet have a hand-labeled dataset.

It reads `.txt` and `.md` files, splits them into sentences/paragraphs, and
creates heuristic simplifications that you can review and correct.

Example:
    python manage.py bootstrap_dataset --input-dir ../samples --output training_pairs.jsonl
    python manage.py bootstrap_dataset --input-dir ../docs --output training_pairs.csv --format csv
"""

from __future__ import annotations

import csv
import json
import logging
import re
from dataclasses import asdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from restructurer.general_training_data import TrainingPair

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Create a starter restructuring dataset from raw text files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--input-dir",
            type=str,
            required=True,
            help="Directory containing .txt or .md files",
        )
        parser.add_argument(
            "--output",
            type=str,
            default="training_pairs.jsonl",
            help="Output path for the generated dataset",
        )
        parser.add_argument(
            "--format",
            type=str,
            choices=["jsonl", "csv"],
            default="jsonl",
            help="Output format",
        )
        parser.add_argument(
            "--min-sentences",
            type=int,
            default=1,
            help="Minimum number of sentences per chunk",
        )
        parser.add_argument(
            "--max-sentences",
            type=int,
            default=3,
            help="Maximum number of sentences per chunk",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=2000,
            help="Maximum number of pairs to generate",
        )

    def handle(self, *args, **options):
        input_dir = Path(options["input_dir"]).expanduser().resolve()
        output_path = Path(options["output"]).expanduser().resolve()
        output_format = options["format"]
        min_sentences = max(1, int(options["min_sentences"]))
        max_sentences = max(min_sentences, int(options["max_sentences"]))
        limit = max(1, int(options["limit"]))

        if not input_dir.exists():
            raise CommandError(f"Input directory not found: {input_dir}")

        source_files = [
            path for path in sorted(input_dir.rglob("*"))
            if path.is_file() and path.suffix.lower() in {".txt", ".md"}
        ]
        if not source_files:
            raise CommandError(f"No .txt or .md files found in {input_dir}")

        pairs: list[TrainingPair] = []
        for file_path in source_files:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            file_pairs = self._build_pairs_from_text(text, file_path.stem, min_sentences, max_sentences)
            pairs.extend(file_pairs)
            if len(pairs) >= limit:
                break

        pairs = pairs[:limit]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_format == "jsonl":
            with output_path.open("w", encoding="utf-8") as handle:
                for pair in pairs:
                    handle.write(json.dumps(asdict(pair), ensure_ascii=False) + "\n")
        else:
            with output_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["original", "restructured", "source"])
                writer.writeheader()
                for pair in pairs:
                    writer.writerow({
                        "original": pair.original_text,
                        "restructured": pair.restructured_text,
                        "source": pair.source,
                    })

        self.stdout.write(self.style.SUCCESS(f"Created {len(pairs)} pairs at {output_path}"))
        self.stdout.write(
            self.style.WARNING(
                "Review the generated pairs before training. These are starter examples, not final ground truth."
            )
        )

    def _build_pairs_from_text(
        self,
        text: str,
        source_name: str,
        min_sentences: int,
        max_sentences: int,
    ) -> list[TrainingPair]:
        paragraphs = self._split_paragraphs(text)
        pairs: list[TrainingPair] = []

        for paragraph in paragraphs:
            sentences = self._split_sentences(paragraph)
            if len(sentences) < min_sentences:
                continue

            for start in range(0, len(sentences)):
                for size in range(min_sentences, max_sentences + 1):
                    chunk = sentences[start : start + size]
                    if len(chunk) < min_sentences:
                        continue
                    original = " ".join(chunk).strip()
                    if len(original.split()) < 8:
                        continue
                    restructured = self._heuristic_restructure(original)
                    if restructured and restructured != original:
                        pairs.append(
                            TrainingPair(
                                original_text=original,
                                restructured_text=restructured,
                                source=f"bootstrap:{source_name}",
                            )
                        )
        return pairs

    def _split_paragraphs(self, text: str) -> list[str]:
        text = text.replace("\r\n", "\n")
        blocks = [block.strip() for block in re.split(r"\n{2,}", text) if block.strip()]
        return blocks or [text.strip()]

    def _split_sentences(self, text: str) -> list[str]:
        text = re.sub(r"\s+", " ", text).strip()
        parts = re.split(r"(?<=[.!?])\s+", text)
        return [part.strip() for part in parts if part.strip()]

    def _heuristic_restructure(self, text: str) -> str:
        simplified = text

        replacements = [
            (r"\bAlthough\b", "While"),
            (r"\bHowever,\b", ""),
            (r"\bIn order to\b", "To"),
            (r"\bdemonstrate\b", "show"),
            (r"\bfacilitate\b", "help"),
            (r"\butilize\b", "use"),
            (r"\bapproximately\b", "about"),
            (r"\bcommence\b", "start"),
            (r"\breduce cognitive load\b", "make reading easier"),
            (r"\bsubstantially\b", "a lot"),
            (r"\bmultiple\b", "many"),
            (r"\bcomprehensive\b", "full"),
            (r"\bprior to\b", "before"),
            (r"\baccommodate\b", "fit"),
            (r"\bsubsequently\b", "then"),
        ]
        for pattern, replacement in replacements:
            simplified = re.sub(pattern, replacement, simplified, flags=re.IGNORECASE)

        # Split long sentences at common conjunctions when possible.
        simplified = re.sub(r",\s*(and|but|so|because|while|which|that)\s+", ". ", simplified, flags=re.IGNORECASE)
        simplified = re.sub(r";\s*", ". ", simplified)
        simplified = re.sub(r"\s+", " ", simplified).strip()

        # Keep it short and readable.
        if len(simplified.split()) > 40:
            parts = re.split(r"(?<=[.!?])\s+", simplified)
            if len(parts) > 1:
                simplified = " ".join(parts)

        if simplified and simplified[-1] not in ".!?":
            simplified += "."

        return simplified
