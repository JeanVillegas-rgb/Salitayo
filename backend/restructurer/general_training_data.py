"""General-purpose training data preparation for text restructuring.

This module supports any text domain by using a task prefix plus a mixed-bag
pair dataset loaded from CSV, JSON, or JSONL files.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrainingPair:
    original_text: str
    restructured_text: str
    source: str = "external"


class GeneralTrainingDataCollector:
    def __init__(self, task_prefix: str = "restructure:", output_dir: Optional[Path] = None):
        self.task_prefix = task_prefix.strip()
        self.output_dir = Path(output_dir) if output_dir else Path.cwd() / "training_data"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.pairs: List[TrainingPair] = []

    def prefix(self, text: str) -> str:
        return f"{self.task_prefix} {text}".strip()

    def load_pair_file(self, pair_file: Path) -> List[TrainingPair]:
        pair_file = Path(pair_file)
        if not pair_file.exists():
            raise FileNotFoundError(f"Training pair file not found: {pair_file}")

        suffix = pair_file.suffix.lower()
        rows: List[TrainingPair] = []

        if suffix == ".csv":
            with pair_file.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    rows.extend(self._rows_from_mapping(row))
        elif suffix in {".json", ".jsonl"}:
            payloads = self._read_json_payloads(pair_file, suffix)
            for row in payloads:
                if isinstance(row, dict):
                    rows.extend(self._rows_from_mapping(row))
        else:
            raise ValueError(f"Unsupported training file type: {pair_file.suffix}")

        logger.info("Loaded %d training pairs from %s", len(rows), pair_file)
        return rows

    def _read_json_payloads(self, pair_file: Path, suffix: str) -> Sequence[dict]:
        if suffix == ".jsonl":
            payloads = []
            for line in pair_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    payloads.append(json.loads(line))
            return payloads

        payload = json.loads(pair_file.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("pairs", [])
        return []

    def _rows_from_mapping(self, row: dict) -> List[TrainingPair]:
        original = (row.get("original") or row.get("input") or row.get("source") or "").strip()
        restructured = (row.get("restructured") or row.get("target") or row.get("output") or "").strip()
        source = (row.get("source") or "external").strip() or "external"
        if original and restructured:
            return [TrainingPair(original, restructured, source)]
        return []

    def create_synthetic_pairs(self) -> List[TrainingPair]:
        # Mixed-bag examples across domains and styles so the model learns the task,
        # not one subject area.
        examples = [
            # Highly-targeted complex academic / technical word simplifications
            TrainingPair(
                "The primary objective of the methodology is to elucidate complex cellular behaviors.",
                "The main goal of the method is to explain complex cell behaviors.",
                "synthetic",
            ),
            TrainingPair(
                "The dissemination of the research findings was meticulously planned by the department.",
                "The department carefully planned how to spread the research findings.",
                "synthetic",
            ),
            TrainingPair(
                "We must amalgamate these distinct datasets to perform a holistic analysis.",
                "We must combine these separate datasets to do a complete study.",
                "synthetic",
            ),
            TrainingPair(
                "The auditor will scrutinize all financial transactions to ensure optimal compliance.",
                "The auditor will check all financial transactions to make sure everything complies.",
                "synthetic",
            ),
            TrainingPair(
                "The project encountered unprecedented challenges that required immediate remediation.",
                "The project faced new challenges that needed to be fixed immediately.",
                "synthetic",
            ),
            TrainingPair(
                "It is critical to remain cognizant of the environmental factors that influence learning.",
                "It is important to be aware of the environmental factors that affect learning.",
                "synthetic",
            ),
            TrainingPair(
                "The user commenced the setup procedure but subsequently terminated the operation.",
                "The user started the setup but then stopped it.",
                "synthetic",
            ),
            TrainingPair(
                "The initial hypothesis proved to be erroneous upon subsequent replication trials.",
                "The first hypothesis turned out to be wrong when trials were repeated.",
                "synthetic",
            ),
            TrainingPair(
                "This educational framework is designed to facilitate cognitive development in children.",
                "This school system is designed to help children develop their thinking skills.",
                "synthetic",
            ),
            TrainingPair(
                "We utilized advanced analytics to determine the optimal configuration for the server.",
                "We used advanced analytics to find the best setup for the server.",
                "synthetic",
            ),
            TrainingPair(
                "The student made a conscientious effort to adhere to the designated protocol.",
                "The student tried hard to follow the given rules.",
                "synthetic",
            ),
            TrainingPair(
                "The instruction manual was highly ambiguous, causing significant confusion among users.",
                "The instruction book was not clear, causing a lot of confusion for users.",
                "synthetic",
            ),
            TrainingPair(
                "We need to minimize redundant processes to maximize the overall throughput.",
                "We need to reduce extra steps to increase overall speed.",
                "synthetic",
            ),
            TrainingPair(
                "The software update resolved various vulnerabilities inside the network infrastructure.",
                "The software update fixed many security weaknesses in the network.",
                "synthetic",
            ),
            TrainingPair(
                "Please prioritize the task that has the highest potential impact on performance.",
                "Please do the task first that can help performance the most.",
                "synthetic",
            ),
            TrainingPair(
                "The implementation of a holistic approach is beneficial for long-term growth.",
                "Using a complete method is helpful for long-term growth.",
                "synthetic",
            ),

            # Original baseline examples
            TrainingPair(
                "The researchers, who had been studying the effects of various reading interventions for over a decade, discovered that structured literacy approaches were significantly more effective.",
                "The researchers studied reading interventions for over a decade. They found that structured literacy worked better.",
                "synthetic",
            ),
            TrainingPair(
                "The party of the first part shall, upon written notice, remit the outstanding balance within thirty calendar days unless the parties mutually agree otherwise.",
                "The first party must pay the remaining balance within 30 days after written notice unless both sides agree to something else.",
                "synthetic",
            ),
            TrainingPair(
                "The patient exhibited symptoms consistent with dehydration, including tachycardia, dry mucous membranes, and reduced urine output.",
                "The patient showed signs of dehydration. These included a fast heart rate, dry mouth, and less urine output.",
                "synthetic",
            ),
            TrainingPair(
                "Preheat the oven to 180 degrees Celsius, fold the wet ingredients into the dry mixture, and bake until the surface is lightly browned.",
                "Heat the oven to 180 degrees Celsius. Mix the wet ingredients into the dry ones. Bake until the top is lightly brown.",
                "synthetic",
            ),
            TrainingPair(
                "Honestly, I was super confused by the instructions, so I just tried a few things until it worked.",
                "I was confused by the instructions. I tried a few things until it worked.",
                "synthetic",
            ),
            TrainingPair(
                "Although climate change represents a multifaceted challenge requiring comprehensive mitigation strategies, renewable energy adoption constitutes a viable mechanism for carbon emission reduction.",
                "Climate change is complex. We need many solutions. Renewable energy can help reduce carbon.",
                "synthetic",
            ),
            TrainingPair(
                "The experiment was conducted by the team using standardized protocols that had been previously validated.",
                "The team conducted the experiment. They used validated protocols.",
                "synthetic",
            ),
            TrainingPair(
                "The participants reviewed the lesson, and pagkatapos ay sinagot nila ang mga tanong sa worksheet.",
                "The participants reviewed the lesson. Then they answered the worksheet questions.",
                "synthetic",
            ),
            TrainingPair(
                "Students who struggle with reading comprehension, particularly those who have been diagnosed with dyslexia, benefit substantially from multisensory instructional techniques.",
                "Some students struggle with reading. Dyslexic students especially need help. Multisensory techniques work well.",
                "synthetic",
            ),
            TrainingPair(
                "Officials announced that the program, which was designed to reduce wait times and improve access, would begin operating next month.",
                "Officials said the program will start next month. It is meant to reduce wait times and improve access.",
                "synthetic",
            ),
            TrainingPair(
                "To configure the environment, edit the settings file, restart the service, and confirm that the health check returns a successful response.",
                "To set up the environment, edit the settings file. Restart the service. Then check that the health test passes.",
                "synthetic",
            ),
            TrainingPair(
                "The photosynthetic mechanism facilitates the conversion of photons into chemical energy via electron transfer chains.",
                "Plants use photosynthesis. Photosynthesis turns light into energy. This happens in plant cells.",
                "synthetic",
            ),
            TrainingPair(
                "The committee, after reviewing the voluminous reports submitted by various departments, reached a unanimous decision regarding the allocation of funds.",
                "The committee read many reports. They decided how to allocate the funds.",
                "synthetic",
            ),
            TrainingPair(
                "In order to optimize system performance, engineers implemented a series of iterative improvements that addressed both latency and throughput concerns.",
                "Engineers improved the system. They reduced delays and increased throughput.",
                "synthetic",
            ),
            TrainingPair(
                "The hypothesis was proven false after repeated trials failed to reproduce the initial results.",
                "Repeated trials failed to reproduce the initial results, so the hypothesis was proven false.",
                "synthetic",
            ),
            TrainingPair(
                "While numerous factors contribute to economic growth, investment in education remains a primary driver of long-term development.",
                "Many factors affect economic growth. Investing in education helps long-term development.",
                "synthetic",
            ),
            TrainingPair(
                "The algorithm leverages a combination of heuristics and probabilistic models to generate approximate solutions efficiently.",
                "The algorithm uses heuristics and probability models to find fast approximate solutions.",
                "synthetic",
            ),
            TrainingPair(
                "Given the complexity of the dataset, preprocessing steps such as normalization and outlier removal were necessary to ensure model stability.",
                "The dataset was complex. We normalized it and removed outliers to make the model stable.",
                "synthetic",
            ),
            TrainingPair(
                "The prevalence of ambiguous terms in the report required clarification to avoid misinterpretation by stakeholders.",
                "The report had ambiguous terms. We clarified them so stakeholders would not misinterpret the meaning.",
                "synthetic",
            ),
            TrainingPair(
                "In an effort to reduce cognitive load, the instructor presented the material in small, digestible segments with frequent summaries.",
                "To reduce cognitive load, the instructor used small segments and gave frequent summaries.",
                "synthetic",
            ),
            TrainingPair(
                "The synthesis of these compounds involves multiple reaction steps and precise temperature control to achieve the desired yield.",
                "Making these compounds requires several reaction steps and careful temperature control to get the desired yield.",
                "synthetic",
            ),
            TrainingPair(
                "The statistical analysis indicated a significant correlation between study time and performance metrics across the sample population.",
                "The analysis showed a strong link between study time and performance across the sample.",
                "synthetic",
            ),
            TrainingPair(
                "Researchers observed that participants exposed to multisensory cues demonstrated improved retention compared to the control group.",
                "Participants who received multisensory cues remembered more than the control group.",
                "synthetic",
            ),
            TrainingPair(
                "The project timeline was adjusted to accommodate additional quality assurance testing prior to deployment.",
                "We adjusted the timeline to add more quality assurance testing before deployment.",
                "synthetic",
            ),
            TrainingPair(
                "A comprehensive review of the literature revealed several gaps that warrant further investigation.",
                "A literature review found several gaps that need more research.",
                "synthetic",
            ),
            TrainingPair(
                "To facilitate bilingual comprehension, the materials included equivalent phrases in both Filipino and English where appropriate.",
                "To help bilingual readers, the materials included Filipino and English phrases when needed.",
                "synthetic",
            ),
            TrainingPair(
                "The software patch addresses critical security vulnerabilities identified during the audit.",
                "The software patch fixes important security problems found in the audit.",
                "synthetic",
            ),
            TrainingPair(
                "Despite the initial setback, the team implemented contingency plans that restored normal operations within hours.",
                "After the setback, the team used contingency plans and restored operations within hours.",
                "synthetic",
            ),
        ]
        return examples

    def collect_all_pairs(self, pair_file: Optional[Path] = None) -> List[TrainingPair]:
        pairs: List[TrainingPair] = []
        if pair_file:
            pairs.extend(self.load_pair_file(pair_file))

        # Keep synthetic examples so the model sees many task formats even when
        # the external dataset is small.
        pairs.extend(self.create_synthetic_pairs())
        self.pairs = [TrainingPair(f"{self.task_prefix} {p.original_text}".strip(), p.restructured_text, p.source) for p in pairs]
        logger.info("Prepared %d task-formatted training pairs", len(self.pairs))
        return self.pairs

    def get_train_test_split(self, test_size: float = 0.2):
        if not self.pairs:
            self.collect_all_pairs()

        split_idx = int(len(self.pairs) * (1 - test_size))
        return self.pairs[:split_idx], self.pairs[split_idx:]

    def save_training_data(self, format: str = "jsonl") -> Path:
        if not self.pairs:
            self.collect_all_pairs()

        if format == "jsonl":
            output_path = self.output_dir / "training_data.jsonl"
            with output_path.open("w", encoding="utf-8") as handle:
                for pair in self.pairs:
                    handle.write(json.dumps(asdict(pair), ensure_ascii=False) + "\n")
            return output_path

        if format == "csv":
            output_path = self.output_dir / "training_data.csv"
            with output_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["original_text", "restructured_text", "source"])
                writer.writeheader()
                for pair in self.pairs:
                    writer.writerow(asdict(pair))
            return output_path

        raise ValueError(f"Unsupported output format: {format}")
