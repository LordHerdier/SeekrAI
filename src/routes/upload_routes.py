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
    """Check if the filename has one of the permitted extensions.

    Args:
        filename (str): The name of the uploaded file.
        allowed_extensions (set[str]): Set of lowercase extensions (no dot).

    Returns:
        bool: True if `filename` contains a period and its extension
            (after the last '.') is found in `allowed_extensions`; False otherwise.
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def cleanup_file_on_error(filepath):
    """Attempt to delete the file at `filepath` if it exists, logging the outcome.

    This is invoked after a processing exception to avoid leaving stray uploads.

    Args:
        filepath (str): Absolute or relative path to the file to remove.

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
    """Render the upload form page.

    Logs the request and returns the `index.html` template containing
    the resume upload form.

    Returns:
        flask.wrappers.Response: The rendered upload form.
    """
    logging.info("Serving main page")
    return render_template('index.html')

@upload_bp.route('/upload', methods=['POST'])
def upload_resume():
    """Process a resume upload, invoking `ResumeProcessor`, and handle outcomes.

    Workflow:
      1. Verify the 'resume' part exists in `request.files`.
      2. Ensure a non-empty filename.
      3. Check extension against `ALLOWED_EXTENSIONS` from app config.
      4. Save file with a secure, timestamped name into `UPLOAD_FOLDER`.
      5. Pull `desired_position` and `target_location` from `request.form`.
      6. Call `ResumeProcessor.process_resume(...)`.
         - On success: render `results.html` with a data dict.
         - On failure: flash error, clean up the saved file, and redirect.

    Flash & Redirect behavior:
      - Missing file part or blank filename → flash 'No file selected',
        redirect back to the upload URL.
      - Invalid extension → flash allowed types, redirect to the main upload page.
      - Processing exception → flash exception message, remove file, redirect to main.

    Returns:
        flask.wrappers.Response: One of:
          - `render_template('results.html', data=...)` on success.
          - `redirect(request.url)` if no file or empty filename.
          - `redirect(url_for('upload.index'))` on invalid type or processing error.
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