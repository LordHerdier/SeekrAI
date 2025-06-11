"""
Configuration Management Routes for SeekrAI

This module provides Flask routes for managing application configuration through a web interface.
It supports viewing, updating, resetting, and exporting YAML-based configuration files used by
the SeekrAI job analysis platform.

The configuration system supports:
- Hierarchical YAML configuration with dot-notation access (e.g., 'app.debug', 'openai.model')
- Environment variable substitution using ${VAR} and ${VAR:-default} syntax
- Type conversion for form inputs (strings, integers, floats, booleans, lists)
- Configuration validation and error handling
- Live configuration reloading without application restart

Routes:
    GET  /config          - Configuration management interface
    POST /config/update   - Update configuration values via JSON API
    POST /config/reset    - Reset/reload configuration from file
    GET  /config/export   - Export current configuration as JSON

Example Usage:
    # Access configuration page
    curl http://localhost:5000/config
    
    # Update multiple config values
    curl -X POST http://localhost:5000/config/update \
         -H "Content-Type: application/json" \
         -d '{"updates": {"app.debug": "true", "openai.temperature": "0.5"}}'
    
    # Export configuration
    curl http://localhost:5000/config/export
"""

import logging
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from config_loader import get_config
from typing import Any, Dict

# Create blueprint
config_bp = Blueprint('config', __name__)

@config_bp.route('/config')
def config_management():
    """
    Render the configuration management web interface.
    
    This endpoint provides a web-based interface for viewing and managing application
    configuration settings. It displays all configuration sections and their current
    values in a user-friendly format, allowing administrators to understand and
    modify the application's behavior.
    
    The interface includes:
    - Hierarchical display of configuration sections
    - Current values for all configuration keys
    - Form inputs for editing values with appropriate type conversion
    - Validation and error feedback
    - Save and reset functionality
    
    Returns:
        str: Rendered HTML template for the configuration management page
        
    Raises:
        Exception: If configuration loading fails, renders error page with empty config
        
    Template Variables:
        config_data (dict): Complete configuration dictionary with all sections and values
        sections (list): List of top-level configuration section names
        error (str, optional): Error message if configuration loading failed
        
    HTTP Status Codes:
        200: Configuration page rendered successfully
        200: Configuration page rendered with error (but still shows interface)
        
    Logging:
        - INFO: Configuration page access attempts
        - ERROR: Configuration loading failures with full traceback
    """
    logging.info("Configuration management page requested")
    
    try:
        config = get_config()
        config_data = config.get_all_config()
        sections = config.get_config_sections()
        
        return render_template('config.html', 
                             config_data=config_data,
                             sections=sections)
        
    except Exception as e:
        logging.error(f"Error loading configuration: {str(e)}", exc_info=True)
        return render_template('config.html', 
                             config_data={},
                             sections=[],
                             error=str(e))

