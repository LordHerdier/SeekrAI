import os
import yaml
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Union


def _get_project_root():
    """Get the project root directory.
    
    Returns:
        Path: The project root directory path (parent of src/).
    """
    # Get the directory containing this config_loader.py file (src/)
    current_dir = Path(__file__).parent
    # Go up one level to get the project root
    return current_dir.parent


def _substitute_env_vars(value):
    """Substitute environment variables in a string value.
    
    Supports ${VAR:-default}, ${VAR}, and $VAR syntax for environment variable
    substitution with optional default values.
    
    Args:
        value: The value to process. If not a string, returns unchanged.
        
    Returns:
        The value with environment variables substituted, or original value
        if not a string.
    """
    if not isinstance(value, str):
        return value
    
    # Pattern to match ${VAR:-default} or ${VAR} or $VAR
    pattern = r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)'
    
    def replace_match(match):
        if match.group(1):  # ${...} format
            var_expr = match.group(1)
            if ':-' in var_expr:
                # Handle ${VAR:-default} syntax
                var_name, default_value = var_expr.split(':-', 1)
                return os.environ.get(var_name.strip(), default_value)
            else:
                # Handle ${VAR} syntax
                var_name = var_expr.strip()
                return os.environ.get(var_name, '')
        elif match.group(2):  # $VAR format
            var_name = match.group(2)
            return os.environ.get(var_name, '')
        return match.group(0)
    
    return re.sub(pattern, replace_match, value)


def _process_config_recursively(config_data):
    """Recursively process configuration data to substitute environment variables.
    
    Args:
        config_data: The configuration data to process (dict, list, or scalar).
        
    Returns:
        The processed configuration data with environment variables substituted.
    """
    if isinstance(config_data, dict):
        return {key: _process_config_recursively(value) for key, value in config_data.items()}
    elif isinstance(config_data, list):
        return [_process_config_recursively(item) for item in config_data]
    elif isinstance(config_data, str):
        return _substitute_env_vars(config_data)
    else:
        return config_data


