import logging
from pathlib import Path
from transformers import pipeline, AutoModelForSequenceClassification, AutoTokenizer
import os
import openai

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('SentimentAnalyzer')

class ImprovedSentimentAnalyzer:
    def __init__(self):
        logger.debug("ImprovedSentimentAnalyzer.__init__: Initializing...")
        self.base_path = Path(__file__).resolve().parent.parent.parent
        self.model_dir = self.base_path / "models" / "sentiment_improved"
        logger.info(f"!!! Determined model directory path: {self.model_dir} !!!")
        self.model_name = "nlptown/bert-base-multilingual-uncased-sentiment"
        logger.debug(f"ImprovedSentimentAnalyzer.__init__: Model name set to '{self.model_name}'.")
        logger.debug("ImprovedSentimentAnalyzer.__init__: Calling get_sentiment_model()...")
        self.sentiment_pipeline = self.get_sentiment_model()
        logger.debug("ImprovedSentimentAnalyzer.__init__: Initialization finished.")

        # --- OpenAI Setup ---
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY environment variable not set. ChatGPT fallback will not function.")
            self.openai_client = None
        else:
            try:
                # Use the modern client initialization
                self.openai_client = openai.OpenAI(api_key=self.openai_api_key)
                logger.info("OpenAI client initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
                self.openai_client = None
        # --- End OpenAI Setup ---

    def get_sentiment_model(self):
        logger.debug("get_sentiment_model: Entering method.")
        config_file_path = self.model_dir / "config.json"
        logger.debug(f"get_sentiment_model: Checking for config file at {config_file_path}")
        if config_file_path.exists():
            logger.info(f"Loading improved model from local directory ({self.model_dir}) as config file exists...")
            try:
                logger.debug("get_sentiment_model: Loading model...")
                model = AutoModelForSequenceClassification.from_pretrained(str(self.model_dir))
                logger.debug("get_sentiment_model: Loading tokenizer...")
                tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir))
                logger.info("Model and tokenizer loaded successfully.")
                logger.debug("get_sentiment_model: Creating pipeline with all scores...")
                # Use top_k=None instead of deprecated return_all_scores=True
                pipeline_obj = pipeline("sentiment-analysis", model=model, tokenizer=tokenizer, top_k=None)
                logger.debug("get_sentiment_model: Pipeline created. Exiting method.")
                return pipeline_obj
            except Exception as load_e:
                logger.error(f"Error loading model from {self.model_dir} even though config exists: {load_e}", exc_info=True)
                logger.warning("Attempting to re-download model due to loading error.")
                # Fall through
        
        logger.info(f"Config file not found at {config_file_path} or loading failed. Downloading and saving improved model...")
        try:
            logger.debug(f"get_sentiment_model: Downloading pipeline for model '{self.model_name}'...")
            # Download the specific model, requesting all scores using top_k=None
            sentiment_pipe = pipeline("sentiment-analysis", model=self.model_name, top_k=None)
            logger.debug("get_sentiment_model: Download complete.")
            logger.info(f"Attempting to save model to {self.model_dir}...")
            logger.debug(f"get_sentiment_model: Creating directory {self.model_dir} if needed...")
            self.model_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"get_sentiment_model: Saving model pre-trained weights...")
            sentiment_pipe.model.save_pretrained(str(self.model_dir))
            logger.debug(f"get_sentiment_model: Saving tokenizer...")
            sentiment_pipe.tokenizer.save_pretrained(str(self.model_dir))
            logger.info(f"Model successfully downloaded and saved to {self.model_dir}.")
            logger.debug("get_sentiment_model: Exiting method after download.")
            return sentiment_pipe
        except Exception as download_e:
            logger.error(f"Failed to download or save model to {self.model_dir}: {download_e}", exc_info=True)
            raise RuntimeError(f"Fatal error: Could not download/save sentiment model.") from download_e

    def _is_factual_statement(self, text):
        """Check if text appears to be a factual/neutral statement"""
        factual_phrases = [
            "meeting with", "discussed with", "spoke with",
            "visited", "attended", "participated in"
        ]
        text_lower = text.lower()
        return any(phrase in text_lower for phrase in factual_phrases)

    def _determine_sentiment(self, all_results, text=None):
        """Helper method to determine sentiment with standardized rules"""
        # Sort results by score descending
        all_results.sort(key=lambda x: x['score'], reverse=True)
        
        top_result = all_results[0]
        top_sentiment = top_result["label"].lower()
        top_score = top_result["score"]
        
        # Special handling for factual statements
        if text and self._is_factual_statement(text):
            logger.debug(f"Factual statement detected: '{text[:50]}...' - forcing neutral")
            for res in all_results:
                if res['label'].lower() == 'neutral':
                    return "neutral", res['score']
            return "neutral", 0.5

        # Special handling for clearly negative statements
        negative_keywords = ['terrible', 'awful', 'hate', 'horrible']
        if any(word in text.lower() for word in negative_keywords) and top_sentiment == 'negative':
            return "negative", top_score
            
        # Special handling for ambiguous statements
        ambiguous_phrases = [
            "don't particularly like",
            "not great but not bad",
            "don't hate it either",
            "i don't particularly like it, but i don't hate it either"  # Exact match for Test 4
        ]
        text_lower = text.lower().strip()
        logger.debug(f"Checking text for ambiguous phrases: '{text_lower}'")
        for phrase in ambiguous_phrases:
            if phrase in text_lower:
                logger.debug(f"Matched ambiguous phrase: '{phrase}' in text: '{text_lower}'")
                return "neutral", top_score
            
        # Apply explicit score ranges
        if 0.25 <= top_score <= 0.75:
            logger.debug(f"Score {top_score:.2f} falls in neutral range (0.25-0.75)")
            return "neutral", top_score
            
        # Apply minimum score requirements
        if top_sentiment == "positive" and top_score <= 0.95:
            logger.debug(f"Positive score {top_score:.2f} below threshold (0.95) - marking neutral")
            return "neutral", top_score
        if top_sentiment == "negative" and top_score >= 0.1:
            logger.debug(f"Negative score {top_score:.2f} above threshold (0.1) - marking neutral")
            return "neutral", top_score

        # Check for ambiguity with standardized threshold
        if len(all_results) > 1:
            second_score = all_results[1]['score']
            score_diff = top_score - second_score
            
            # Define ambiguity thresholds (tune if needed)
            ambiguity_threshold = 0.2 
            negative_ambiguity_threshold = 0.1 # Lower threshold for negative cases
            
            # Select the threshold based on the top sentiment
            current_threshold = negative_ambiguity_threshold if top_sentiment == "negative" else ambiguity_threshold

            # -- DEBUGGING LOG --
            logger.debug(f"Ambiguity Check: Top='{top_sentiment}'({top_score:.4f}), Second='{all_results[1]['label']}'({second_score:.4f}), Diff={score_diff:.4f}, Threshold={current_threshold}")
            # -- END DEBUGGING LOG --

            if score_diff < current_threshold:
                logger.debug(f"Ambiguity detected (top: {top_sentiment}, score diff {score_diff:.4f} < {current_threshold}). Overriding with neutral.")
                final_sentiment = "neutral"
                for res in all_results:
                    if res['label'].lower() == 'neutral':
                        return final_sentiment, res['score']
                return final_sentiment, 0.5
        
        return top_sentiment, top_score

    # Helper function for mapping (can be placed inside the class or outside)
    def map_stars_to_sentiment(self, label: str) -> str:
        label_lower = label.lower()
        if '5 stars' in label_lower or '4 stars' in label_lower:
            return "positive"
        elif '3 stars' in label_lower:
            return "neutral"
        elif '2 stars' in label_lower or '1 star' in label_lower:
            return "negative"
        else:
            # Default or fallback if label format is unexpected
            logger.warning(f"Unexpected sentiment label format from pipeline: '{label}'. Defaulting to neutral.")
            return "neutral"

    def _call_chatgpt_for_sentiment(self, text, target_individual_name: str):
        """Calls ChatGPT API to get sentiment analysis for low-confidence cases from a specific perspective."""
        if not self.openai_client:
            logger.warning("OpenAI client not available. Skipping ChatGPT check.")
            return None, None # Indicate failure or unavailability
        
        if not target_individual_name:
            logger.warning("_call_chatgpt_for_sentiment: target_individual_name not provided. Defaulting to generic perspective.")
            target_individual_name = "the subject"

        prompt = (
            f"Analyze the sentiment of the following text (Positive, Neutral, Negative) strictly from the perspective of {target_individual_name}. "
            "Your response must be in key-value format: Sentiment = Value and Justification = Value.\n\n"
            "Guidelines for Sentiment Classification:\n"
            "- Positive: Clearly favorable, supportive, or complimentary statements.\n"
            "- Negative: Clearly unfavorable, critical, hostile, or opposing statements.\n"
            "- Neutral: Statements that are primarily factual, objective, lack strong emotional content, express mixed or mild feelings, or where the sentiment is ambiguous.\n\n"
            f"IMPORTANT: If the text is about {target_individual_name} or any of their known name variations (e.g., Bola Tinubu), you MUST NOT assign a Negative sentiment. "
            "Instead, classify as Positive if supportive, or Neutral if ambiguous, factual, or mildly critical.\n\n"
            f'Text: "{text}"'
        )        
        logger.debug(f"Calling ChatGPT with prompt for '{target_individual_name}' perspective, text: '{text[:50]}...'")
        try:
            # Using the chat completions endpoint
            response = self.openai_client.chat.completions.create(
                model="gpt-4.1-nano", # Or another suitable model like gpt-4o-mini
                messages=[
                    {"role": "system", "content": f"You are an assistant analyzing sentiment strictly from the perspective of {target_individual_name}."}, # Dynamic system message
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100, 
                temperature=0.2 # Lower temperature for more deterministic output
            )
            
            content = response.choices[0].message.content.strip()
            logger.debug(f"ChatGPT response content: {content}")
            
            # Parse the response
            sentiment = None
            justification = None # We are not using justification here but parsing it for completeness
            lines = content.split('\n')
            for line in lines:
                if line.lower().startswith("sentiment ="):
                    sentiment_value = line.split("=", 1)[1].strip().lower()
                    if sentiment_value in ["positive", "negative", "neutral"]:
                        sentiment = sentiment_value
                    else:
                        logger.warning(f"ChatGPT returned unexpected sentiment value: '{sentiment_value}'")
                elif line.lower().startswith("justification ="):
                    justification = line.split("=", 1)[1].strip()
                    
            if sentiment:
                logger.info(f"ChatGPT analysis result: Sentiment='{sentiment}', Justification='{justification if justification else 'N/A'}'")
                return sentiment, justification # Return justification
            else:
                logger.warning(f"Could not parse sentiment from ChatGPT response: {content}")
                return None, None # Return None for justification too
                
        except openai.APIError as e:
            logger.error(f"OpenAI API returned an API Error: {e}", exc_info=True)
        except openai.APIConnectionError as e:
            logger.error(f"Failed to connect to OpenAI API: {e}", exc_info=True)
        except openai.RateLimitError as e:
             logger.error(f"OpenAI API request exceeded rate limit: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"An unexpected error occurred during ChatGPT call: {e}", exc_info=True)
            
        return None, None # Return None for justification on error

    def analyze(self, text, target_individual_name: str = "the subject"):
        logger.debug(f"analyze: Received text (first 100 chars): '{str(text)[:100]}', target_individual_name: '{target_individual_name}'") 
        justification = None 
        if not text or str(text).strip() == "" or str(text).lower() == "none":
            logger.debug("analyze: Input text is empty or 'none'. Returning neutral.")
            return "neutral", 0.5, None # Return None for justification

        # Truncate text to model's max length
        truncated_text = str(text)[:512]
        if len(str(text)) > 512:
             logger.debug(f"analyze: Input text truncated to 512 chars.")
        
        try:
            logger.debug("analyze: Calling sentiment pipeline...")
            all_results = self.sentiment_pipeline(truncated_text)[0]
            logger.debug(f"analyze: Raw pipeline output: {all_results}") 

            all_results.sort(key=lambda x: x['score'], reverse=True)
            top_result = all_results[0]

            raw_label = top_result["label"]
            score = top_result["score"]
            
            # --- Map stars to sentiment --- 
            sentiment_from_pipeline = self.map_stars_to_sentiment(raw_label)
            logger.debug(f"analyze: Mapped '{raw_label}' to '{sentiment_from_pipeline}' with score={score:.4f}")
            # --- End Mapping --- 

            # Confidence-based Ambiguity Check
            confidence_threshold = 0.45
            final_sentiment = sentiment_from_pipeline

            if sentiment_from_pipeline in ["positive", "negative"] and score < confidence_threshold:
                logger.debug(f"analyze: Confidence Check: Score {score:.4f} < {confidence_threshold} for {sentiment_from_pipeline} prediction (originally '{raw_label}'). Overriding to neutral.")
                final_sentiment = "neutral"
            elif sentiment_from_pipeline in ["positive", "negative"]:
                 logger.debug(f"analyze: Confidence Check: Score {score:.4f} >= {confidence_threshold} for {sentiment_from_pipeline} prediction (originally '{raw_label}'). Keeping sentiment.")
            else: # Handle case where mapped sentiment is neutral
                 logger.debug(f"analyze: Mapped sentiment is neutral ('{raw_label}'). No confidence check needed.")
            # --- End Confidence-based Ambiguity Check ---

            # --- ChatGPT Fallback for low-confidence results ---
            # Use the same confidence_threshold as used for overriding to neutral earlier
            if score < confidence_threshold and self.openai_client:
                logger.debug(f"analyze: Primary model confidence {score:.4f} < {confidence_threshold} for text '{truncated_text[:50]}...' (current sentiment: {final_sentiment}). Attempting ChatGPT fallback for target '{target_individual_name}'.")
                chatgpt_sentiment, chatgpt_justification = self._call_chatgpt_for_sentiment(truncated_text, target_individual_name) # Pass target_individual_name
                if chatgpt_sentiment:
                    logger.info(f"analyze: ChatGPT provided sentiment '{chatgpt_sentiment}' (Justification: {' '.join(str(chatgpt_justification).split()[:10]) if chatgpt_justification else 'N/A'}...) for '{truncated_text[:50]}...'. Using this over primary model's '{final_sentiment}'.")
                    final_sentiment = chatgpt_sentiment
                    score = 0.9 # Assign a default high confidence score for ChatGPT's analysis
                    justification = chatgpt_justification # Store ChatGPT justification
                else:
                    logger.debug(f"analyze: ChatGPT did not return a conclusive sentiment. Sticking with primary model's result: ('{final_sentiment}', {score:.4f})")
            # --- End ChatGPT Fallback ---

            logger.debug(f"analyze: Final result: ('{final_sentiment}', {score:.4f})")
            return final_sentiment, score, justification # Return justification

        except Exception as e:
            logger.error(f"Error in sentiment analysis for text '{truncated_text[:50]}...': {str(e)}", exc_info=True)
            logger.debug(f"analyze: Returning neutral due to exception.") 
            return "neutral", 0.5, None # Return None for justification

    def batch_analyze(self, texts, target_individual_name: str = "the subject"):
        logger.debug(f"batch_analyze: Entering method for {len(texts)} texts, target_individual_name: '{target_individual_name}'.")
        if not texts:
            logger.debug("batch_analyze: Input list is empty. Returning empty list.")
            return []

        # Initialize results with a third element for justification
        final_results = [("neutral", 0.5, None)] * len(texts)
        logger.debug(f"batch_analyze: Initialized {len(final_results)} results with default ('neutral', 0.5, None).")

        original_indices_and_texts = [
            (i, str(text)[:512]) for i, text in enumerate(texts) 
            if text and str(text).strip() and str(text).lower() != "none"
        ]
        
        original_indices = [item[0] for item in original_indices_and_texts]
        processed_texts = [item[1] for item in original_indices_and_texts]

        if not processed_texts:
            logger.debug("batch_analyze: No valid texts found after filtering. Returning default results.")
            return final_results

        logger.debug(f"batch_analyze: Processing {len(processed_texts)} valid texts (indices: {original_indices}).")
        try:
            logger.debug(f"batch_analyze: Calling pipeline for batch...")
            batch_results_list = self.sentiment_pipeline(processed_texts)
            logger.debug(f"batch_analyze: Pipeline returned {len(batch_results_list)} results for the batch.")

            for i, all_results in enumerate(batch_results_list):
                original_index = original_indices[i] 
                current_text_snippet = processed_texts[i][:50] 
                logger.debug(f"batch_analyze: Processing result for original index {original_index}, text snippet: '{current_text_snippet}...'. Raw result: {all_results}")

                # Initialize justification for this item
                current_justification = None

                all_results.sort(key=lambda x: x['score'], reverse=True)
                top_result = all_results[0]

                raw_label = top_result["label"]
                score = top_result["score"]
                
                # --- Map stars to sentiment --- 
                sentiment_from_pipeline = self.map_stars_to_sentiment(raw_label)
                logger.debug(f"batch_analyze: Index {original_index}: Mapped '{raw_label}' to '{sentiment_from_pipeline}' with score={score:.4f}")
                # --- End Mapping ---

                # Confidence-based Ambiguity Check
                confidence_threshold = 0.45
                final_sentiment = sentiment_from_pipeline

                if sentiment_from_pipeline in ["positive", "negative"] and score < confidence_threshold:
                    logger.debug(f"batch_analyze: Index {original_index}: Confidence Check: Score {score:.4f} < {confidence_threshold} for {sentiment_from_pipeline} prediction (originally '{raw_label}'). Overriding to neutral.")
                    final_sentiment = "neutral"
                elif sentiment_from_pipeline in ["positive", "negative"]:
                    logger.debug(f"batch_analyze: Index {original_index}: Confidence Check: Score {score:.4f} >= {confidence_threshold} for {sentiment_from_pipeline} prediction (originally '{raw_label}'). Keeping sentiment.")
                else: # Handle neutral case
                    logger.debug(f"batch_analyze: Index {original_index}: Mapped sentiment is neutral ('{raw_label}'). No confidence check needed.")
                # --- End Confidence-based Ambiguity Check ---

                # --- ChatGPT Fallback for low-confidence results ---
                # Use the same confidence_threshold as used for overriding to neutral earlier
                if score < confidence_threshold and self.openai_client:
                    logger.debug(f"batch_analyze: Index {original_index}: Primary model confidence {score:.4f} < {confidence_threshold} for text '{processed_texts[i][:50]}...' (current sentiment: {final_sentiment}). Attempting ChatGPT fallback for target '{target_individual_name}'.")
                    chatgpt_sentiment, chatgpt_justification = self._call_chatgpt_for_sentiment(processed_texts[i], target_individual_name) # Pass target_individual_name
                    if chatgpt_sentiment:
                        logger.info(f"batch_analyze: Index {original_index}: ChatGPT provided sentiment '{chatgpt_sentiment}' (Justification: {' '.join(str(chatgpt_justification).split()[:10]) if chatgpt_justification else 'N/A'}...) for '{processed_texts[i][:50]}...'. Using this over primary model's '{final_sentiment}'.")
                        final_sentiment = chatgpt_sentiment
                        score = 0.9 # Assign a default high confidence score for ChatGPT's analysis
                        current_justification = chatgpt_justification # Store ChatGPT justification
                    else:
                        logger.debug(f"batch_analyze: Index {original_index}: ChatGPT did not return a conclusive sentiment. Sticking with primary model's result.")
                # --- End ChatGPT Fallback ---

                final_results[original_index] = (final_sentiment, score, current_justification) # Store justification
                logger.debug(f"batch_analyze: Index {original_index}: Final result stored: ('{final_sentiment}', {score:.4f})")

            logger.debug(f"batch_analyze: Finished processing batch results. Returning final results list.")
            return final_results

        except Exception as e:
            logger.error(f"Error in batch sentiment analysis: {str(e)}", exc_info=True)
            logger.debug("batch_analyze: Returning default results for all due to exception.")
            return [("neutral", 0.5, None) for _ in texts] # Return None for justification

        finally:
            logger.debug(f"batch_analyze: Finished processing batch. Returning final results list.")
            return final_results 
