# Configuration Guide

## Overview

SeekrAI now uses a centralized configuration system that allows you to customize the application behavior without modifying the code. This system supports both configuration files and environment variable overrides.

## Configuration Files

### Main Configuration: `config.yaml`

The main configuration file contains all default settings for the application:

```yaml
# Application Settings
app:
  secret_key: "dev-secret-key-change-in-production"
  debug: false
  host: "127.0.0.1"
  port: 5000

# File Management
files:
  upload_folder: "uploads"
  job_results_folder: "job_results"
  cache_folder: ".cache"
  logs_folder: "logs"
  max_size_mb: 16
  allowed_extensions: [".pdf", ".docx", ".doc", ".txt"]

# And many more sections...
```

### Environment Variables: `.env`

Copy `.env.example` to `.env` and customize your settings:

```bash
cp .env.example .env
```

## Using Configuration in Your Code

### Python Code

```python
from config_loader import get_config

# Get configuration instance
config = get_config()

# Access values with fallbacks
secret_key = config.get('app.secret_key', 'default-secret')

# Use convenience methods
api_key = config.get_openai_api_key()
max_size = config.get_max_file_size_bytes()

# Access configuration sections
app_settings = config.app_config
file_settings = config.file_config
```

### JavaScript Code

Configuration is automatically loaded via `config.js`:

```javascript
// Access configuration
const maxSize = Config.get('files.maxSizeMB', 16);
const allowedTypes = Config.get('files.allowedTypes', []);

// Use utility methods
const isAllowed = Config.isFileTypeAllowed('application/pdf');
const fileSize = Config.formatFileSize(1024000);
const message = Config.getMessage('fileUpload.success');
```

## Configuration Sections

### Application Settings (`app`)
- `secret_key`: Flask secret key
- `debug`: Enable debug mode
- `host`: Server host
- `port`: Server port

### File Management (`files`)
- `upload_folder`: Directory for uploaded files
- `job_results_folder`: Directory for job search results
- `max_size_mb`: Maximum file size in MB
- `allowed_extensions`: List of allowed file extensions

### OpenAI Settings (`openai`)
- `api_key`: OpenAI API key (set via environment variable)
- `model`: Model to use (e.g., gpt-3.5-turbo)
- `temperature`: Model temperature (0.0-1.0)
- `max_retries`: Maximum retry attempts
- `timeout`: Request timeout in seconds

### Cache Settings (`cache`)
- `directory`: Cache directory path
- `expiration_days`: How long to keep cached files
- `max_size_mb`: Maximum cache size
- `cleanup_enabled`: Enable automatic cleanup

### Job Search Settings (`job_search`)
- `default_sites`: Default job sites to search
- `default_results`: Default number of results
- `hours_old`: Maximum job age in hours
- `country`: Default country for searches

### UI Settings (`ui`)
- `auto_dismiss_alerts_ms`: Auto-dismiss alerts after milliseconds
- `loading_button_timeout_ms`: Button timeout in milliseconds
- `job_results_per_page`: Pagination size
- `animation_duration_ms`: Animation duration

### Security Settings (`security`)
- `csrf_protection`: Enable CSRF protection
- `secure_uploads`: Enable secure file uploads
- `max_upload_attempts`: Maximum upload attempts
- `rate_limiting`: Enable rate limiting

## Environment Variable Overrides

Any configuration value can be overridden with environment variables:

### Format
Convert the YAML path to uppercase and replace dots with underscores:

```yaml
# config.yaml
app:
  secret_key: "default"
files:
  max_size_mb: 16
```

```bash
# .env
APP_SECRET_KEY=your-secret-key
FILES_MAX_SIZE_MB=32
```

### Common Environment Variables

```bash
# Essential settings
OPENAI_API_KEY=your_api_key
SECRET_KEY=your_secret_key

# File settings
MAX_FILE_SIZE_MB=32
UPLOAD_FOLDER=uploads

# Development
FLASK_DEBUG=true
LOG_LEVEL=DEBUG
```

## Best Practices

1. **Never commit sensitive data**: Use environment variables for API keys and secrets
2. **Use .env files locally**: Copy `.env.example` and customize for local development
3. **Override in production**: Use environment variables in production deployments
4. **Validate required settings**: The config loader will warn about missing required values
5. **Use configuration sections**: Organize related settings together

## Configuration Validation

The system validates required configuration keys:

```python
# Check for required keys
config = get_config()
missing_keys = config.validate_required_keys([
    'openai.api_key',
    'app.secret_key'
])

if missing_keys:
    print(f"Missing required configuration: {missing_keys}")
```

## Reloading Configuration

Configuration can be reloaded without restarting the application:

```python
from config_loader import reload_config

# Reload configuration from file
reload_config()
```

## Troubleshooting

### Common Issues

1. **Missing config.yaml**: The file will be created with defaults if missing
2. **Invalid YAML syntax**: Check indentation and syntax
3. **Environment variables not loading**: Ensure `.env` file is in the project root
4. **Permission errors**: Check file permissions for config files and directories

### Debug Configuration

Enable debug logging to see configuration loading:

```bash
LOG_LEVEL=DEBUG python app.py
```

This will show:
- Which configuration file is being loaded
- Environment variable overrides being applied
- Missing configuration keys
- Configuration validation results 