class ConfigLoader:
    """Configuration loader for SeekrAI application.
    
    Loads configuration from YAML file with environment variable overrides
    and provides convenient access methods for configuration values.
    """
    
    def __init__(self, config_file: str = None):
        """Initialize the configuration loader.
        
        Args:
            config_file (str, optional): Path to the YAML configuration file.
                If None, defaults to config/config.yaml relative to project root.
        """
        if config_file is None:
            # Default to config/config.yaml relative to project root
            project_root = _get_project_root()
            config_file = project_root / "config" / "config.yaml"
        
        self.config_file = Path(config_file)
        self._config = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from YAML file.
        
        Raises:
            FileNotFoundError: If the configuration file does not exist.
            ValueError: If the YAML file contains invalid syntax.
            RuntimeError: If the configuration fails to load for other reasons.
        """
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                raw_config = yaml.safe_load(f) or {}
            
            # Process environment variable substitution
            self._config = _process_config_recursively(raw_config)
            
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML configuration file: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration: {e}")
    
    def save_config(self) -> None:
        """Save current configuration to YAML file.
        
        Creates a backup of the existing configuration file before saving.
        
        Raises:
            RuntimeError: If the configuration fails to save.
        """
        try:
            # Create backup of current config
            backup_file = self.config_file.with_suffix('.yaml.backup')
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as src:
                    with open(backup_file, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
            
            # Save current configuration
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self._config, f, default_flow_style=False, indent=2, sort_keys=False)
                
            logging.info(f"Configuration saved to {self.config_file}")
            
        except Exception as e:
            raise RuntimeError(f"Failed to save configuration: {e}")
    
    def set(self, key_path: str, value: Any) -> None:
        """Set configuration value using dot-separated path.
        
        Creates nested dictionaries as needed if intermediate keys don't exist.
        
        Args:
            key_path (str): Dot-separated path to configuration value (e.g., 'app.debug').
            value (Any): Value to set.
        """
        keys = key_path.split('.')
        current = self._config
        
        # Navigate to the parent of the final key
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            elif not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        
        # Set the final value
        current[keys[-1]] = value
    
    def update_multiple(self, updates: Dict[str, Any]) -> None:
        """Update multiple configuration values at once.
        
        Args:
            updates (Dict[str, Any]): Dictionary mapping key paths to new values.
        """
        for key_path, value in updates.items():
            self.set(key_path, value)
    
    def get_all_config(self) -> Dict:
        """Get the complete configuration dictionary.
        
        Returns:
            Dict: A copy of the complete configuration dictionary.
        """
        return self._config.copy()
    
    def get_config_sections(self) -> List[str]:
        """Get list of top-level configuration sections.
        
        Returns:
            List[str]: List of top-level configuration section names.
        """
        return list(self._config.keys())
    
    def get(self, key_path: str, default: Any = None, env_override: str = None) -> Any:
        """Get configuration value with optional environment variable override.
        
        Environment variable override takes precedence over configuration file values.
        
        Args:
            key_path (str): Dot-separated path to configuration value (e.g., 'app.debug').
            default (Any, optional): Default value if key is not found.
            env_override (str, optional): Environment variable name to check for override.
            
        Returns:
            Any: Configuration value, environment override, or default value.
        """
        # Check environment variable override first
        if env_override and env_override in os.environ:
            env_value = os.environ[env_override]
            # Try to convert to appropriate type
            return self._convert_env_value(env_value)
        
        # Navigate through nested configuration
        current = self._config
        keys = key_path.split('.')
        
        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default
    
    def _convert_env_value(self, value: str) -> Union[str, int, float, bool]:
        """Convert environment variable string to appropriate type.
        
        Attempts to convert string values to boolean, integer, float, or keeps as string.
        
        Args:
            value (str): The environment variable string value.
            
        Returns:
            Union[str, int, float, bool]: The converted value.
        """
        # Boolean conversion
        if value.lower() in ('true', 'yes', '1', 'on'):
            return True
        elif value.lower() in ('false', 'no', '0', 'off'):
            return False
        
        # Number conversion
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # Return as string
        return value
    
    def get_list(self, key_path: str, default: List = None, env_override: str = None) -> List:
        """Get configuration list with optional environment variable override.
        
        Environment variables should be comma-separated values.
        
        Args:
            key_path (str): Dot-separated path to configuration value.
            default (List, optional): Default list if key is not found.
            env_override (str, optional): Environment variable name for comma-separated override.
            
        Returns:
            List: Configuration list value or default.
        """
        if env_override and env_override in os.environ:
            env_value = os.environ[env_override]
            return [item.strip() for item in env_value.split(',') if item.strip()]
        
        return self.get(key_path, default or [])
    
    def get_dict(self, key_path: str, default: Dict = None) -> Dict:
        """Get configuration dictionary.
        
        Args:
            key_path (str): Dot-separated path to configuration value.
            default (Dict, optional): Default dictionary if key is not found.
            
        Returns:
            Dict: Configuration dictionary value or default.
        """
        return self.get(key_path, default or {})
    
    def reload(self) -> None:
        """Reload configuration from file.
        
        Re-reads and processes the configuration file, updating the internal state.
        """
        self._load_config()
    
    def validate_required_keys(self, required_keys: List[str]) -> List[str]:
        """Validate that required configuration keys exist.
        
        Args:
            required_keys (List[str]): List of required key paths.
            
        Returns:
            List[str]: List of missing key paths.
        """
        missing_keys = []
        for key in required_keys:
            if self.get(key) is None:
                missing_keys.append(key)
        return missing_keys
    
    # Convenience methods for common configuration access patterns
    
    @property
    def app_config(self) -> Dict:
        """Get application configuration.
        
        Returns:
            Dict: Application configuration section.
        """
        return self.get_dict('app')
    
    @property
    def file_config(self) -> Dict:
        """Get file management configuration.
        
        Returns:
            Dict: File management configuration section.
        """
        return self.get_dict('files')
    
    @property
    def logging_config(self) -> Dict:
        """Get logging configuration.
        
        Returns:
            Dict: Logging configuration section.
        """
        return self.get_dict('logging')
    
    @property
    def openai_config(self) -> Dict:
        """Get OpenAI configuration.
        
        Returns:
            Dict: OpenAI configuration section.
        """
        return self.get_dict('openai')
    
    @property
    def cache_config(self) -> Dict:
        """Get cache configuration.
        
        Returns:
            Dict: Cache configuration section.
        """
        return self.get_dict('cache')
    
    @property
    def job_search_config(self) -> Dict:
        """Get job search configuration.
        
        Returns:
            Dict: Job search configuration section.
        """
        return self.get_dict('job_search')
    
    @property
    def resume_processing_config(self) -> Dict:
        """Get resume processing configuration.
        
        Returns:
            Dict: Resume processing configuration section.
        """
        return self.get_dict('resume_processing')
    
    @property
    def cleanup_config(self) -> Dict:
        """Get cleanup configuration.
        
        Returns:
            Dict: Cleanup configuration section.
        """
        return self.get_dict('cleanup')
    
    @property
    def ui_config(self) -> Dict:
        """Get UI configuration.
        
        Returns:
            Dict: UI configuration section.
        """
        return self.get_dict('ui')
    
    @property
    def development_config(self) -> Dict:
        """Get development configuration.
        
        Returns:
            Dict: Development configuration section.
        """
        return self.get_dict('development')
    
    @property
    def security_config(self) -> Dict:
        """Get security configuration.
        
        Returns:
            Dict: Security configuration section.
        """
        return self.get_dict('security')
    
    # Specific getters with environment overrides for common values
    
    def get_secret_key(self) -> str:
        """Get Flask secret key with environment override.
        
        Returns:
            str: Flask secret key from config or SECRET_KEY environment variable.
        """
        return self.get('app.secret_key', env_override='SECRET_KEY')
    
    def get_openai_api_key(self) -> str:
        """Get OpenAI API key from environment.
        
        Returns:
            str: OpenAI API key from OPENAI_API_KEY environment variable.
        """
        return os.environ.get('OPENAI_API_KEY', '')
    
    def get_upload_folder(self) -> str:
        """Get upload folder path.
        
        Returns:
            str: Upload folder path, defaults to 'uploads'.
        """
        return self.get('files.upload_folder', 'uploads')
    
    def get_max_file_size_bytes(self) -> int:
        """Get maximum file size in bytes.
        
        Returns:
            int: Maximum file size in bytes (converts from MB configuration).
        """
        mb = self.get('files.max_file_size_mb', 16)
        return mb * 1024 * 1024
    
    def get_allowed_extensions(self) -> set:
        """Get allowed file extensions as a set.
        
        Returns:
            set: Set of allowed file extensions.
        """
        extensions = self.get_list('files.allowed_extensions', ['txt', 'pdf', 'docx', 'doc'])
        return set(extensions)
    
    def get_cache_directory(self) -> str:
        """Get cache directory path.
        
        Returns:
            str: Cache directory path, defaults to '.cache'.
        """
        return self.get('cache.directory', '.cache')
    
    def get_cache_expiration_days(self) -> int:
        """Get cache expiration in days.
        
        Returns:
            int: Cache expiration in days, defaults to 7.
        """
        return self.get('cache.expiration_days', 7)
    
    def get_openai_model(self) -> str:
        """Get OpenAI model name.
        
        Returns:
            str: OpenAI model name, defaults to 'gpt-3.5-turbo'.
        """
        return self.get('openai.model', 'gpt-3.5-turbo')
    
    def get_openai_temperature(self) -> float:
        """Get OpenAI temperature setting.
        
        Returns:
            float: OpenAI temperature setting, defaults to 0.3.
        """
        return self.get('openai.temperature', 0.3)
    
    def get_job_search_sites(self) -> List[str]:
        """Get default job search sites.
        
        Returns:
            List[str]: List of default job search sites.
        """
        return self.get_list('job_search.default_sites', ['indeed', 'linkedin'])
    
    def get_default_job_results(self) -> int:
        """Get default number of job results.
        
        Returns:
            int: Default number of job results, defaults to 10.
        """
        return self.get('job_search.default_results', 10)
    
    def get_job_hours_old(self) -> int:
        """Get job search hours old filter.
        
        Returns:
            int: Job search hours old filter, defaults to 72.
        """
        return self.get('job_search.hours_old', 72)
    
    def get_professional_domains(self) -> List[str]:
        """Get list of professional domains to preserve in PII removal.
        
        Returns:
            List[str]: List of professional domains to preserve.
        """
        return self.get_list('resume_processing.pii_removal.professional_domains', 
                           ['github.com', 'linkedin.com', 'stackoverflow.com'])
    
    def get_job_analysis_enabled(self) -> bool:
        """Get whether job analysis and ranking is enabled.
        
        Returns:
            bool: Whether job analysis is enabled, defaults to False.
        """
        return self.get('job_analysis.enabled', False)
    
    def get_job_analysis_config(self) -> Dict:
        """Get complete job analysis configuration.
        
        Returns:
            Dict: Complete job analysis configuration section.
        """
        return self.get_dict('job_analysis')
    
    def get_max_jobs_to_analyze(self) -> int:
        """Get maximum number of jobs to analyze.
        
        Returns:
            int: Maximum number of jobs to analyze, defaults to 20.
        """
        return self.get('job_analysis.max_jobs_to_analyze', 20)
    
    def get_job_analysis_batch_size(self) -> int:
        """Get batch size for job analysis API calls.
        
        Returns:
            int: Batch size for job analysis API calls, defaults to 5.
        """
        return self.get('job_analysis.batch_size', 5)
    
    def get_job_analysis_parallel_enabled(self) -> bool:
        """Get whether parallel batch processing is enabled.
        
        Returns:
            bool: Whether parallel batch processing is enabled, defaults to True.
        """
        return self.get('job_analysis.parallel_processing', True)
    
    def get_job_analysis_max_parallel_batches(self) -> int:
        """Get maximum number of parallel batches to process.
        
        Returns:
            int: Maximum number of parallel batches, defaults to 3.
        """
        return self.get('job_analysis.max_parallel_batches', 3)
    
    def get_job_analysis_request_delay(self) -> float:
        """Get delay between API requests in seconds.
        
        Returns:
            float: Delay between API requests in seconds, defaults to 0.5.
        """
        return self.get('job_analysis.request_delay_seconds', 0.5)
    
    def get_job_analysis_parallel_workers(self) -> int:
        """Get maximum number of parallel workers for job analysis.
        
        Returns:
            int: Maximum number of parallel workers, defaults to 3.
        """
        return self.get('job_analysis.max_parallel_batches', 3)
    
    def get_salary_analysis_enabled(self) -> bool:
        """Get whether salary extraction is enabled.
        
        Returns:
            bool: Whether salary extraction is enabled, defaults to True.
        """
        return self.get('job_analysis.analyze_salary', True)
    
    def get_similarity_ranking_enabled(self) -> bool:
        """Get whether similarity ranking is enabled.
        
        Returns:
            bool: Whether similarity ranking is enabled, defaults to True.
        """
        return self.get('job_analysis.rank_by_similarity', True)
    
    def get_job_analysis_model(self) -> str:
        """Get the model to use for job analysis.
        
        Returns:
            str: Model to use for job analysis, defaults to 'gpt-3.5-turbo'.
        """
        return self.get('job_analysis.similarity_ranking_model', 'gpt-3.5-turbo')
    
    def get_salary_confidence_threshold(self) -> float:
        """Get confidence threshold for salary extraction.
        
        Returns:
            float: Confidence threshold for salary extraction, defaults to 0.7.
        """
        return self.get('job_analysis.salary_extraction_confidence_threshold', 0.7)


# Global configuration instance
_config_instance = None


def get_config(config_file: str = None) -> ConfigLoader:
    """Get the global configuration instance (singleton pattern).
    
    Args:
        config_file (str, optional): Path to configuration file (only used on first call).
        
    Returns:
        ConfigLoader: The global ConfigLoader instance.
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigLoader(config_file)
    return _config_instance


def reload_config() -> None:
    """Reload the global configuration.
    
    Forces the global configuration instance to reload from the configuration file.
    """
    global _config_instance
    if _config_instance:
        _config_instance.reload()


def config_get(key_path: str, default: Any = None, env_override: str = None) -> Any:
    """Quick access to configuration values.
    
    Convenience function that gets the global config instance and retrieves a value.
    
    Args:
        key_path (str): Dot-separated path to configuration value.
        default (Any, optional): Default value if key is not found.
        env_override (str, optional): Environment variable name for override.
        
    Returns:
        Any: Configuration value, environment override, or default value.
    """
    return get_config().get(key_path, default, env_override) 