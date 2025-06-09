import logging
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from config_loader import get_config
from typing import Any, Dict

# Create blueprint
config_bp = Blueprint('config', __name__)

@config_bp.route('/config')
def config_management():
    """Configuration management page"""
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
    """Update configuration values"""
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
    """Reset configuration to defaults or reload from file"""
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
    """Export current configuration as JSON"""
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
    Convert form string value to appropriate Python type.
    
    Args:
        value: String value from form
        
    Returns:
        Converted value (bool, int, float, list, or str)
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