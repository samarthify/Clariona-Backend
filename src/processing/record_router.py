"""
Record router for splitting records across multiple parallel pipelines.
Supports 4 models: gpt-5-mini, gpt-5-nano, gpt-4.1-mini, gpt-4.1-nano
"""

import logging
import random
from typing import List, Tuple, Dict, Any

logger = logging.getLogger('RecordRouter')

class RecordRouter:
    """
    Routes records across multiple parallel pipelines.
    Splits records evenly across available models.
    """
    
    def __init__(self, models: List[str] = None):
        """
        Initialize the record router.
        
        Args:
            models: List of models to use. Defaults to all 4 models.
        """
        if models is None:
            self.models = ["gpt-5-mini", "gpt-5-nano", "gpt-4.1-mini", "gpt-4.1-nano"]
        else:
            self.models = models
        
        # TPM capacity for each model (for capacity-based routing)
        self.model_capacities = {
            "gpt-5-mini": 500000,  # 500k TPM
            "gpt-5-nano": 200000,  # 200k TPM
            "gpt-4.1-mini": 200000,  # 200k TPM
            "gpt-4.1-nano": 200000,  # 200k TPM
        }
        
        # Calculate routing weights based on TPM capacity
        self._calculate_routing_weights()
        
        logger.info(f"RecordRouter initialized with {len(self.models)} models: {self.models}")
        logger.info(f"Routing weights: {self.routing_weights}")
    
    def _calculate_routing_weights(self):
        """Calculate routing weights based on TPM capacity."""
        total_capacity = sum(self.model_capacities.get(model, 200000) for model in self.models)
        self.routing_weights = {}
        self.routing_cumulative = []
        cumulative = 0.0
        
        for model in self.models:
            capacity = self.model_capacities.get(model, 200000)
            weight = capacity / total_capacity
            self.routing_weights[model] = weight
            cumulative += weight
            self.routing_cumulative.append((cumulative, model))
        
        logger.debug(f"Routing weights calculated: {self.routing_weights}")
    
    def route_records(self, texts: List[str], source_types: List[str] = None) -> Dict[str, List[Tuple[int, str, str]]]:
        """
        Route records across pipelines.
        
        Args:
            texts: List of text strings to route
            source_types: Optional list of source types (must match texts length)
        
        Returns:
            Dictionary mapping model names to lists of (index, text, source_type) tuples
        """
        if not texts:
            return {model: [] for model in self.models}
        
        if source_types is None:
            source_types = [None] * len(texts)
        elif len(source_types) != len(texts):
            logger.warning(f"source_types length ({len(source_types)}) doesn't match texts length ({len(texts)}). Padding with None.")
            source_types = source_types + [None] * (len(texts) - len(source_types))
        
        # Split records across models using capacity-based routing (weighted distribution)
        routed = {model: [] for model in self.models}
        
        for idx, (text, source_type) in enumerate(zip(texts, source_types)):
            # Capacity-based assignment: use weighted random based on TPM capacity
            rand = random.random()  # 0.0 to 1.0
            
            # Find which model this record should go to based on cumulative weights
            model = self.models[0]  # Default to first model
            for threshold, m in self.routing_cumulative:
                if rand <= threshold:
                    model = m
                    break
            
            routed[model].append((idx, text, source_type))
        
        # Log distribution
        for model, records in routed.items():
            logger.debug(f"Routed {len(records)} records to {model} pipeline")
        
        total_routed = sum(len(records) for records in routed.values())
        logger.info(f"Routed {total_routed} records across {len(self.models)} pipelines")
        
        return routed
    
    def merge_results(self, routed_results: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Merge results from multiple pipelines back into original order.
        
        Args:
            routed_results: Dictionary mapping model names to lists of (index, result) tuples
        
        Returns:
            List of results in original order
        """
        # Flatten all results with their original indices
        all_results = []
        for model, results in routed_results.items():
            for result_tuple in results:
                if isinstance(result_tuple, tuple) and len(result_tuple) == 2:
                    idx, result = result_tuple
                    all_results.append((idx, result))
                else:
                    # If results don't have indices, we can't merge properly
                    logger.warning(f"Results from {model} don't have indices, cannot merge properly")
                    return []
        
        # Sort by original index
        all_results.sort(key=lambda x: x[0])
        
        # Extract just the results
        merged = [result for _, result in all_results]
        
        logger.info(f"Merged {len(merged)} results from {len(routed_results)} pipelines")
        return merged

