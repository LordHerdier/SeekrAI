import os
import yaml
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Union


def _get_project_root():
    """Get the project root directory."""
    # Get the directory containing this config_loader.py file (src/)
    current_dir = Path(__file__).parent
    # Go up one level to get the project root
    return current_dir.parent


def _substitute_env_vars(value):
    """
    Substitute environment variables in a string value.
    Supports ${VAR:-default}, ${VAR}, and $VAR syntax.
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
    """Recursively process configuration data to substitute environment variables."""
    if isinstance(config_data, dict):
        return {key: _process_config_recursively(value) for key, value in config_data.items()}
    elif isinstance(config_data, list):
        return [_process_config_recursively(item) for item in config_data]
    elif isinstance(config_data, str):
        return _substitute_env_vars(config_data)
    else:
        return config_data


class ConfigLoader:
    """
    Configuration loader for SeekrAI application.
    Loads configuration from YAML file with environment variable overrides.
    """
    
    def __init__(self, config_file: str = None):
        """
        Initialize the configuration loader.
        
        Args:
            config_file: Path to the YAML configuration file
        """
        if config_file is None:
            # Default to config/config.yaml relative to project root
            project_root = _get_project_root()
            config_file = project_root / "config" / "config.yaml"
        
        self.config_file = Path(config_file)
        self._config = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from YAML file."""
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
        """Save current configuration to YAML file."""
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
        """
        Set configuration value using dot-separated path.
        
        Args:
            key_path: Dot-separated path to configuration value (e.g., 'app.debug')
            value: Value to set
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
        """
        Update multiple configuration values at once.
        
        Args:
            updates: Dictionary mapping key paths to new values
        """
        for key_path, value in updates.items():
            self.set(key_path, value)
    
    def get_all_config(self) -> Dict:
        """Get the complete configuration dictionary."""
        return self._config.copy()
    
    def get_config_sections(self) -> List[str]:
        """Get list of top-level configuration sections."""
        return list(self._config.keys())
    
    def get(self, key_path: str, default: Any = None, env_override: str = None) -> Any:
        """
        Get configuration value with optional environment variable override.
        
        Args:
            key_path: Dot-separated path to configuration value (e.g., 'app.debug')
            default: Default value if key is not found
            env_override: Environment variable name to check for override
            
        Returns:
            Configuration value or default
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
        """Convert environment variable string to appropriate type."""
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
        """
        Get configuration list with optional environment variable override.
        Environment variables should be comma-separated values.
        """
        if env_override and env_override in os.environ:
            env_value = os.environ[env_override]
            return [item.strip() for item in env_value.split(',') if item.strip()]
        
        return self.get(key_path, default or [])
    
    def get_dict(self, key_path: str, default: Dict = None) -> Dict:
        """Get configuration dictionary."""
        return self.get(key_path, default or {})
    
    def reload(self) -> None:
        """Reload configuration from file."""
        self._load_config()
    
    def validate_required_keys(self, required_keys: List[str]) -> List[str]:
        """
        Validate that required configuration keys exist.
        
        Args:
            required_keys: List of required key paths
            
        Returns:
            List of missing keys
        """
        missing_keys = []
        for key in required_keys:
            if self.get(key) is None:
                missing_keys.append(key)
        return missing_keys
    
    # Convenience methods for common configuration access patterns
    
    @property
    def app_config(self) -> Dict:
        """Get application configuration."""
        return self.get_dict('app')
    
    @property
    def file_config(self) -> Dict:
        """Get file management configuration."""
        return self.get_dict('files')
    
    @property
    def logging_config(self) -> Dict:
        """Get logging configuration."""
        return self.get_dict('logging')
    
    @property
    def openai_config(self) -> Dict:
        """Get OpenAI configuration."""
        return self.get_dict('openai')
    
    @property
    def cache_config(self) -> Dict:
        """Get cache configuration."""
        return self.get_dict('cache')
    
    @property
    def job_search_config(self) -> Dict:
        """Get job search configuration."""
        return self.get_dict('job_search')
    
    @property
    def resume_processing_config(self) -> Dict:
        """Get resume processing configuration."""
        return self.get_dict('resume_processing')
    
    @property
    def cleanup_config(self) -> Dict:
        """Get cleanup configuration."""
        return self.get_dict('cleanup')
    
    @property
    def ui_config(self) -> Dict:
        """Get UI configuration."""
        return self.get_dict('ui')
    
    @property
    def development_config(self) -> Dict:
        """Get development configuration."""
        return self.get_dict('development')
    
    @property
    def security_config(self) -> Dict:
        """Get security configuration."""
        return self.get_dict('security')
    
    # Specific getters with environment overrides for common values
    
    def get_secret_key(self) -> str:
        """Get Flask secret key with environment override."""
        return self.get('app.secret_key', env_override='SECRET_KEY')
    
    def get_openai_api_key(self) -> str:
        """Get OpenAI API key from environment."""
        return os.environ.get('OPENAI_API_KEY', '')
    
    def get_upload_folder(self) -> str:
        """Get upload folder path."""
        return self.get('files.upload_folder', 'uploads')
    
    def get_max_file_size_bytes(self) -> int:
        """Get maximum file size in bytes."""
        mb = self.get('files.max_file_size_mb', 16)
        return mb * 1024 * 1024
    
    def get_allowed_extensions(self) -> set:
        """Get allowed file extensions as a set."""
        extensions = self.get_list('files.allowed_extensions', ['txt', 'pdf', 'docx', 'doc'])
        return set(extensions)
    
    def get_cache_directory(self) -> str:
        """Get cache directory path."""
        return self.get('cache.directory', '.cache')
    
    def get_cache_expiration_days(self) -> int:
        """Get cache expiration in days."""
        return self.get('cache.expiration_days', 7)
    
    def get_openai_model(self) -> str:
        """Get OpenAI model name."""
        return self.get('openai.model', 'gpt-3.5-turbo')
    
    def get_openai_temperature(self) -> float:
        """Get OpenAI temperature setting."""
        return self.get('openai.temperature', 0.3)
    
    def get_job_search_sites(self) -> List[str]:
        """Get default job search sites."""
        return self.get_list('job_search.default_sites', ['indeed', 'linkedin'])
    
    def get_default_job_results(self) -> int:
        """Get default number of job results."""
        return self.get('job_search.default_results', 10)
    
    def get_job_hours_old(self) -> int:
        """Get job search hours old filter."""
        return self.get('job_search.hours_old', 72)
    
    def get_professional_domains(self) -> List[str]:
        """Get list of professional domains to preserve in PII removal."""
        return self.get_list('resume_processing.pii_removal.professional_domains', 
                           ['github.com', 'linkedin.com', 'stackoverflow.com'])
    
    def get_job_analysis_enabled(self) -> bool:
        """Get whether job analysis and ranking is enabled."""
        return self.get('job_analysis.enabled', False)
    
    def get_job_analysis_config(self) -> Dict:
        """Get complete job analysis configuration."""
        return self.get_dict('job_analysis')
    
    def get_max_jobs_to_analyze(self) -> int:
        """Get maximum number of jobs to analyze."""
        return self.get('job_analysis.max_jobs_to_analyze', 20)
    
    def get_job_analysis_batch_size(self) -> int:
        """Get batch size for job analysis API calls."""
        return self.get('job_analysis.batch_size', 5)
    
    def get_job_analysis_parallel_enabled(self) -> bool:
        """Get whether parallel batch processing is enabled."""
        return self.get('job_analysis.parallel_processing', True)
    
    def get_job_analysis_max_parallel_batches(self) -> int:
        """Get maximum number of parallel batches to process."""
        return self.get('job_analysis.max_parallel_batches', 3)
    
    def get_job_analysis_request_delay(self) -> float:
        """Get delay between API requests in seconds."""
        return self.get('job_analysis.request_delay_seconds', 0.5)
    
    def get_job_analysis_parallel_workers(self) -> int:
        """Get maximum number of parallel workers for job analysis."""
        return self.get('job_analysis.max_parallel_batches', 3)
    
    def get_salary_analysis_enabled(self) -> bool:
        """Get whether salary extraction is enabled."""
        return self.get('job_analysis.analyze_salary', True)
    
    def get_similarity_ranking_enabled(self) -> bool:
        """Get whether similarity ranking is enabled."""
        return self.get('job_analysis.rank_by_similarity', True)
    
    def get_job_analysis_model(self) -> str:
        """Get the model to use for job analysis."""
        return self.get('job_analysis.similarity_ranking_model', 'gpt-3.5-turbo')
    
    def get_salary_confidence_threshold(self) -> float:
        """Get confidence threshold for salary extraction."""
        return self.get('job_analysis.salary_extraction_confidence_threshold', 0.7)


# Global configuration instance
_config_instance = None


def get_config(config_file: str = None) -> ConfigLoader:
    """
    Get the global configuration instance (singleton pattern).
    
    Args:
        config_file: Path to configuration file (only used on first call)
        
    Returns:
        ConfigLoader instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigLoader(config_file)
    return _config_instance


def reload_config() -> None:
    """Reload the global configuration."""
    global _config_instance
    if _config_instance:
        _config_instance.reload()


# Convenience function for quick access
def config_get(key_path: str, default: Any = None, env_override: str = None) -> Any:
    """Quick access to configuration values."""
    return get_config().get(key_path, default, env_override) 