@config_bp.route('/config/update', methods=['POST'])
def update_config():
    """
    Update multiple configuration values via JSON API.
    
    This endpoint accepts a JSON payload containing configuration updates and applies
    them to the current configuration. It supports updating multiple configuration
    values atomically, with proper type conversion and validation.
    
    The endpoint performs the following operations:
    1. Validates the incoming JSON payload structure
    2. Converts string values to appropriate Python types (bool, int, float, list)
    3. Updates the configuration using dot-notation key paths
    4. Saves the updated configuration to the YAML file
    5. Returns a success/failure response with details
    
    Request Format:
        Content-Type: application/json
        Body: {
            "updates": {
                "key.path.1": "value1",
                "key.path.2": "value2",
                ...
            }
        }
        
    Type Conversion Rules:
        - "true"/"yes"/"1"/"on" → True (boolean)
        - "false"/"no"/"0"/"off" → False (boolean)  
        - "1,2,3" → ["1", "2", "3"] (list, comma-separated)
        - "123" → 123 (integer)
        - "12.34" → 12.34 (float)
        - Other strings remain as strings
        
    Args:
        None (uses Flask request.get_json())
        
    Returns:
        tuple: JSON response and HTTP status code
        
    Success Response (200):
        {
            "success": true,
            "message": "Configuration updated successfully! N values changed.",
            "updated_count": N
        }
        
    Error Responses:
        400 - Bad Request:
        {
            "success": false,
            "error": "No data provided" | "No updates provided"
        }
        
        500 - Internal Server Error:
        {
            "success": false, 
            "error": "Detailed error message"
        }
        
    Example Usage:
        curl -X POST http://localhost:5000/config/update \
             -H "Content-Type: application/json" \
             -d '{
                 "updates": {
                     "app.debug": "false",
                     "openai.temperature": "0.7",
                     "files.allowed_extensions": "pdf,docx,txt"
                 }
             }'
             
    Raises:
        400: Invalid JSON payload or missing required fields
        500: Configuration update or file save errors
        
    Logging:
        - INFO: Update requests and successful updates with count
        - ERROR: Update failures with full traceback
        
    Side Effects:
        - Modifies the global application configuration
        - Saves changes to the YAML configuration file
        - Updates affect application behavior immediately
    """
    logging.info("Configuration update request received")
    
    try:
        config = get_config()
        
        # Get JSON data from request
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        updates = data.get('updates', {})
        if not updates:
            return jsonify({'success': False, 'error': 'No updates provided'}), 400
        
        # Convert form values to appropriate types
        processed_updates = {}
        for key_path, value in updates.items():
            processed_value = _convert_form_value(value)
            processed_updates[key_path] = processed_value
        
        # Update configuration
        config.update_multiple(processed_updates)
        config.save_config()
        
        logging.info(f"Configuration updated successfully: {len(processed_updates)} values changed")
        
        return jsonify({
            'success': True,
            'message': f'Configuration updated successfully! {len(processed_updates)} values changed.',
            'updated_count': len(processed_updates)
        })
        
    except Exception as e:
        logging.error(f"Error updating configuration: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@config_bp.route('/config/reset', methods=['POST'])
def reset_config():
    """
    Reset configuration by reloading from the original YAML file.
    
    This endpoint discards any unsaved changes in memory and reloads the configuration
    from the original YAML file on disk. This is useful for reverting changes or
    recovering from configuration errors without restarting the application.
    
    The reset operation:
    1. Discards all in-memory configuration changes
    2. Reloads configuration from the original YAML file
    3. Reprocesses environment variable substitutions
    4. Redirects back to the configuration management page
    5. Shows a flash message indicating success or failure
    
    This is a destructive operation that cannot be undone unless changes were
    previously saved to a backup file.
    
    Returns:
        flask.Response: Redirect response to configuration management page
        
    Flash Messages:
        Success: "Configuration reloaded from file successfully!"
        Error: "Error reloading configuration: <error details>"
        
    Example Usage:
        # Via HTML form
        <form method="POST" action="/config/reset">
            <button type="submit">Reset Configuration</button>
        </form>
        
        # Via curl  
        curl -X POST http://localhost:5000/config/reset
        
    HTTP Status Codes:
        302: Redirect to configuration page (success or error)
        
    Raises:
        Exception: Configuration reload failures (caught and shown as flash message)
        
    Logging:
        - INFO: Reset requests and successful reloads
        - ERROR: Reset failures with full traceback
        
    Side Effects:
        - Discards all unsaved configuration changes
        - Reloads configuration from disk
        - May affect application behavior if unsaved changes existed
        - Flash message added to user session
        
    Warning:
        This operation cannot be undone. Any unsaved configuration changes
        will be permanently lost.
    """
    logging.info("Configuration reset request received")
    
    try:
        config = get_config()
        
        # Reload configuration from file (discarding any unsaved changes)
        config.reload()
        
        flash('Configuration reloaded from file successfully!')
        logging.info("Configuration reloaded successfully")
        
        return redirect(url_for('config.config_management'))
        
    except Exception as e:
        logging.error(f"Error reloading configuration: {str(e)}", exc_info=True)
        flash(f'Error reloading configuration: {str(e)}')
        return redirect(url_for('config.config_management'))

@config_bp.route('/config/export', methods=['GET'])
def export_config():
    """
    Export the current configuration as a JSON response.
    
    This endpoint provides programmatic access to the complete current configuration
    state, including all sections, keys, and processed values (with environment
    variable substitutions applied). Useful for:
    - Configuration backups
    - External system integration  
    - Configuration auditing and comparison
    - API-based configuration management
    
    The exported configuration includes all processed values with environment
    variable substitutions applied, representing the actual runtime configuration
    state rather than the raw YAML file contents.
    
    Returns:
        tuple: JSON response and HTTP status code
        
    Success Response (200):
        {
            "success": true,
            "config": {
                "app": {
                    "debug": false,
                    "secret_key": "processed-value",
                    ...
                },
                "openai": {
                    "model": "gpt-3.5-turbo",
                    "temperature": 0.3,
                    ...
                },
                ...
            }
        }
        
    Error Response (500):
        {
            "success": false,
            "error": "Detailed error message"  
        }
        
    Example Usage:
        # Get full configuration
        curl http://localhost:5000/config/export
        
        # Save to file
        curl http://localhost:5000/config/export | jq '.config' > config-backup.json
        
        # Check specific section
        curl http://localhost:5000/config/export | jq '.config.openai'
        
    Response Headers:
        Content-Type: application/json
        
    HTTP Status Codes:
        200: Configuration exported successfully
        500: Export failed due to internal error
        
    Raises:
        500: Configuration loading or JSON serialization errors
        
    Logging:
        - INFO: Export requests
        - ERROR: Export failures with full traceback
        
    Note:
        - The exported configuration includes processed environment variables
        - Sensitive values (like API keys) may be included in the export
        - TODO: Consider access control for this endpoint in production environments
        - The export represents the current in-memory state, not necessarily
          the saved file state if there are unsaved changes
    """
    logging.info("Configuration export requested")
    
    try:
        config = get_config()
        config_data = config.get_all_config()
        
        return jsonify({
            'success': True,
            'config': config_data
        })
        
    except Exception as e:
        logging.error(f"Error exporting configuration: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def _convert_form_value(value: str) -> Any:
    """
    Convert form string value to appropriate Python type for configuration storage.
    
    This utility function handles type conversion from string form inputs to the
    appropriate Python types that should be stored in the configuration. It
    supports automatic detection and conversion of common data types including
    booleans, numbers, lists, and strings.
    
    The conversion follows these rules in order:
    1. Empty strings remain as empty strings
    2. Boolean values: 'true'/'yes'/'1'/'on' → True, 'false'/'no'/'0'/'off' → False
    3. Lists: Comma-separated values → List of trimmed strings
    4. Numbers: Values containing '.' → float, integer strings → int
    5. Everything else remains as a string
    
    Args:
        value (str): String value from form input to be converted
        
    Returns:
        Any: Converted value with appropriate Python type:
            - bool: For recognized boolean string values
            - int: For integer numeric strings  
            - float: For decimal numeric strings
            - list: For comma-separated string values
            - str: For all other string values
            - Any: Returns input unchanged if not a string
            
    Type Conversion Examples:
        Boolean:
            'true' → True
            'false' → False
            'yes' → True  
            'no' → False
            '1' → True
            '0' → False
            'on' → True
            'off' → False
            
        Numbers:
            '42' → 42
            '3.14' → 3.14
            '0' → 0 (not False, since it would be converted as number first)
            
        Lists:
            'apple,banana,cherry' → ['apple', 'banana', 'cherry']
            'pdf, docx, txt' → ['pdf', 'docx', 'txt']
            'single' → 'single' (no comma, stays string)
            
        Strings:
            'hello world' → 'hello world'
            '' → ''
            '   ' → ''
            
    Note:
        - Boolean conversion is case-insensitive
        - List items are automatically trimmed of whitespace
        - Empty list items are filtered out
        - Invalid numbers fall back to string type
        - Non-string inputs are returned unchanged
        
    Example Usage:
        # In configuration update processing
        for key_path, raw_value in form_data.items():
            typed_value = _convert_form_value(raw_value)
            config.set(key_path, typed_value)
            
        # Direct usage
        assert _convert_form_value('true') == True
        assert _convert_form_value('42') == 42
        assert _convert_form_value('a,b,c') == ['a', 'b', 'c']
        
    Warning:
        - The string '0' converts to integer 0, not boolean False
        - Comma-separated values always become lists, even single items with commas
        - Numeric conversion errors silently fall back to strings
    """
    if not isinstance(value, str):
        return value
    
    # Handle empty strings
    if value.strip() == '':
        return ''
    
    # Boolean conversion
    if value.lower() in ('true', 'yes', '1', 'on'):
        return True
    elif value.lower() in ('false', 'no', '0', 'off'):
        return False
    
    # List conversion (comma-separated values)
    if ',' in value:
        return [item.strip() for item in value.split(',') if item.strip()]
    
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