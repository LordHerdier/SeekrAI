"""
upload_routes.py

Defines a Flask blueprint for handling resume uploads, saving files,
processing them via ResumeProcessor, and cleaning up on errors.
"""
import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from resume_processor import ResumeProcessor
import logging

# Create blueprint
upload_bp = Blueprint('upload', __name__)

def allowed_file(filename, allowed_extensions):
    """Determines whether a filename has an allowed extension.

    Args:
        filename (str): The name of the file to check.
        allowed_extensions (set[str]): Allowed extensions (without leading dot).

    Returns:
        bool: True if `filename` contains an extension and it is in
            `allowed_extensions`, False otherwise.
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def cleanup_file_on_error(filepath):
    """Removes the given file if it exists, logging success or failure.

    This is typically called when resume processing blows up and
    you don’t want orphaned uploads lying around.

    Args:
        filepath (str): Full path to the file to delete.

    Returns:
        None
    """
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logging.info(f"Cleaned up file after error: {filepath}")
    except Exception as e:
        logging.error(f"Could not clean up file {filepath}: {e}")

@upload_bp.route('/')
def index():
    """Renders the main upload page.

    Returns:
        flask.wrappers.Response: Rendered `index.html` template
        containing the resume upload form.
    """
    logging.info("Serving main page")
    return render_template('index.html')

@upload_bp.route('/upload', methods=['POST'])
def upload_resume():
    """Handles an uploaded resume file and kicks off processing.

    - Validates presence and extension of the uploaded file.
    - Saves it with a timestamped, secure filename.
    - Extracts `desired_position` and `target_location` from the form.
    - Invokes `ResumeProcessor.process_resume`.
    - On success, renders `results.html` with keywords/search terms.
    - On failure, logs the error, cleans up, flashes a message, and redirects
      back to the upload form.

    Returns:
        flask.wrappers.Response:
            - On success: rendered `results.html` with `data` dict.
            - On missing file or invalid type: redirect back to upload page.
            - On processing error: redirect to index with an error flash.

    Raises:
        None: All exceptions during processing are caught and handled internally.
    """
    from flask import current_app
    
    logging.info("Resume upload request received")
    
    if 'resume' not in request.files:
        logging.warning("Upload request without resume file")
        flash('No file selected')
        return redirect(request.url)
    
    file = request.files['resume']
    if file.filename == '':
        logging.warning("Upload request with empty filename")
        flash('No file selected')
        return redirect(request.url)
    
    allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', {'pdf', 'doc', 'docx', 'txt'})
    
    if file and allowed_file(file.filename, allowed_extensions):
        # Save uploaded file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        logging.info(f"Saving uploaded file: {filename}")
        file.save(filepath)
        
        # Get form data
        desired_position = request.form.get('desired_position', '').strip()
        target_location = request.form.get('target_location', '').strip()
        
        logging.info(f"Processing resume - Position: {desired_position}, Location: {target_location}")
        
        try:
            # Process the resume
            processor = ResumeProcessor()
            logging.info("Starting resume processing")
            results = processor.process_resume(
                filepath, 
                target_location=target_location if target_location else None,
                desired_position=desired_position if desired_position else None
            )
            
            logging.info("Resume processing completed successfully")
            
            # Store results in session or pass to results page
            session_data = {
                'filename': filename,
                'filepath': filepath,
                'desired_position': desired_position,
                'target_location': target_location,
                'keywords': results.get('keywords', {}),
                'search_terms': results.get('search_terms', {}),
                'timestamp': timestamp
            }
            
            logging.info(f"Resume processing results: {len(results.get('keywords', {}))} keywords extracted")
            return render_template('results.html', data=session_data)
            
        except Exception as e:
            logging.error(f"Error processing resume: {str(e)}", exc_info=True)
            flash(f'Error processing resume: {str(e)}')
            # Clean up uploaded file on error
            cleanup_file_on_error(filepath)
            return redirect(url_for('upload.index'))
    
    else:
        logging.warning(f"Invalid file type uploaded: {file.filename}")
        allowed_exts = ', '.join(f'.{ext}' for ext in allowed_extensions)
        flash(f'Invalid file type. Please upload a {allowed_exts} file.')
        return redirect(url_for('upload.index')) 