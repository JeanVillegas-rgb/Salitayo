"""
Fine-tune T5 model for dyslexia-friendly text restructuring.

This module implements the training loop and model management for
a fine-tuned T5 model specialized in academic text simplification.

Usage:
    python manage.py shell
    >>> from restructurer.training_engine import T5FineTuner
    >>> tuner = T5FineTuner()
    >>> tuner.train(epochs=3)
    >>> tuner.evaluate()
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch
import numpy as np
from transformers import (
    T5ForConditionalGeneration,
    T5Tokenizer,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    DataCollatorForSeq2Seq,
)
from datasets import Dataset

from .general_training_data import GeneralTrainingDataCollector

logger = logging.getLogger(__name__)


class T5FineTuner:
    """Fine-tune T5 model for text restructuring."""

    def __init__(
        self,
        model_name: str = "t5-base",
        output_dir: str = "models/t5_restructurer",
        cache_dir: str = "models/cache",
        device: str = None,
    ):
        """
        Initialize the fine-tuner.

        Args:
            model_name: HuggingFace model ID (t5-base, t5-small, etc.)
            output_dir: Directory to save fine-tuned model
            cache_dir: Directory for model cache
            device: "cuda" or "cpu" (auto-detect if None)
        """
        self.model_name = model_name
        self.output_dir = Path(output_dir)
        self.cache_dir = Path(cache_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Auto-detect device
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device

        logger.info(f"Using device: {self.device}")

        # Load model and tokenizer
        self.tokenizer = T5Tokenizer.from_pretrained(
            model_name, cache_dir=str(self.cache_dir)
        )
        self.model = T5ForConditionalGeneration.from_pretrained(
            model_name, cache_dir=str(self.cache_dir)
        )
        self.model.to(self.device)

        self.trainer = None
        self.train_dataset = None
        self.eval_dataset = None

    def prepare_data(self, corpus_dir: Path = None, pair_file: Path = None, test_size: float = 0.2) -> Tuple:
        """
        Prepare training and evaluation datasets.

        Args:
            corpus_dir: Optional path kept for backward compatibility
            pair_file: Optional CSV/JSON/JSONL file with original/restructured pairs
            test_size: Proportion of data for evaluation

        Returns:
            Tuple of (train_dataset, eval_dataset)
        """
        logger.info("Preparing training data...")

        # Collect data from the explicit dataset file when available.
        if pair_file:
            collector = GeneralTrainingDataCollector()
            pairs = collector.collect_all_pairs(pair_file=pair_file)
        else:
            from .training_data import TrainingDataCollector
            collector = TrainingDataCollector()
            pairs = collector.collect_all_pairs()

        # Split
        train_pairs, eval_pairs = collector.get_train_test_split(test_size=test_size)

        # Convert to HuggingFace Dataset format
        train_texts = {
            "input_ids": [],
            "attention_mask": [],
            "labels": [],
        }

        eval_texts = {
            "input_ids": [],
            "attention_mask": [],
            "labels": [],
        }

        # Tokenize training data
        logger.info("Tokenizing training data...")
        for pair in train_pairs:
            # Encode input with task prefix to help T5 learn the task
            task_input = f"restructure: {pair.original_text}"
            input_encoding = self.tokenizer(
                task_input,
                max_length=512,
                padding="max_length",
                truncation=True,
                return_tensors=None,
            )

            # Encode target
            target_encoding = self.tokenizer(
                pair.restructured_text,
                max_length=256,
                padding="max_length",
                truncation=True,
                return_tensors=None,
            )

            # Replace padding token ids in labels by -100 to ignore them
            labels = target_encoding["input_ids"].copy()
            labels = [label if label != self.tokenizer.pad_token_id else -100 for label in labels]

            train_texts["input_ids"].append(input_encoding["input_ids"])
            train_texts["attention_mask"].append(input_encoding["attention_mask"])
            train_texts["labels"].append(labels)

        # Tokenize evaluation data
        logger.info("Tokenizing evaluation data...")
        for pair in eval_pairs:
            task_input = f"restructure: {pair.original_text}"
            input_encoding = self.tokenizer(
                task_input,
                max_length=512,
                padding="max_length",
                truncation=True,
                return_tensors=None,
            )

            target_encoding = self.tokenizer(
                pair.restructured_text,
                max_length=256,
                padding="max_length",
                truncation=True,
                return_tensors=None,
            )

            labels = target_encoding["input_ids"].copy()
            labels = [label if label != self.tokenizer.pad_token_id else -100 for label in labels]

            eval_texts["input_ids"].append(input_encoding["input_ids"])
            eval_texts["attention_mask"].append(input_encoding["attention_mask"])
            eval_texts["labels"].append(labels)

        # Create HuggingFace Datasets
        self.train_dataset = Dataset.from_dict(train_texts)
        self.eval_dataset = Dataset.from_dict(eval_texts)

        logger.info(f"Train dataset size: {len(self.train_dataset)}")
        logger.info(f"Eval dataset size: {len(self.eval_dataset)}")

        return self.train_dataset, self.eval_dataset

    def train(
        self,
        corpus_dir: Path = None,
        pair_file: Path = None,
        num_epochs: int = 3,
        batch_size: int = 8,
        learning_rate: float = 2e-5,
        warmup_steps: int = 500,
        weight_decay: float = 0.01,
    ):
        """
        Fine-tune the model.

        Args:
            corpus_dir: Optional path kept for backward compatibility
            pair_file: Optional CSV/JSON/JSONL file with original/restructured pairs
            num_epochs: Number of training epochs
            batch_size: Training batch size
            learning_rate: Learning rate
            warmup_steps: Number of warmup steps
            weight_decay: Weight decay for optimizer
        """
        logger.info("Starting training...")

        # Prepare data
        self.prepare_data(corpus_dir=corpus_dir, pair_file=pair_file)

        # Training arguments
        training_args = Seq2SeqTrainingArguments(
            output_dir=str(self.output_dir),
            num_train_epochs=num_epochs,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            learning_rate=learning_rate,
            warmup_steps=warmup_steps,
            weight_decay=weight_decay,
            eval_strategy="epoch",
            save_strategy="epoch",
            load_best_model_at_end=True,
            logging_dir=str(self.output_dir / "logs"),
            logging_steps=10,
            predict_with_generate=True,
            generation_max_length=256,
            generation_num_beams=4,
            seed=42,
        )

        # Data collator
        data_collator = DataCollatorForSeq2Seq(
            self.tokenizer,
            model=self.model,
            label_pad_token_id=-100,
        )

        # Trainer
        self.trainer = Seq2SeqTrainer(
            model=self.model,
            args=training_args,
            train_dataset=self.train_dataset,
            eval_dataset=self.eval_dataset,
            data_collator=data_collator,
        )

        # Train
        self.trainer.train()

        # Save final model
        self.save_model()
        logger.info("Training completed!")

    def evaluate(self) -> Dict[str, float]:
        """
        Evaluate the model on the evaluation set.

        Returns:
            Dictionary of evaluation metrics
        """
        if self.trainer is None:
            raise ValueError("Model not trained yet. Call train() first.")

        logger.info("Evaluating model...")
        results = self.trainer.evaluate()
        logger.info(f"Evaluation results: {results}")

        return results

    def predict(self, text: str, max_length: int = 256) -> str:
        """
        Generate restructured text.

        Args:
            text: Input text to restructure
            max_length: Maximum output length

        Returns:
            Restructured text
        """
        self.model.eval()
        with torch.no_grad():
            # Add task prefix for generation
            task_input = f"restructure: {text}"
            inputs = self.tokenizer.encode(task_input, return_tensors="pt").to(self.device)

            # Generate output with constrained decoding to reduce hallucination
            outputs = self.model.generate(
                inputs,
                max_length=max_length,
                num_beams=4,
                no_repeat_ngram_size=3,
                early_stopping=True,
                do_sample=False,
            )

            # Decode output
            restructured_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        return restructured_text

    def save_model(self):
        """Save the fine-tuned model."""
        try:
            self.model.save_pretrained(str(self.output_dir))
            self.tokenizer.save_pretrained(str(self.output_dir))
            logger.info(f"Model saved to {self.output_dir}")
        except Exception as e:
            fallback_dir = self.output_dir.parent / f"{self.output_dir.name}_updated"
            logger.warning(f"Target directory {self.output_dir} is locked by another process. Saving to fallback directory: {fallback_dir}")
            fallback_dir.mkdir(parents=True, exist_ok=True)
            self.model.save_pretrained(str(fallback_dir))
            self.tokenizer.save_pretrained(str(fallback_dir))
            self.output_dir = fallback_dir
            logger.info(f"Model saved to fallback directory: {fallback_dir}")


    def load_model(self, model_dir: Path = None):
        """Load a fine-tuned model."""
        model_dir = model_dir or self.output_dir
        self.model = T5ForConditionalGeneration.from_pretrained(str(model_dir))
        self.tokenizer = T5Tokenizer.from_pretrained(str(model_dir))
        self.model.to(self.device)
        logger.info(f"Model loaded from {model_dir}")

    def get_model_stats(self) -> Dict:
        """Get model statistics."""
        total_params = sum(p.numel() for p in self.model.parameters())
        trainable_params = sum(
            p.numel() for p in self.model.parameters() if p.requires_grad
        )

        return {
            "model_name": self.model_name,
            "total_parameters": total_params,
            "trainable_parameters": trainable_params,
            "device": self.device,
            "saved_at": str(self.output_dir),
        }
