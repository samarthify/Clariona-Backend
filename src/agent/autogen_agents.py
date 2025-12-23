from typing import Dict, List, Any, Optional
import autogen
from pathlib import Path
import logging
import json
import os
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd # Import pandas

logger = logging.getLogger('AutogenAgents')

class AutogenAgentSystem:
    def __init__(self, config_path: Path, llm_config: Optional[Dict[str, Any]] = None):
        self.config_path = config_path
        # Explicitly load .env file from the agent directory
        agent_env_path = Path(__file__).parent / '.env'
        if agent_env_path.exists():
            load_dotenv(dotenv_path=agent_env_path, override=True)
            logger.info(f"Loaded environment variables from {agent_env_path}")
        else:
             logger.warning(f"Agent-specific .env file not found at {agent_env_path}. Relying on system environment or other .env files.")
             
        self.latest_insights = []  # Store latest insights for email reporting
        self.llm_config = llm_config or self._get_default_llm_config()
        
        # Initialize the agent group
        self.assistant = self._create_assistant()
        self.researcher = self._create_researcher()
        self.data_analyst = self._create_data_analyst()
        self.critic = self._create_critic()
        
        # Create group chat
        self.group_chat = self._create_group_chat()
        
    def _get_default_llm_config(self) -> Dict[str, Any]:
        """Get default LLM configuration (adjusted for openai>=1.0)"""
        # Parameters like timeout, temperature are now typically expected within the config_list items
        config_list = self._load_config_list()
        # Return only the config_list as per newer autogen/openai patterns
        return {"config_list": config_list}

    def _load_config_list(self) -> List[Dict[str, Any]]:
        """Load API configurations, automatically adding OpenRouter if key is in env."""
        config_file = self.config_path / 'llm_config.json'
        allowed_keys = {"model", "api_key", "base_url", "api_type", "api_version", "max_tokens"}
        processed_config_list = []
        found_openrouter_in_file = False

        # Default parameters to merge
        default_params = {
            "timeout": 600,
            "temperature": 0.7
        }

        # 1. Process config file if it exists
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                config_list_from_file = config_data.get('config_list', [])

                for item in config_list_from_file:
                    raw_item = item.copy()
                    resolved_item = {}
                    # Resolve environment variables
                    for key, value in raw_item.items():
                        if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                            env_var = value[2:-1]
                            resolved_item[key] = os.getenv(env_var, value)
                        else:
                            resolved_item[key] = value

                    # Merge default params if missing
                    for dk, dv in default_params.items():
                        if dk not in resolved_item:
                             resolved_item[dk] = dv
                             
                    # Filter for allowed keys
                    filtered_item = {k: v for k, v in resolved_item.items() if k in allowed_keys}

                    # Check for required keys (model, api_key)
                    if "model" in filtered_item and "api_key" in filtered_item:
                        processed_config_list.append(filtered_item)
                        # Track if OpenRouter was explicitly configured
                        if "openrouter.ai" in filtered_item.get("base_url", ""):
                            found_openrouter_in_file = True
                    else:
                        logger.warning(f"Skipping config item from file due to missing model or api_key: {resolved_item}")
                        
            except json.JSONDecodeError:
                logger.error(f"Error decoding JSON from {config_file}. Proceeding without file config.", exc_info=True)
            except Exception as e:
                 logger.error(f"Error processing {config_file}: {e}. Proceeding without file config.", exc_info=True)
        else:
            logger.info(f"{config_file} not found. Checking environment variables for configuration.")

        # 2. Check for OPENROUTER_API_KEY environment variable
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if openrouter_key and not found_openrouter_in_file:
            logger.info("Found OPENROUTER_API_KEY environment variable. Adding OpenRouter config with free model.")
            openrouter_config = {
                "model": "google/gemma-3-4b-it:free",
                "api_key": openrouter_key,
                "base_url": "https://openrouter.ai/api/v1",
                **default_params # Add default params
            }
            filtered_openrouter_config = {k: v for k, v in openrouter_config.items() if k in allowed_keys}
            processed_config_list.append(filtered_openrouter_config)

        # 3. Fallback/Default: Check for standard OPENAI_API_KEY if no other configs were added
        openai_key = os.getenv("OPENAI_API_KEY")
        if not processed_config_list and openai_key:
             logger.info("No specific configs found, but OPENAI_API_KEY exists. Adding default OpenAI config.")
             default_openai_config = {
                 "model": "gpt-4", # Or another default OpenAI model
                 "api_key": openai_key,
                 **default_params
             }
             filtered_openai_config = {k: v for k, v in default_openai_config.items() if k in allowed_keys}
             processed_config_list.append(filtered_openai_config)
             
        # 4. Final fallback if absolutely nothing is configured
        if not processed_config_list:
            logger.error("CRITICAL: No LLM configuration found in file or environment variables (OPENROUTER_API_KEY, OPENAI_API_KEY). Autogen agents will likely fail.")
            # Return a dummy config to avoid immediate crashes, but log severity
            processed_config_list = [{
                "model": "placeholder_model",
                "api_key": "MISSING_API_KEY"
            }]

        logger.info(f"Final Autogen config_list: {[{k: (v[:5] + '...' if k == 'api_key' else v) for k,v in item.items()} for item in processed_config_list]}")
        return processed_config_list

    def _create_assistant(self) -> autogen.AssistantAgent:
        """Create the main assistant agent"""
        return autogen.AssistantAgent(
            name="assistant",
            system_message="""You are a highly capable AI assistant coordinating a sentiment analysis task.
            Your role is to manage the discussion between the researcher, data analyst, and critic.
            Ensure the team focuses SOLELY on the data sample and metadata provided in the initial prompt.
            DO NOT write or execute Python code for analysis. Rely on the analyst's findings.
            Summarize the final insights, data quality concerns, and recommendations derived from the provided data sample.""",
            llm_config=self.llm_config
        )

    def _create_researcher(self) -> autogen.AssistantAgent:
        """Create the researcher agent"""
        return autogen.AssistantAgent(
            name="researcher",
            system_message="""You are a data validation specialist.
            Your role is to examine the data sample and metadata provided in the initial prompt.
            Focus ONLY on the provided sample.
            Assess its apparent quality, consistency (e.g., date formats, sentiment scores vs labels), and potential completeness issues VISIBLE IN THE SAMPLE.
            Identify specific examples from the sample data to support your assessment.
            DO NOT write or execute Python code.""",
            llm_config=self.llm_config
        )

    def _create_data_analyst(self) -> autogen.AssistantAgent:
        """Create the data analyst agent"""
        return autogen.AssistantAgent(
            name="data_analyst",
            system_message="""You are a data analyst expert specializing in sentiment analysis.
            Your role is to analyze the data sample provided in the initial prompt.
            Focus ONLY on the provided sample.
            Identify sentiment patterns (e.g., trends by source, platform, or country based on the sample), and summarize key observations.
            Calculate simple statistics (like average sentiment) based ONLY on the sample data presented.
            DO NOT write or execute Python code. Perform your analysis based on reading the provided Markdown table.""",
            llm_config=self.llm_config
        )

    def _create_critic(self) -> autogen.AssistantAgent:
        """Create the critic agent"""
        return autogen.AssistantAgent(
            name="critic",
            system_message="""You are a critical reviewer of data analysis.
            Your role is to evaluate the analysis performed by the researcher and data analyst based ONLY on the data sample and metadata provided in the initial prompt.
            Identify potential limitations, biases, or misinterpretations evident *from the sample data*.
            Suggest alternative interpretations or necessary clarifications based *only on the sample*.
            DO NOT write or execute Python code.""",
            llm_config=self.llm_config
        )

    def _create_group_chat(self) -> autogen.GroupChat:
        """Create a group chat for agent collaboration"""
        return autogen.GroupChat(
            agents=[self.assistant, self.researcher, self.data_analyst, self.critic],
            messages=[],
            max_round=10
        )

    async def analyze_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform collaborative analysis using the agent group"""
        try:
            # Extract data and metadata
            records = data.get('data', [])
            metadata = data.get('metadata', {})
            record_count = len(records)
            
            # Prepare a sample of the data as a Markdown table string (first 50 rows)
            data_sample_str = "No data sample available." # Default message
            if records:
                sample_df = pd.DataFrame(records[:50]) # Create DataFrame from first 50 records
                # Select common/important columns to display (adjust as needed)
                cols_to_show = ['date', 'source', 'platform', 'text', 'sentiment_label', 'sentiment_score', 'country']
                existing_cols = [col for col in cols_to_show if col in sample_df.columns]
                if existing_cols:
                    # Truncate long text for display
                    if 'text' in existing_cols:
                        sample_df['text'] = sample_df['text'].str.slice(0, 100) + '...'
                    data_sample_str = sample_df[existing_cols].to_markdown(index=False)
                else:
                    data_sample_str = "Could not display relevant columns from data sample."
            
            # Create the initial message including the data sample
            initial_message = {
                "content": f"""Please analyze the following data based on the provided sample and metadata.
                
                Metadata:
                - Timestamp: {metadata.get('timestamp', 'N/A')}
                - Source Count: {metadata.get('source_count', 'N/A')}
                - Total Records: {metadata.get('total_records', record_count)}
                
                Data Sample (first 50 rows):
                ```markdown
                {data_sample_str}
                ```

                Please follow these steps:
                1. Researcher: Validate data quality and completeness based on the sample and metadata.
                2. Data Analyst: Perform sentiment analysis and pattern recognition based on the sample and metadata.
                3. Critic: Review findings and suggest improvements based on the sample and metadata.
                4. Assistant: Summarize key insights and recommendations based on the sample and metadata.""",
                "role": "user"
            }
            
            # Initialize the group chat manager
            manager = autogen.GroupChatManager(
                groupchat=self.group_chat,
                llm_config=self.llm_config
            )
            
            # Start the analysis
            result = manager.run(initial_message)
            logger.info("Autogen agent conversation for data analysis completed.")
            
            # Extract insights from the conversation history within the result object
            insights = self._extract_insights(result.chat_history if hasattr(result, 'chat_history') else [])
            
            return {
                "timestamp": datetime.now().isoformat(),
                "insights": insights,
                "raw_conversation": result.chat_history if hasattr(result, 'chat_history') else [] # Return history list
            }
            
        except Exception as e:
            logger.error(f"Error in collaborative analysis: {str(e)}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def _extract_insights(self, conversation: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract key insights, quality notes, and recommendations from the conversation"""
        insights = {
            "summary": [],
            "data_quality": [],
            "recommendations": []
        }
        temp_insights_set = set() # To avoid duplicates across categories initially
        
        # Extract insights from assistant responses
        for message in conversation:
            # Focus on messages from key agents, especially the final summary from assistant
            if message.get('name') in ['assistant', 'critic', 'researcher', 'data_analyst']:
                content = message.get('content', '').lower()
                lines = content.split('\n')
                current_section = "summary" # Default section

                for line in lines:
                    line_stripped = line.strip()
                    
                    # Detect section headers (simple heuristic)
                    if "quality" in line_stripped and len(line_stripped) < 50: # Avoid long lines being headers
                        current_section = "data_quality"
                        continue
                    if "recommend" in line_stripped and len(line_stripped) < 50:
                        current_section = "recommendations"
                        continue
                    if "summary" in line_stripped or "insight" in line_stripped or "finding" in line_stripped and len(line_stripped) < 50:
                        current_section = "summary"
                        continue
                        
                    # Check if line looks like an insight/point
                    if (line_stripped.startswith('- ') or line_stripped.startswith('* ') or line_stripped.startswith('•')):
                        clean_line = line_stripped.strip('- *•').strip()
                        
                        # Basic filtering and deduplication
                        if len(clean_line) > 10 and clean_line not in temp_insights_set:
                             # Assign to the detected section
                            if current_section in insights:
                                insights[current_section].append(clean_line)
                            else: # Fallback to summary
                                insights["summary"].append(clean_line)
                            temp_insights_set.add(clean_line)
        
        # Store a flat list of summary points for potential email reporting (can be adjusted)
        self.latest_insights = insights.get("summary", [])
        
        # Log extracted insights structure for debugging
        logger.debug(f"Extracted insights structure: {{summary: {len(insights['summary'])}, quality: {len(insights['data_quality'])}, recs: {len(insights['recommendations'])} }}")
        
        return insights # Return the dictionary

    def _parse_researcher_message(self, content: str) -> Dict[str, Any]:
        """Parse researcher's message for data quality insights"""
        # Implementation would depend on the expected format of researcher's messages
        return {
            "completeness": self._extract_metric(content, "completeness"),
            "validity": self._extract_metric(content, "validity"),
            "issues": self._extract_list(content, "issues")
        }

    def _parse_analyst_message(self, content: str) -> Dict[str, Any]:
        """Parse data analyst's message for sentiment analysis results"""
        return {
            "overall_sentiment": self._extract_metric(content, "overall sentiment"),
            "confidence": self._extract_metric(content, "confidence"),
            "patterns": self._extract_list(content, "patterns")
        }

    def _parse_critic_message(self, content: str) -> List[str]:
        """Parse critic's message for concerns and improvements"""
        return self._extract_list(content, "concerns")

    def _parse_assistant_message(self, content: str) -> List[str]:
        """Parse assistant's message for recommendations"""
        return self._extract_list(content, "recommendations")

    def _extract_metric(self, content: str, metric_name: str) -> float:
        """Extract a metric value from text content"""
        try:
            # This is a simple implementation - could be enhanced with better parsing
            lines = content.lower().split('\n')
            for line in lines:
                if metric_name.lower() in line:
                    # Try to find a number in the line
                    import re
                    numbers = re.findall(r"[-+]?\d*\.\d+|\d+", line)
                    if numbers:
                        return float(numbers[0])
            return 0.0
        except:
            return 0.0

    def _extract_list(self, content: str, section_name: str) -> List[str]:
        """Extract a list of items from text content"""
        items = []
        try:
            lines = content.lower().split('\n')
            capturing = False
            for line in lines:
                if section_name.lower() in line:
                    capturing = True
                    continue
                if capturing and line.strip():
                    # Remove common list markers and clean the line
                    clean_line = line.strip().lstrip('•-*').strip()
                    if clean_line:
                        items.append(clean_line)
                if capturing and not line.strip():
                    capturing = False
        except:
            pass
        return items

    async def optimize_collection(self, performance_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Use agents to optimize system based on high-level performance metrics."""
        try:
            # Prepare a summary of the metrics for the prompt
            metrics_summary = json.dumps(performance_metrics, indent=2, default=str)
            # Truncate if too long to avoid excessive prompt length
            if len(metrics_summary) > 3000:
                metrics_summary = metrics_summary[:3000] + "\n... (metrics truncated) ..."
                
            message = {
                "content": f"""Please analyze the following system performance metrics and suggest optimizations:
                ```json
                {metrics_summary}
                ```
                
                Consider potential improvements based ONLY on these high-level metrics. Focus on:
                1. Adjusting `collection_interval_minutes` (currently {performance_metrics.get('current_collection_interval_minutes')}) or `processing_interval_minutes` (currently {performance_metrics.get('current_processing_interval_minutes')}). Justify based on data freshness needs vs. processing time or observed sentiment stability.
                2. Suggesting general data quality checks if `latest_data_quality` indicates issues (e.g., low completeness).
                3. Highlighting potential bottlenecks if `overall_collection_status` shows long durations or failures.
                4. Briefly interpreting the `latest_sentiment_analysis` summary.
                
                Provide concise, actionable suggestions. Example output format for frequency:
                "Suggest changing collection_interval_minutes to 60 because..."
                If suggesting other changes, describe them briefly.
                DO NOT ask for granular per-source statistics as they are not available.""",
                "role": "user"
            }
            
            manager = autogen.GroupChatManager(
                groupchat=self.group_chat,
                llm_config=self.llm_config
            )
            
            result = manager.run(message)
            logger.info("Autogen agent conversation for optimization completed.")
            
            # Extract optimization suggestions from the conversation history within the result object
            optimizations = self._extract_optimizations(result.chat_history if hasattr(result, 'chat_history') else [])
            
            return {
                "timestamp": datetime.now().isoformat(),
                "optimizations": optimizations,
                "raw_conversation": result.chat_history if hasattr(result, 'chat_history') else [] # Return history list
            }
            
        except Exception as e:
            logger.error(f"Error in optimization analysis: {str(e)}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def _extract_optimizations(self, conversation: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract optimization suggestions from the agent conversation"""
        optimizations = {
            "collection_frequency": None,
            "resource_adjustments": [],
            "quality_improvements": [],
            "suggested_changes": []
        }
        
        for message in conversation:
            content = message["content"].lower()
            if "frequency" in content:
                optimizations["collection_frequency"] = self._extract_frequency(content)
            if "resource" in content:
                optimizations["resource_adjustments"].extend(self._extract_list(content, "resource"))
            if "quality" in content:
                optimizations["quality_improvements"].extend(self._extract_list(content, "quality"))
            if "suggest" in content or "recommend" in content:
                optimizations["suggested_changes"].extend(self._extract_list(content, "suggest"))
        
        return optimizations

    def _extract_frequency(self, content: str) -> Optional[int]:
        """Extract suggested collection frequency from text"""
        try:
            import re
            # Look for patterns like "every X minutes" or "X-minute interval"
            patterns = [
                r"every (\d+) minute",
                r"(\d+)[- ]minute interval",
                r"(\d+) min"
            ]
            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    return int(match.group(1))
            return None
        except:
            return None 