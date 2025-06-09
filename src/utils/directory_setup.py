import os
from config_loader import get_config


def ensure_directories(app_config, config=None):
    """Create all required directories if they don't exist"""
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