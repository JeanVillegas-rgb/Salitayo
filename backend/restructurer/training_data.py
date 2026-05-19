"""
Data preparation for fine-tuning the T5 model.

This module creates training pairs from corpus documents and example text
to train the model on dyslexia-friendly text restructuring.
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class TrainingPair:
    """A single training example."""
    original_text: str
    restructured_text: str
    source: str  # "corpus" or "synthetic"


class TrainingDataCollector:
    """Collects and formats training data from corpus and synthetic examples."""

    def __init__(self, corpus_dir: Path, output_dir: Path = None):
        self.corpus_dir = Path(corpus_dir)
        self.output_dir = Path(output_dir) if output_dir else self.corpus_dir.parent / "training_data"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.pairs: List[TrainingPair] = []

    def load_corpus_guidance(self) -> str:
        """Load dyslexia-friendly guidelines from corpus."""
        guidance_path = self.corpus_dir / "dyslexia_friendly_guidelines.md"
        if guidance_path.exists():
            return guidance_path.read_text(encoding="utf-8")
        return ""

    def create_synthetic_pairs(self) -> List[TrainingPair]:
        """Create synthetic training pairs based on dyslexia principles."""
        synthetic_examples = [
            # =========================
            # Academic simplification
            # =========================
            TrainingPair(
                original_text="The methodology employed in this study aims to examine the lived experiences of marginalized communities.",
                restructured_text="This study looks at the real experiences of people from disadvantaged communities.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The research highlights the significance of inclusive education in addressing social inequality.",
                restructured_text="The research shows that inclusive education can help reduce social inequality.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The findings indicate that poverty greatly influences students' academic performance.",
                restructured_text="The results show that poverty strongly affects how well students do in school.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The respondents demonstrated varying levels of awareness regarding environmental sustainability.",
                restructured_text="The respondents had different levels of knowledge about protecting the environment.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The implementation of the program resulted in measurable improvements in student participation.",
                restructured_text="The program helped students participate more.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="This study seeks to determine the relationship between technology use and academic achievement.",
                restructured_text="This study aims to find out how technology use affects school performance.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The data were analyzed to identify patterns in learner behavior.",
                restructured_text="The data were studied to find patterns in how learners behave.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The results suggest that parental involvement contributes to improved learning outcomes.",
                restructured_text="The results suggest that students learn better when parents are involved.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The participants expressed concerns regarding the accessibility of online learning platforms.",
                restructured_text="The participants were worried about how easy it is to access online learning platforms.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The intervention was designed to enhance learners' comprehension and engagement.",
                restructured_text="The activity was made to help learners understand better and stay interested.",
                source="synthetic"
            ),

            # =========================
            # Social issue / political simplification
            # =========================
            TrainingPair(
                original_text="Legislative decisions are dictated by corporate funding.",
                restructured_text="Business money influences lawmaking decisions.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="Marginalized sectors continue to experience systemic barriers to equal opportunities.",
                restructured_text="Disadvantaged groups still face unfair barriers to equal opportunities.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="Economic instability has intensified the struggles of low-income families.",
                restructured_text="Economic problems have made life harder for poor families.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="Government policies must address the needs of vulnerable communities.",
                restructured_text="Government policies should help communities that need support the most.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The unequal distribution of resources worsens social inequality.",
                restructured_text="When resources are not shared fairly, inequality becomes worse.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="Corruption undermines public trust in government institutions.",
                restructured_text="Corruption makes people lose trust in the government.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The lack of access to basic services contributes to persistent poverty.",
                restructured_text="People stay poor when they cannot access basic services.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="Powerful institutions often influence decisions that affect ordinary citizens.",
                restructured_text="Powerful groups often affect decisions that impact regular people.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The policy disproportionately affects individuals from low-income backgrounds.",
                restructured_text="The policy affects poor people more than others.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="Social exclusion prevents many individuals from fully participating in society.",
                restructured_text="Social exclusion stops many people from taking part in society.",
                source="synthetic"
            ),

            # =========================
            # Religious education / theology simplification
            # =========================
            TrainingPair(
                original_text="The Eucharist signifies the real presence of Christ among the faithful.",
                restructured_text="The Eucharist means that Christ is truly present with believers.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The celebration of the Holy Mass invites believers to participate in the sacrifice of Christ.",
                restructured_text="The Holy Mass invites believers to join in Christ's sacrifice.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The Church teaches that the Eucharist is the source and summit of Christian life.",
                restructured_text="The Church teaches that the Eucharist is the center of Christian life.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The Passover reminds the Jewish people of God's saving action in history.",
                restructured_text="The Passover reminds the Jewish people that God saved them in the past.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The Eucharistic celebration strengthens the unity of the Christian community.",
                restructured_text="The Eucharist helps Christians become more united.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The faithful are called to receive the Eucharist with reverence and gratitude.",
                restructured_text="Believers are called to receive the Eucharist with respect and thankfulness.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The liturgy allows the community to encounter God through prayer, scripture, and sacrament.",
                restructured_text="The liturgy helps the community meet God through prayer, the Bible, and the sacraments.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The Paschal Mystery refers to the suffering, death, and resurrection of Jesus Christ.",
                restructured_text="The Paschal Mystery means the suffering, death, and resurrection of Jesus Christ.",
                source="synthetic"
            ),

            # =========================
            # Technical / IT simplification
            # =========================
            TrainingPair(
                original_text="The system utilizes artificial intelligence to improve the accuracy of text classification.",
                restructured_text="The system uses AI to classify text more accurately.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The application was developed to provide users with a more accessible digital experience.",
                restructured_text="The app was made to give users an easier digital experience.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The backend handles data processing, authentication, and communication with the database.",
                restructured_text="The backend processes data, checks users, and connects to the database.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The frontend allows users to interact with the system through a visual interface.",
                restructured_text="The frontend lets users use the system through screens and buttons.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The proposed system aims to automate manual processes and reduce human error.",
                restructured_text="The proposed system aims to make manual work automatic and reduce mistakes.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="Computer vision can detect patterns in images and convert them into meaningful information.",
                restructured_text="Computer vision can find patterns in images and turn them into useful information.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The model requires sufficient training data to improve prediction accuracy.",
                restructured_text="The model needs enough training data to make better predictions.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The prototype demonstrates the feasibility of using AI for assistive technology.",
                restructured_text="The prototype shows that AI can be used for assistive technology.",
                source="synthetic"
            ),

            # =========================
            # Research proposal style
            # =========================
            TrainingPair(
                original_text="This study aims to develop an assistive device that supports blind learners in practicing Braille.",
                restructured_text="This study aims to create a device that helps blind learners practice Braille.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The proposed device provides tactile feedback to help users recognize Braille characters.",
                restructured_text="The device gives touch feedback to help users identify Braille characters.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The system is designed to enhance accessibility for visually impaired individuals.",
                restructured_text="The system is designed to make things easier for people with visual impairments.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The project addresses the limited availability of affordable Braille learning tools.",
                restructured_text="The project solves the lack of affordable tools for learning Braille.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The study contributes to inclusive education by supporting learners with special needs.",
                restructured_text="The study supports inclusive education by helping learners with special needs.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The device converts digital text into a tactile Braille output.",
                restructured_text="The device changes digital text into Braille that users can feel.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The system improves independent learning by allowing users to practice without constant assistance.",
                restructured_text="The system helps users practice on their own without always needing help.",
                source="synthetic"
            ),

            # =========================
            # Formal to simple sentences
            # =========================
            TrainingPair(
                original_text="It is necessary to consider the limitations of the current study.",
                restructured_text="It is important to look at the limits of this study.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The results provide evidence that the strategy was effective.",
                restructured_text="The results show that the strategy worked.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The issue requires immediate attention from concerned authorities.",
                restructured_text="The issue needs quick action from the proper authorities.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The community experienced difficulties due to the lack of available resources.",
                restructured_text="The community had problems because they did not have enough resources.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The project was created in response to the needs of the target users.",
                restructured_text="The project was made to answer the needs of the target users.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The study emphasizes the importance of user-centered design.",
                restructured_text="The study shows why designing for users is important.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The implementation phase involved testing, evaluation, and revision.",
                restructured_text="The implementation phase included testing, checking, and improving the system.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The researchers gathered data through interviews and observation.",
                restructured_text="The researchers collected data by interviewing and observing people.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The concept was developed to address communication barriers.",
                restructured_text="The idea was made to solve communication problems.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The solution provides a practical approach to improving accessibility.",
                restructured_text="The solution gives a practical way to improve accessibility.",
                source="synthetic"
            ),

            # =========================
            # Hard words simplification
            # =========================
            TrainingPair(
                original_text="The phenomenon illustrates the complexity of human behavior.",
                restructured_text="This situation shows how complex human behavior can be.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The initiative promotes collaboration among different stakeholders.",
                restructured_text="The project encourages different groups to work together.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The assessment revealed significant gaps in service delivery.",
                restructured_text="The assessment showed major problems in providing services.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The organization seeks to empower disadvantaged individuals.",
                restructured_text="The organization wants to help disadvantaged people become stronger and more independent.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The framework guides the development and evaluation of the system.",
                restructured_text="The framework guides how the system is built and checked.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The analysis shows a correlation between income level and access to education.",
                restructured_text="The analysis shows a connection between income and access to education.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The strategy was implemented to mitigate the negative effects of the problem.",
                restructured_text="The strategy was used to reduce the bad effects of the problem.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The intervention improved the participants' ability to understand complex information.",
                restructured_text="The activity helped the participants understand difficult information better.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The approach encourages active participation from the community.",
                restructured_text="The approach encourages the community to take part.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The study investigates the factors that influence student motivation.",
                restructured_text="The study looks at the things that affect student motivation.",
                source="synthetic"
            ),

            # =========================
            # Presentation explanation style
            # =========================
            TrainingPair(
                original_text="Our system is a ground-up web application developed to maximize client flexibility.",
                restructured_text="Our system is a web application made from scratch to better fit the client's needs.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The project overview explains the main purpose, users, and functions of the system.",
                restructured_text="The project overview explains what the system is for, who uses it, and what it can do.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="As the project manager, I coordinated the team, assigned tasks, and monitored the development progress.",
                restructured_text="As the project manager, I organized the team, gave tasks, and checked our progress.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The main challenge was ensuring that all parts of the system worked together properly.",
                restructured_text="The main challenge was making sure all parts of the system worked well together.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The validation process ensures that the system meets the required functions and user expectations.",
                restructured_text="The validation process checks if the system works as needed and meets user expectations.",
                source="synthetic"
            ),

            # =========================
            # More complex academic examples
            # =========================
            TrainingPair(
                original_text="The increasing dependence on digital platforms has transformed the way individuals communicate and access information.",
                restructured_text="People now rely more on digital platforms, which has changed how they communicate and get information.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The study explores how technological innovation can address barriers experienced by persons with disabilities.",
                restructured_text="The study looks at how new technology can help remove barriers for people with disabilities.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="Limited access to assistive devices prevents many learners from fully participating in educational activities.",
                restructured_text="Many learners cannot fully join school activities because they do not have assistive devices.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The research emphasizes the need for affordable, accessible, and user-friendly learning tools.",
                restructured_text="The research shows the need for learning tools that are affordable, accessible, and easy to use.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The proposed innovation aims to bridge the gap between traditional learning methods and modern assistive technology.",
                restructured_text="The proposed innovation connects traditional learning with modern assistive technology.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The effectiveness of the system depends on the accuracy of its detection and feedback mechanisms.",
                restructured_text="The system works well if its detection and feedback are accurate.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The study contributes to the development of inclusive technologies that support independent learning.",
                restructured_text="The study helps create inclusive technologies that support independent learning.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The system was evaluated based on usability, accuracy, reliability, and user satisfaction.",
                restructured_text="The system was checked based on ease of use, accuracy, reliability, and user satisfaction.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The proposed solution responds to the need for more accessible educational resources.",
                restructured_text="The proposed solution answers the need for easier access to educational resources.",
                source="synthetic"
            ),
            TrainingPair(
                original_text="The results may serve as a basis for future improvements and further development.",
                restructured_text="The results can be used to improve and develop the system further.",
                source="synthetic"
            ),
        ]
        return synthetic_examples
        return synthetic_examples

    def load_corpus_documents(self) -> List[TrainingPair]:
        """Load markdown documents from corpus as reference."""
        pairs = []
        if self.corpus_dir.exists():
            for path in self.corpus_dir.glob("*.md"):
                if path.name != "dyslexia_friendly_guidelines.md":
                    content = path.read_text(encoding="utf-8")
                    # Split by sections and use as examples
                    sections = content.split("##")
                    for i, section in enumerate(sections[1:]):  # Skip title
                        lines = section.strip().split("\n")
                        if len(lines) > 2:
                            # Use section as reference for restructuring principles
                            pairs.append(
                                TrainingPair(
                                    original_text=section.strip(),
                                    restructured_text="\n".join(lines[:3]),  # Simplified version
                                    source="corpus"
                                )
                            )
        return pairs

    def collect_all_pairs(self) -> List[TrainingPair]:
        """Collect all training pairs."""
        logger.info("Collecting training data...")

        # Get synthetic examples
        synthetic = self.create_synthetic_pairs()
        logger.info(f"Created {len(synthetic)} synthetic training pairs")

        # Get corpus examples
        corpus_based = self.load_corpus_documents()
        logger.info(f"Created {len(corpus_based)} corpus-based training pairs")

        self.pairs = synthetic + corpus_based
        logger.info(f"Total training pairs: {len(self.pairs)}")
        return self.pairs

    def save_training_data(self, format: str = "jsonl") -> Path:
        """Save training data to disk."""
        if not self.pairs:
            self.collect_all_pairs()

        if format == "jsonl":
            output_path = self.output_dir / "training_data.jsonl"
            with open(output_path, "w", encoding="utf-8") as f:
                for pair in self.pairs:
                    f.write(json.dumps(asdict(pair)) + "\n")
            logger.info(f"Saved training data to {output_path}")
            return output_path

        elif format == "txt":
            output_path = self.output_dir / "training_pairs.txt"
            with open(output_path, "w", encoding="utf-8") as f:
                for i, pair in enumerate(self.pairs, 1):
                    f.write(f"=== Pair {i} ===\n")
                    f.write(f"Source: {pair.source}\n")
                    f.write(f"Original:\n{pair.original_text}\n\n")
                    f.write(f"Restructured:\n{pair.restructured_text}\n\n")
            logger.info(f"Saved training pairs to {output_path}")
            return output_path

        return None

    def get_train_test_split(self, test_size: float = 0.2):
        """Get train/test split of data."""
        if not self.pairs:
            self.collect_all_pairs()

        split_idx = int(len(self.pairs) * (1 - test_size))
        train = self.pairs[:split_idx]
        test = self.pairs[split_idx:]

        logger.info(f"Train set: {len(train)}, Test set: {len(test)}")
        return train, test
