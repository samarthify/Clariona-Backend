from typing import Dict, List, Any, Optional, Union
import logging
from pathlib import Path
import json
import requests
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
import torch
from huggingface_hub import login as hf_login
import os

logger = logging.getLogger('LLMProviders')

class LLMProvider:
    """Base class for LLM providers"""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.initialized = False

    async def generate(self, prompt: str) -> str:
        raise NotImplementedError

    def cleanup(self):
        pass

class HuggingFaceProvider(LLMProvider):
    """Provider for HuggingFace models"""
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.model = None
        self.tokenizer = None
        self.pipeline = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.initialize()

    def initialize(self):
        try:
            model_name = self.config.get("model_name", "TinyLlama/TinyLlama-1.1B-Chat-v1.0")
            
            # Login if token is provided
            if "hf_token" in self.config:
                hf_login(self.config["hf_token"])

            # Load in 8-bit if specified
            if self.config.get("use_8bit", True):
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    load_in_8bit=True,
                    device_map="auto",
                    torch_dtype=torch.float16
                )
            else:
                self.model = AutoModelForCausalLM.from_pretrained(model_name).to(self.device)

            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.pipeline = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device=self.device
            )
            self.initialized = True
            logger.info(f"Initialized HuggingFace model: {model_name}")
        except Exception as e:
            logger.error(f"Error initializing HuggingFace model: {str(e)}")
            raise

    async def generate(self, prompt: str) -> str:
        try:
            outputs = self.pipeline(
                prompt,
                max_length=self.config.get("max_length", 512),
                temperature=self.config.get("temperature", 0.7),
                num_return_sequences=1,
                pad_token_id=self.tokenizer.eos_token_id
            )
            return outputs[0]['generated_text'].replace(prompt, "").strip()
        except Exception as e:
            logger.error(f"Error generating text with HuggingFace: {str(e)}")
            return ""

    def cleanup(self):
        if self.model:
            del self.model
        if self.pipeline:
            del self.pipeline
        torch.cuda.empty_cache()

class OllamaProvider(LLMProvider):
    """Provider for Ollama models"""
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.model_name = config.get("model_name", "llama2")
        self.initialize()

    def initialize(self):
        try:
            # Check if Ollama is running and model is available
            response = requests.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                models = response.json()
                if not any(model["name"] == self.model_name for model in models.get("models", [])):
                    logger.warning(f"Model {self.model_name} not found in Ollama, attempting to pull...")
                    self._pull_model()
                self.initialized = True
                logger.info(f"Initialized Ollama with model: {self.model_name}")
        except Exception as e:
            logger.error(f"Error initializing Ollama: {str(e)}")
            raise

    def _pull_model(self):
        try:
            response = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": self.model_name}
            )
            if response.status_code != 200:
                raise Exception(f"Failed to pull model: {response.text}")
        except Exception as e:
            logger.error(f"Error pulling Ollama model: {str(e)}")
            raise

    async def generate(self, prompt: str) -> str:
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "temperature": self.config.get("temperature", 0.7),
                    "max_tokens": self.config.get("max_tokens", 500)
                }
            )
            if response.status_code == 200:
                return response.json()["response"]
            else:
                logger.error(f"Error from Ollama API: {response.text}")
                return ""
        except Exception as e:
            logger.error(f"Error generating text with Ollama: {str(e)}")
            return ""

class OpenAIProvider(LLMProvider):
    """Provider for OpenAI models (kept for compatibility)"""
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        import openai
        self.client = openai.OpenAI(api_key=config.get("api_key"))
        self.model = config.get("model", "gpt-4")
        self.initialized = True

    async def generate(self, prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.get("temperature", 0.7),
                max_tokens=self.config.get("max_tokens", 2000)
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating text with OpenAI: {str(e)}")
            return ""

class LLMProviderFactory:
    """Factory for creating LLM providers"""
    @staticmethod
    def create_provider(config_path: Path) -> LLMProvider:
        try:
            with open(config_path / "llm_config.json", "r") as f:
                config = json.load(f)
            
            provider_type = config.get("provider", "huggingface").lower()
            
            if provider_type == "huggingface":
                return HuggingFaceProvider(config)
            elif provider_type == "ollama":
                return OllamaProvider(config)
            elif provider_type == "openai":
                return OpenAIProvider(config)
            else:
                logger.error(f"Unknown provider type: {provider_type}")
                # Default to HuggingFace with TinyLlama
                return HuggingFaceProvider({
                    "model_name": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
                    "use_8bit": True
                })
        except Exception as e:
            logger.error(f"Error creating LLM provider: {str(e)}")
            # Fallback to HuggingFace with TinyLlama
            return HuggingFaceProvider({
                "model_name": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
                "use_8bit": True
            }) 
