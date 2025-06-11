"""File management routes for the SeekrAI platform.

Provides file download, listing, cleanup, and cache‐info endpoints via a Flask blueprint.
"""

import os
from flask import Blueprint, render_template, request, jsonify, send_file, current_app, redirect, url_for, flash
from werkzeug.utils import secure_filename
from pathlib import Path
from resume_processor import ResumeProcessor
import logging

# Create blueprint
file_bp = Blueprint('files', __name__)

@file_bp.route('/download/<filename>')
def download_file(filename):
    """
    Serve a CSV from JOB_RESULTS_FOLDER as an attachment.

    Sanitizes `filename` to prevent path traversal, checks for existence,
    then returns it with `send_file(as_attachment=True)`.

    Args:
        filename (str): Base filename to serve (no path separators).

    Returns:
        200: send_file response with attachment headers.
        404: ("File not found", 404) if missing.
        500: ("Error downloading file", 500) on unexpected errors.
    """
    logging.info(f"File download requested: {filename}")
    try:
        # Security check: ensure filename doesn't have path traversal
        safe_filename = secure_filename(filename)
        file_path = os.path.join(current_app.config['JOB_RESULTS_FOLDER'], safe_filename)
        
        if os.path.exists(file_path):
            logging.info(f"Serving file: {file_path}")
            return send_file(file_path, as_attachment=True)
        else:
            logging.warning(f"File not found: {file_path}")
            return "File not found", 404
            
    except Exception as e:
        logging.error(f"Error serving file {filename}: {str(e)}")
        return "Error downloading file", 500

@file_bp.route('/files')
def file_management():
    """
    Render 'files.html' with lists of upload and result files.

    Scans UPLOAD_FOLDER and JOB_RESULTS_FOLDER, collects each file’s name,
    size (KB), and mtime, sorts newest→oldest, and passes them to the template.
    On any error, renders with empty lists and an 'error' message.

    Returns:
        HTML 200: rendered template with:
            - uploaded_files: List[Dict(name, size, modified)]
            - result_files:  List[Dict(name, size, modified)]
        HTML 200: same template + error message on failure.
    """
    logging.info("File management page requested")
    
    try:
        # Get uploaded files
        upload_folder = Path(current_app.config['UPLOAD_FOLDER'])
        uploaded_files = []
        if upload_folder.exists():
            for file_path in upload_folder.glob('*'):
                if file_path.is_file():
                    stat = file_path.stat()
                    uploaded_files.append({
                        'name': file_path.name,
                        'size': round(stat.st_size / 1024, 2),  # KB
                        'modified': stat.st_mtime
                    })
        
        # Get job result files
        results_folder = Path(current_app.config['JOB_RESULTS_FOLDER'])
        result_files = []
        if results_folder.exists():
            for file_path in results_folder.glob('*.csv'):
                if file_path.is_file():
                    stat = file_path.stat()
                    result_files.append({
                        'name': file_path.name,
                        'size': round(stat.st_size / 1024, 2),  # KB
                        'modified': stat.st_mtime
                    })
        
        # Sort by modification time (newest first)
        uploaded_files.sort(key=lambda x: x['modified'], reverse=True)
        result_files.sort(key=lambda x: x['modified'], reverse=True)
        
        logging.info(f"Found {len(uploaded_files)} uploaded files and {len(result_files)} result files")
        
        return render_template('files.html', 
                             uploaded_files=uploaded_files, 
                             result_files=result_files)
        
    except Exception as e:
        logging.error(f"Error in file management: {str(e)}", exc_info=True)
        return render_template('files.html', 
                             uploaded_files=[], 
                             result_files=[],
                             error="Error loading file information")

@file_bp.route('/cleanup_files', methods=['POST'])
def cleanup_files():
    """
    Delete files older than `max_age_days` in uploads/results folders and return JSON.

    Request JSON:
        {
            "type": "uploads"|"results"|"all",   # default "all"
            "max_age_days": int                  # default 7
        }

    Returns:
        JSON 200:
            {
                success: True,
                deleted_files: [{name, type, size}, …],
                total_files_deleted: int,
                total_size_freed_kb: float
            }
        JSON 500:
            {
                success: False,
                error: str
            }
    """
    logging.info("File cleanup request received")
    
    try:
        data = request.get_json()
        cleanup_type = data.get('type', 'all')  # 'uploads', 'results', or 'all'
        max_age_days = int(data.get('max_age_days', 7))
        
        from datetime import datetime, timedelta
        cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 60 * 60)
        
        deleted_files = []
        total_size_freed = 0
        
        def cleanup_directory(folder_path, file_type):
            """Helper function to clean up files in a specific directory.
            
            Args:
                folder_path (str): Path to the directory to clean up
                file_type (str): Type identifier for logging ('upload' or 'result')
            """
            nonlocal deleted_files, total_size_freed
            folder = Path(folder_path)
            if not folder.exists():
                return
                
            for file_path in folder.glob('*'):
                if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                    try:
                        size = file_path.stat().st_size
                        file_path.unlink()
                        deleted_files.append({
                            'name': file_path.name,
                            'type': file_type,
                            'size': round(size / 1024, 2)
                        })
                        total_size_freed += size
                        logging.info(f"Deleted {file_type} file: {file_path.name}")
                    except Exception as e:
                        logging.error(f"Could not delete {file_path}: {e}")
        
        # Clean up based on type
        if cleanup_type in ['uploads', 'all']:
            cleanup_directory(current_app.config['UPLOAD_FOLDER'], 'upload')
        
        if cleanup_type in ['results', 'all']:
            cleanup_directory(current_app.config['JOB_RESULTS_FOLDER'], 'result')
        
        total_size_freed_kb = round(total_size_freed / 1024, 2)
        
        logging.info(f"Cleanup completed: {len(deleted_files)} files deleted, {total_size_freed_kb} KB freed")
        
        return jsonify({
            'success': True,
            'deleted_files': deleted_files,
            'total_files_deleted': len(deleted_files),
            'total_size_freed_kb': total_size_freed_kb
        })
        
    except Exception as e:
        logging.error(f"Error during file cleanup: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@file_bp.route('/cache')
def cache_info():
    """
    Render 'cache.html' with cache statistics from ResumeProcessor.

    Fetches cache data via `ResumeProcessor.get_cache_info()` and passes:
        - cache_info: dict (directory, counts, sizes, per-file details)
    On error, renders with empty cache_info and an 'error' message.
    """
    logging.info("Cache info requested")
    try:
        processor = ResumeProcessor()
        cache_data = processor.get_cache_info()
        return render_template('cache.html', cache_info=cache_data)
    except Exception as e:
        logging.error(f"Error getting cache info: {str(e)}")
        return render_template('cache.html', cache_info={}, error=str(e))

@file_bp.route('/clear_cache', methods=['POST'])
def clear_cache():
    """
    Clear all cached resume data and redirect to cache page with flash status.

    Calls `ResumeProcessor.clear_cache()`, flashes a success or error message,
    then redirects to the cache info endpoint.

    Returns:
        Redirect (302) to 'files.cache_info'.
    """
    logging.info("Cache clear request received")
    try:
        processor = ResumeProcessor()
        result = processor.clear_cache()
        flash(f'Cache cleared successfully! {result["files_removed"]} files removed, {result["space_freed_mb"]} MB freed.')
        logging.info("Cache cleared successfully")
    except Exception as e:
        logging.error(f"Error clearing cache: {str(e)}")
        flash(f'Error clearing cache: {str(e)}')
    
    return redirect(url_for('files.cache_info')) 