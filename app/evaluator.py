import torch
import numpy as np

from selfcheckgpt.selfcheckgpt.modeling_selfcheck import SelfCheckNLI, SelfCheckBERTScore

class HallucinationEvaluator:
    def __init__(self, method: str = "nli"):
        if method not in ("nli", "bertscore"):
            raise ValueError(f"Unknown method: '{method}'. Choose 'nli' or 'bertscore'.")
        self.method = method
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[HallucinationEvaluator] Method: {method} | Device: {self.device}")

        
        # Load SpaCy for sentence segmentation. Done only once here
        import spacy
        self.nlp = spacy.load("en_core_web_sm")
        print("[HallucinationEvaluator] SpaCy model (en_core_web_sm) loaded successfully.")
 
        
        # Load the scoring model according to the selected method
        if method == "nli":
            # SelfCheckNLI will download the DeBERTa-v3-large model if it is not available locally
            self.scorer = SelfCheckNLI(device=self.device)
            print("[HallucinationEvaluator] DeBERTa model (SelfCheckNLI) loaded successfully.")
        else:
            self.scorer = SelfCheckBERTScore(rescale_with_baseline=True)
            print("[HallucinationEvaluator] BERTScore model loaded successfully.")
        
    def evaluate(self, main_answer: str, samples: list[str]) -> dict:
        """
        Calculate the hallucination score.
        High score = High probability of hallucination
        Low score = Factual
        """
        
        # Stage 1: Sentence segmentation from the main answer
        sentences = [sent.text.strip() for sent in self.nlp(main_answer).sents]
        print(f"[HallucinationEvaluator] Number of sentences: {len(sentences)} | Number of samples: {len(samples)}")
                
        # Stage 2: Calculate consistency score for each sentence
        # Both methods ('nli' and 'bertscore') use the same .predict() interface
        sentence_scores = self.scorer.predict(
            sentences=sentences,
            sampled_passages=samples
        )
        
        # Stage 3: Average score of all sentences to form the document score
        avg_score = float(np.mean(sentence_scores)) if len(sentence_scores) > 0 else 0.0
 
        return {
            "avg_score": avg_score,
            "sentence_scores": sentence_scores,
            "sentences": sentences,
        }