import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from processors.resume_processor import ResumeProcessor
import logging

# Create blueprint
upload_bp = Blueprint('upload', __name__)

def allowed_file(filename, allowed_extensions):
    """Check if file has allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def cleanup_file_on_error(filepath):
    """Clean up uploaded file if processing fails"""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logging.info(f"Cleaned up file after error: {filepath}")
    except Exception as e:
        logging.error(f"Could not clean up file {filepath}: {e}")

@upload_bp.route('/')
def index():
    """Main page with upload form"""
    logging.info("Serving main page")
    return render_template('index.html')

@upload_bp.route('/upload', methods=['POST'])
def upload_resume():
    """Handle resume upload and initial processing"""
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