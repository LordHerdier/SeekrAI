import os
from pathlib import Path
from flask import Flask
from dotenv import load_dotenv
from config_loader import get_config
from utils.logging_setup import setup_flask_logging
from utils.directory_setup import ensure_directories
from routes.upload_routes import upload_bp
from routes.job_routes import job_bp
from routes.file_routes import file_bp

# Load environment variables
load_dotenv()

# Initialize configuration
config = get_config()

# Get project root directory (parent of src/)
project_root = Path(__file__).parent.parent

def create_app():
    """Application factory function"""
    # Initialize Flask app with correct template and static paths
    app = Flask(__name__, 
               template_folder=str(project_root / 'templates'),
               static_folder=str(project_root / 'static'))

    # Configure app
    app.config['SECRET_KEY'] = config.get_secret_key()
    app.config['UPLOAD_FOLDER'] = config.get_upload_folder()
    app.config['JOB_RESULTS_FOLDER'] = config.get('files.job_results_folder', 'job_results')
    app.config['MAX_CONTENT_LENGTH'] = config.get_max_file_size_bytes()
    app.config['ALLOWED_EXTENSIONS'] = config.get_allowed_extensions()

    # Ensure required directories exist
    ensure_directories(app.config, config)

    # Setup logging
    logger = setup_flask_logging(app)

    # Register request/response logging
    @app.before_request
    def log_request_info():
        """Log incoming requests"""
        from flask import request
        logger.info(f"Request: {request.method} {request.url} - Remote IP: {request.remote_addr}")

    @app.after_request
    def log_response_info(response):
        """Log response information"""
        from flask import request
        logger.info(f"Response: {response.status_code} for {request.method} {request.url}")
        return response

    # Register blueprints
    app.register_blueprint(upload_bp)
    app.register_blueprint(job_bp)
    app.register_blueprint(file_bp)

    # Error handlers
    @app.errorhandler(413)
    def too_large(e):
        """Handle file too large error"""
        logger.warning("File upload too large")
        return "File too large. Please upload a smaller file.", 413

    @app.errorhandler(404)
    def not_found(e):
        """Handle not found error"""
        return "Page not found", 404

    @app.errorhandler(500)
    def internal_error(e):
        """Handle internal server error"""
        logger.error(f"Internal server error: {str(e)}")
        return "Internal server error", 500

    return app

# Create the app instance
app = create_app()

if __name__ == '__main__':
    # Development server
    debug_mode = config.get('flask.debug', False)
    port = config.get('flask.port', 5000)
    host = config.get('flask.host', '127.0.0.1')
    
    app.run(debug=debug_mode, host=host, port=port) 