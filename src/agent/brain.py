import numpy as np
from typing import Dict, List, Any, Tuple
from datetime import datetime, timedelta
import logging
from pathlib import Path
import json
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

logger = logging.getLogger('AgentBrain')

class AgentBrain:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.memory = {
            'short_term': [],  # Recent events and observations
            'long_term': []    # Historical patterns and learned behaviors
        }
        self.performance_metrics = {}
        self.action_history = []
        self.load_brain_state()
        
    def load_brain_state(self):
        """Load previous brain state if exists"""
        brain_state_path = self.config_path / 'brain_state.json'
        if brain_state_path.exists():
            with open(brain_state_path, 'r') as f:
                state = json.load(f)
                self.memory['long_term'] = state.get('long_term_memory', [])
                self.performance_metrics = state.get('performance_metrics', {})
                self.action_history = state.get('action_history', [])

    def save_brain_state(self):
        """Persist brain state"""
        brain_state_path = self.config_path / 'brain_state.json'
        state = {
            'long_term_memory': self.memory['long_term'],
            'performance_metrics': self.performance_metrics,
            'action_history': self.action_history
        }
        with open(brain_state_path, 'w') as f:
            json.dump(state, f, indent=4)

    def analyze_data_quality(self, data: pd.DataFrame) -> Dict[str, float]:
        """Analyze the quality of collected data"""
        metrics = {
            'completeness': 1 - data.isnull().mean().mean(),
            'uniqueness': 1 - (data.duplicated().sum() / len(data)),
            'timeliness': self._calculate_timeliness(data),
            'consistency': self._check_data_consistency(data)
        }
        return metrics

    def _calculate_timeliness(self, data: pd.DataFrame) -> float:
        """Calculate how recent the data is"""
        if 'timestamp' not in data.columns:
            return 0.0
        
        now = datetime.now()
        max_age = timedelta(days=7)  # Consider data older than 7 days as stale
        
        timestamps = pd.to_datetime(data['timestamp'])
        ages = now - timestamps
        timeliness_scores = 1 - (ages / max_age).clip(0, 1)
        return float(timeliness_scores.mean())

    def _check_data_consistency(self, data: pd.DataFrame) -> float:
        """Check for data consistency across different metrics"""
        try:
            numeric_data = data.select_dtypes(include=[np.number])
            if numeric_data.empty:
                return 1.0
            
            # Use PCA to detect anomalies
            scaler = StandardScaler()
            scaled_data = scaler.fit_transform(numeric_data)
            pca = PCA()
            pca.fit(scaled_data)
            
            # Calculate reconstruction error
            transformed_data = pca.transform(scaled_data)
            reconstructed_data = pca.inverse_transform(transformed_data)
            reconstruction_error = np.mean(np.square(scaled_data - reconstructed_data))
            
            # Convert to consistency score (0-1)
            consistency = 1 / (1 + reconstruction_error)
            return float(consistency)
        except Exception as e:
            logger.error(f"Error checking data consistency: {str(e)}")
            return 0.0

    def evaluate_action(self, action: str, result: Dict[str, Any]) -> float:
        """Evaluate the success and impact of an action"""
        success = result.get('success', False)
        duration = result.get('duration', 0)
        
        # Calculate base score
        base_score = 1.0 if success else 0.0
        
        # Adjust for duration
        if success and duration > 0:
            expected_duration = self._get_expected_duration(action)
            time_score = 1.0 - min(max(duration - expected_duration, 0) / expected_duration, 1.0)
            base_score *= (0.7 + 0.3 * time_score)
        
        # Record action result
        self.action_history.append({
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'success': success,
            'score': base_score,
            'metadata': result
        })
        
        return base_score

    def _get_expected_duration(self, action: str) -> float:
        """Get expected duration for an action based on historical data"""
        relevant_actions = [a for a in self.action_history if a['action'] == action and a['success']]
        if not relevant_actions:
            return 60.0  # Default 60 seconds
        
        durations = [a['metadata'].get('duration', 60.0) for a in relevant_actions]
        return np.median(durations)

    def optimize_schedule(self, current_config: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize task scheduling based on historical performance"""
        if len(self.action_history) < 10:
            return current_config
        
        # Analyze success rates at different times
        hourly_success = self._analyze_hourly_success_rates()
        
        # Adjust collection interval based on data quality and success rates
        new_config = current_config.copy()
        base_interval = current_config.get('collection_interval_minutes', 30)
        
        # Calculate optimal interval
        success_rate = self._calculate_recent_success_rate()
        if success_rate < 0.5:
            # Increase interval if failing often
            new_interval = min(base_interval * 1.5, 120)
        elif success_rate > 0.9:
            # Decrease interval if very successful
            new_interval = max(base_interval * 0.8, 15)
        else:
            new_interval = base_interval
        
        new_config['collection_interval_minutes'] = int(new_interval)
        return new_config

    def _analyze_hourly_success_rates(self) -> Dict[int, float]:
        """Analyze success rates by hour"""
        hourly_stats = {}
        for action in self.action_history:
            hour = datetime.fromisoformat(action['timestamp']).hour
            if hour not in hourly_stats:
                hourly_stats[hour] = {'success': 0, 'total': 0}
            hourly_stats[hour]['total'] += 1
            if action['success']:
                hourly_stats[hour]['success'] += 1
        
        return {h: stats['success']/stats['total'] 
                for h, stats in hourly_stats.items() 
                if stats['total'] > 0}

    def _calculate_recent_success_rate(self) -> float:
        """Calculate success rate of recent actions"""
        recent_actions = self.action_history[-50:]  # Look at last 50 actions
        if not recent_actions:
            return 1.0
        
        return sum(1 for a in recent_actions if a['success']) / len(recent_actions)

    def suggest_improvements(self, metrics: Dict[str, Any]) -> List[str]:
        """Suggest improvements based on current metrics"""
        suggestions = []
        
        # Check data quality
        if metrics.get('data_quality', {}).get('completeness', 1.0) < 0.8:
            suggestions.append("Consider adding data validation to collection process")
        
        # Check performance
        success_rate = self._calculate_recent_success_rate()
        if success_rate < 0.7:
            suggestions.append("Review error logs and adjust collection strategy")
        
        # Check system health
        if metrics.get('system_health', {}).get('memory_usage', 0) > 0.9:
            suggestions.append("Consider increasing cleanup frequency")
        
        return suggestions

    def update_memory(self, event: Dict[str, Any]):
        """Update agent's memory with new events/observations"""
        self.memory['short_term'].append(event)
        
        # Keep short term memory limited
        if len(self.memory['short_term']) > 100:
            # Analyze patterns in short term memory before clearing
            self._analyze_and_store_patterns()
            self.memory['short_term'] = self.memory['short_term'][-50:]
        
        # Save state periodically
        if len(self.memory['short_term']) % 10 == 0:
            self.save_brain_state()

    def _analyze_and_store_patterns(self):
        """Analyze short term memory for patterns and store in long term memory"""
        if len(self.memory['short_term']) < 10:
            return
        
        # Group events by type
        event_types = {}
        for event in self.memory['short_term']:
            event_type = event.get('type', 'unknown')
            if event_type not in event_types:
                event_types[event_type] = []
            event_types[event_type].append(event)
        
        # Analyze patterns for each type
        for event_type, events in event_types.items():
            if len(events) < 5:
                continue
            
            pattern = {
                'event_type': event_type,
                'frequency': len(events) / len(self.memory['short_term']),
                'avg_success': sum(e.get('success', False) for e in events) / len(events),
                'timestamp': datetime.now().isoformat()
            }
            
            self.memory['long_term'].append(pattern)
        
        # Keep long term memory manageable
        if len(self.memory['long_term']) > 1000:
            self.memory['long_term'] = self.memory['long_term'][-1000:] 