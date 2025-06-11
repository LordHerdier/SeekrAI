
"""Logging setup utilities for configuring application-wide logging.

This module provides functions for setting up and configuring logging for the
entire application, including console and file handlers with rotation.
"""
import logging
import logging.handlers
from pathlib import Path
from config_loader import get_config


def setup_logging():
    """Configure application-wide logging with console and file handlers.
    
    Sets up a comprehensive logging system with rotating file handlers for both
    general application logs and error-specific logs. Creates the logs directory
    if it doesn't exist and configures logging based on application configuration.
    
    The function configures:
    - Console handler for real-time log output
    - Rotating file handler for general application logs (seekrai.log)
    - Rotating file handler for error-level logs only (seekrai_errors.log)
    
    All handlers use the same formatter and log level as specified in the
    application configuration.
    
    Returns:
        logging.Logger: The configured root logger instance with all handlers attached.
        
    Raises:
        OSError: If the logs directory cannot be created due to permission issues.
        KeyError: If required configuration keys are missing from the config.
        AttributeError: If an invalid log level is specified in the configuration.
    """
    config = get_config()
    
    # Create logs directory if it doesn't exist
    logs_dir = Path(config.get('files.logs_folder', 'logs'))
    logs_dir.mkdir(exist_ok=True)
    
    # Configure logging format
    log_format = logging.Formatter(config.get('logging.format'))
    
    # Get the root logger
    logger = logging.getLogger()
    log_level = getattr(logging, config.get('logging.level', 'INFO').upper())
    logger.setLevel(log_level)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    max_bytes = config.get('logging.max_file_size_mb', 10) * 1024 * 1024
    backup_count = config.get('logging.backup_count', 5)
    
    file_handler = logging.handlers.RotatingFileHandler(
        logs_dir / 'seekrai.log',
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)
    
    # Error file handler
    error_handler = logging.handlers.RotatingFileHandler(
        logs_dir / 'seekrai_errors.log',
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(log_format)
    logger.addHandler(error_handler)
    
    return logger


def setup_flask_logging(app):
    """Setup Flask-specific logging by integrating with application logging configuration.
    
    Configures the Flask application's logger to use the same handlers and log level
    as the main application logging system. This ensures consistent logging behavior
    across the entire application, including Flask's internal logging.
    
    Args:
        app (flask.Flask): The Flask application instance to configure logging for.
        
    Returns:
        logging.Logger: The configured logger instance that's now being used by
            both the application and Flask.
            
    Raises:
        OSError: If the logs directory cannot be created during setup_logging().
        KeyError: If required configuration keys are missing from the config.
        AttributeError: If an invalid log level is specified in the configuration.
    """
    logger = setup_logging()
    
    # Set Flask's logger to use our configuration
    app.logger.handlers = logger.handlers
    app.logger.setLevel(logger.level)
    
    return logger 