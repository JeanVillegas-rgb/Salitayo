"""
Django management command to fine-tune T5 model.

Usage:
    python manage.py train_t5 --epochs 3 --batch-size 8 --learning-rate 2e-5
    python manage.py train_t5 --epochs 3 --batch-size 4 --model t5-small
    python manage.py train_t5 --data-file training_pairs.jsonl
    python manage.py train_t5 --evaluate-only
    python manage.py train_t5 --predict "The samples were analyzed by the researchers."
"""

import logging
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from restructurer.training_engine import T5FineTuner

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Fine-tune T5 model for text restructuring"

    def add_arguments(self, parser):
        parser.add_argument(
            "--epochs",
            type=int,
            default=3,
            help="Number of training epochs (default: 3)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=8,
            help="Training batch size (default: 8)",
        )
        parser.add_argument(
            "--learning-rate",
            type=float,
            default=2e-5,
            help="Learning rate (default: 2e-5)",
        )
        parser.add_argument(
            "--model",
            type=str,
            default="t5-base",
            choices=["t5-small", "t5-base", "t5-large"],
            help="Model size (default: t5-base)",
        )
        parser.add_argument(
            "--evaluate-only",
            action="store_true",
            help="Only evaluate the model without training",
        )
        parser.add_argument(
            "--predict",
            type=str,
            help="Generate prediction for given text",
        )
        parser.add_argument(
            "--stats",
            action="store_true",
            help="Display model statistics",
        )
        parser.add_argument(
            "--data-file",
            type=str,
            help="Optional CSV, JSON, or JSONL file with original/restructured pairs",
        )

    def handle(self, *args, **options):
        try:
            # Use an explicit dataset file when supplied; otherwise fall back to
            # the existing corpus directory for backward compatibility.
            corpus_dir = Path(__file__).resolve().parent.parent.parent.parent / "rag_corpus"
            data_file = Path(options["data_file"]).expanduser().resolve() if options.get("data_file") else None

            if data_file and not data_file.exists():
                raise CommandError(
                    f"Training data file not found: {data_file}. "
                    f"Pass a real file path or omit --data-file to use the built-in task-pattern examples."
                )

            if not data_file and not corpus_dir.exists():
                raise CommandError(f"Corpus directory not found: {corpus_dir}")

            # Initialize fine-tuner
            self.stdout.write(
                self.style.SUCCESS(f"Initializing T5 fine-tuner ({options['model']})...")
            )
            tuner = T5FineTuner(model_name=options["model"])

            # Stats
            if options["stats"]:
                stats = tuner.get_model_stats()
                self.stdout.write(self.style.SUCCESS("\n=== Model Statistics ==="))
                for key, value in stats.items():
                    self.stdout.write(f"{key}: {value}")
                return

            # Predict
            if options["predict"]:
                self.stdout.write(self.style.SUCCESS("\nLoading fine-tuned model..."))
                try:
                    tuner.load_model()
                except:
                    raise CommandError(
                        "Fine-tuned model not found. Train the model first."
                    )

                self.stdout.write(self.style.SUCCESS("\n=== Input ==="))
                self.stdout.write(options["predict"])

                prediction = tuner.predict(options["predict"])
                self.stdout.write(self.style.SUCCESS("\n=== Restructured Output ==="))
                self.stdout.write(prediction)
                return

            # Evaluate only
            if options["evaluate_only"]:
                self.stdout.write(self.style.SUCCESS("Preparing data..."))
                tuner.prepare_data(corpus_dir=corpus_dir, pair_file=data_file)

                self.stdout.write(self.style.SUCCESS("Evaluating model..."))
                results = tuner.evaluate()

                self.stdout.write(self.style.SUCCESS("\n=== Evaluation Results ==="))
                for key, value in results.items():
                    self.stdout.write(f"{key}: {value}")
                return

            # Train
            self.stdout.write(self.style.SUCCESS("\n=== Starting Training ==="))
            self.stdout.write(f"Epochs: {options['epochs']}")
            self.stdout.write(f"Batch size: {options['batch_size']}")
            self.stdout.write(f"Learning rate: {options['learning_rate']}")
            self.stdout.write(f"Corpus: {corpus_dir}\n")
            if data_file:
                self.stdout.write(f"Data file: {data_file}\n")

            tuner.train(
                corpus_dir=corpus_dir,
                pair_file=data_file,
                num_epochs=options["epochs"],
                batch_size=options["batch_size"],
                learning_rate=options["learning_rate"],
            )

            self.stdout.write(
                self.style.SUCCESS("\n✓ Training completed successfully!")
            )
            self.stdout.write(f"Model saved to: {tuner.output_dir}")

        except CommandError as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
            raise
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Unexpected error: {str(e)}"))
            logger.exception("Training failed")
            raise CommandError(str(e))
