"""
Health check routes for production monitoring.
"""

import os
import time
from datetime import datetime
from flask import Blueprint, jsonify, current_app
from pathlib import Path

health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    """
    Basic health check endpoint for load balancers and monitoring systems.
    Returns 200 OK if the application is healthy.
    """
    try:
        # Check if critical directories exist and are writable
        directories_to_check = [
            current_app.config.get('UPLOAD_FOLDER', '/app/uploads'),
            current_app.config.get('JOB_RESULTS_FOLDER', '/app/job_results'),
            current_app.config.get('CACHE_FOLDER', '/app/.cache'),
            current_app.config.get('LOGS_FOLDER', '/app/logs')
        ]
        
        for directory in directories_to_check:
            dir_path = Path(directory)
            if not dir_path.exists():
                return jsonify({
                    'status': 'unhealthy',
                    'error': f'Directory {directory} does not exist',
                    'timestamp': datetime.utcnow().isoformat()
                }), 503
            
            if not os.access(directory, os.W_OK):
                return jsonify({
                    'status': 'unhealthy',
                    'error': f'Directory {directory} is not writable',
                    'timestamp': datetime.utcnow().isoformat()
                }), 503
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0',
            'uptime': time.time() - current_app.config.get('START_TIME', time.time())
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 503

@health_bp.route('/health/detailed', methods=['GET'])
def detailed_health_check():
    """
    Detailed health check endpoint with more comprehensive checks.
    """
    try:
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0',
            'uptime': time.time() - current_app.config.get('START_TIME', time.time()),
            'checks': {}
        }
        
        # Check directories
        directories = {
            'uploads': current_app.config.get('UPLOAD_FOLDER', '/app/uploads'),
            'job_results': current_app.config.get('JOB_RESULTS_FOLDER', '/app/job_results'),
            'cache': current_app.config.get('CACHE_FOLDER', '/app/.cache'),
            'logs': current_app.config.get('LOGS_FOLDER', '/app/logs')
        }
        
        for name, directory in directories.items():
            try:
                dir_path = Path(directory)
                health_data['checks'][f'directory_{name}'] = {
                    'status': 'healthy' if dir_path.exists() and os.access(directory, os.W_OK) else 'unhealthy',
                    'path': directory,
                    'exists': dir_path.exists(),
                    'writable': os.access(directory, os.W_OK) if dir_path.exists() else False
                }
            except Exception as e:
                health_data['checks'][f'directory_{name}'] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
        
        # Check environment variables
        required_env_vars = ['OPENAI_API_KEY', 'SECRET_KEY']
        for var in required_env_vars:
            health_data['checks'][f'env_{var.lower()}'] = {
                'status': 'healthy' if os.environ.get(var) else 'unhealthy',
                'configured': bool(os.environ.get(var))
            }
        
        # Check disk space
        try:
            upload_folder = current_app.config.get('UPLOAD_FOLDER', '/app/uploads')
            statvfs = os.statvfs(upload_folder)
            free_space_gb = (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
            health_data['checks']['disk_space'] = {
                'status': 'healthy' if free_space_gb > 1.0 else 'warning',
                'free_space_gb': round(free_space_gb, 2)
            }
        except Exception as e:
            health_data['checks']['disk_space'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
        
        # Determine overall status
        unhealthy_checks = [check for check in health_data['checks'].values() 
                           if check.get('status') == 'unhealthy']
        
        if unhealthy_checks:
            health_data['status'] = 'unhealthy'
            return jsonify(health_data), 503
        
        warning_checks = [check for check in health_data['checks'].values() 
                         if check.get('status') == 'warning']
        
        if warning_checks:
            health_data['status'] = 'warning'
            return jsonify(health_data), 200
        
        return jsonify(health_data), 200
        
    except Exception as e:
        current_app.logger.error(f"Detailed health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 503

@health_bp.route('/ready', methods=['GET'])
def readiness_check():
    """
    Readiness check endpoint for Kubernetes-style readiness probes.
    """
    try:
        # Perform minimal checks to determine if the app is ready to serve traffic
        upload_folder = Path(current_app.config.get('UPLOAD_FOLDER', '/app/uploads'))
        
        if not upload_folder.exists():
            return jsonify({
                'status': 'not_ready',
                'reason': 'Upload folder not available',
                'timestamp': datetime.utcnow().isoformat()
            }), 503
        
        return jsonify({
            'status': 'ready',
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Readiness check failed: {str(e)}")
        return jsonify({
            'status': 'not_ready',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 503 