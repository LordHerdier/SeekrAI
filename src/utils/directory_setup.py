"""Directory setup utilities for ensuring required directories exist.

This module provides utilities for creating and managing directory structures
required by the application, including upload folders, job results folders,
logs directories, and cache directories.
"""
import os
from config_loader import get_config


def ensure_directories(app_config, config=None):
    """Create all required directories if they don't exist.
    
    This function ensures that all necessary directories for the application
    are created, including upload folders, job results folders, logs directory,
    and cache directory. Directories are created recursively if needed.
    
    Args:
        app_config (dict): Application configuration dictionary containing
            directory paths like 'UPLOAD_FOLDER' and 'JOB_RESULTS_FOLDER'.
        config (object, optional): Configuration object with methods like
            get() and get_cache_directory(). If None, will be loaded using
            get_config(). Defaults to None.
    
    Returns:
        None
        
    Raises:
        OSError: If directory creation fails due to permission issues or
            invalid paths.
    """
    if config is None:
        config = get_config()
    
    directories = [
        app_config['UPLOAD_FOLDER'],
        app_config['JOB_RESULTS_FOLDER'],
        config.get('files.logs_folder', 'logs'),
        config.get_cache_directory()
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True) 