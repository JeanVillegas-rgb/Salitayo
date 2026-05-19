"""
Django management command to evaluate T5 model quality.

Usage:
    python manage.py evaluate_model
    python manage.py evaluate_model --sample-size 10
"""

import logging
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from restructurer.training_engine import T5FineTuner
from restructurer.model_evaluator import TextEvaluator

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Evaluate T5 restructuring model quality"

    def add_arguments(self, parser):
        parser.add_argument(
            "--sample-size",
            type=int,
            default=5,
            help="Number of samples to evaluate (default: 5)",
        )

    def handle(self, *args, **options):
        try:
            self.stdout.write(self.style.SUCCESS("Loading fine-tuned model..."))
            tuner = T5FineTuner()

            try:
                tuner.load_model()
            except:
                raise CommandError(
                    "Fine-tuned model not found. Train the model first with: python manage.py train_t5"
                )

            evaluator = TextEvaluator()

            # Sample test cases
            test_cases = [
                {
                    "original": "The researchers, who had been studying the effects of various reading interventions for over a decade, discovered that structured literacy approaches were significantly more effective.",
                    "name": "Complex sentence"
                },
                {
                    "original": "Although climate change represents a multifaceted challenge requiring comprehensive mitigation strategies, renewable energy adoption constitutes a viable mechanism for carbon emission reduction.",
                    "name": "Technical complexity"
                },
                {
                    "original": "The experiment was conducted by the team using standardized protocols that had been previously validated.",
                    "name": "Passive voice"
                },
                {
                    "original": "Students who struggle with reading comprehension, particularly those who have been diagnosed with dyslexia, benefit substantially from multisensory instructional techniques.",
                    "name": "Multiple clauses"
                },
                {
                    "original": "The photosynthetic mechanism facilitates the conversion of photons into chemical energy via electron transfer chains.",
                    "name": "Technical jargon"
                },
            ]

            self.stdout.write(self.style.SUCCESS("\n=== Model Evaluation ===\n"))

            sample_limit = min(options["sample_size"], len(test_cases))

            for i, case in enumerate(test_cases[:sample_limit], 1):
                self.stdout.write(f"\n--- Sample {i}: {case['name']} ---")
                self.stdout.write(f"Original:\n{case['original']}\n")

                # Predict
                restructured = tuner.predict(case["original"])
                self.stdout.write(f"Restructured:\n{restructured}\n")

                # Evaluate
                metrics = evaluator.evaluate_pair(case["original"], restructured)

                self.stdout.write(self.style.SUCCESS("Metrics:"))
                
                # Readability
                self.stdout.write(f"  Readability Grade: {metrics['readability']['readability_grade']}")
                self.stdout.write(f"  Avg Sentence Length: {metrics['readability']['avg_sentence_length']}")
                self.stdout.write(f"  Avg Word Length: {metrics['readability']['avg_word_length']}")
                
                # Compression
                self.stdout.write(f"  Compression Ratio: {metrics['compression']:.2f}")
                
                # Vocabulary
                self.stdout.write(f"  Vocabulary Preserved: {metrics['vocabulary']['vocabulary_preserved']:.1%}")

            self.stdout.write(
                self.style.SUCCESS("\n✓ Evaluation completed!")
            )

        except CommandError as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
            raise
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Unexpected error: {str(e)}"))
            logger.exception("Evaluation failed")
            raise CommandError(str(e))
