#!/usr/bin/env python3
"""
WSGI entry point for production deployment.
This module configures the Flask application for production use with Gunicorn.
"""

import os
import sys
from pathlib import Path

# Add the src directory to Python path
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.insert(0, str(current_dir))

# Import the Flask application
from app import create_app

# Create the application instance
application = create_app()
app = application  # Alias for compatibility

# Configure production settings
if os.environ.get('FLASK_ENV') == 'production':
    # Disable debug mode
    app.config['DEBUG'] = False
    
    # Configure session security
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    # Configure permanent session lifetime (30 minutes)
    app.config['PERMANENT_SESSION_LIFETIME'] = 1800

if __name__ == "__main__":
    # This won't be used in production but helps with development
    app.run() 