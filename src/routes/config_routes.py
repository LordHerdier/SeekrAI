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
    Serve the config management UI.

    Loads current settings and renders 'config.html'. If loading blows up,
    logs the heck out of it and renders the same page with an empty config
    plus an `error` message.

    Returns:
        flask.Response: Rendered template with context:
            - config_data (dict): current config or {}
            - sections (list): config section names or []
            - error (str, optional): error text if load failed
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
    Apply JSON-based config updates and save them.

    Expects a JSON body like:
        {"updates": {"a.b.c": "value", ...}}

    Values are converted (bool/int/float/list) before saving.
    Returns JSON + status code:
      - 200: {"success": True, "message": "...", "updated_count": N}
      - 400: {"success": False, "error": "..."}  # bad/missing payload
      - 500: {"success": False, "error": "..."}  # save or other failures

    Side effects:
      - config.update_multiple(...)
      - config.save_config()
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
    Reload the YAML file from disk, tossing out any unsaved changes.

    Calls `config.reload()`, flashes success or error, then redirects
    you back to /config so you can admire your fresh slate.

    Returns:
        flask.Response: 302 redirect to config_management.
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
    Dump the current in-memory config as JSON.

    Returns JSON + status code:
      - 200: {"success": True, "config": {...}}
      - 500: {"success": False, "error": "..."}  # on mystery faults

    No fancy access control here—be careful if you’re hiding secrets.
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
    Turn a form-string into the right Python type.

    - Non-strings come back unchanged.
    - Blank or whitespace-only → ''.
    - 'true','yes','1','on' → True; 'false','no','0','off' → False.
    - Strings with commas → [trimmed, non-empty pieces].
    - Dots → float; else try int; if that fails, leave as the original string.

    Args:
        value: the raw form value

    Returns:
        bool | int | float | list[str] | str | original type
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