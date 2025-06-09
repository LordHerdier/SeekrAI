import logging
import logging.handlers
from pathlib import Path
from config_loader import get_config


def setup_logging():
    """Configure application-wide logging"""
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
    """Setup Flask-specific logging"""
    logger = setup_logging()
    
    # Set Flask's logger to use our configuration
    app.logger.handlers = logger.handlers
    app.logger.setLevel(logger.level)
    
    return logger 