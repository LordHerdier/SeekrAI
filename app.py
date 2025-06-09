import os
import csv
import json
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
from jobspy import scrape_jobs
from resume_processor import ResumeProcessor
from dotenv import load_dotenv
import pandas as pd

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Configure logging
def setup_logging():
    """Configure application-wide logging"""
    # Create logs directory if it doesn't exist
    logs_dir = Path('logs')
    logs_dir.mkdir(exist_ok=True)
    
    # Configure logging format
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    
    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        logs_dir / 'seekrai.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)
    
    # Error file handler
    error_handler = logging.handlers.RotatingFileHandler(
        logs_dir / 'seekrai_errors.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(log_format)
    logger.addHandler(error_handler)
    
    # Set Flask's logger to use our configuration
    app.logger.handlers = logger.handlers
    app.logger.setLevel(logger.level)
    
    return logger

# Setup logging
logger = setup_logging()

# Allowed file extensions
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'doc'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.before_request
def log_request_info():
    """Log incoming requests"""
    logger.info(f"Request: {request.method} {request.url} - Remote IP: {request.remote_addr}")

@app.after_request
def log_response_info(response):
    """Log response information"""
    logger.info(f"Response: {response.status_code} for {request.method} {request.url}")
    return response

@app.route('/')
def index():
    """Main page with upload form"""
    logger.info("Serving main page")
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_resume():
    """Handle resume upload and initial processing"""
    logger.info("Resume upload request received")
    
    if 'resume' not in request.files:
        logger.warning("Upload request without resume file")
        flash('No file selected')
        return redirect(request.url)
    
    file = request.files['resume']
    if file.filename == '':
        logger.warning("Upload request with empty filename")
        flash('No file selected')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        # Save uploaded file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        logger.info(f"Saving uploaded file: {filename}")
        file.save(filepath)
        
        # Get form data
        desired_position = request.form.get('desired_position', '').strip()
        target_location = request.form.get('target_location', '').strip()
        
        logger.info(f"Processing resume - Position: {desired_position}, Location: {target_location}")
        
        try:
            # Process the resume
            processor = ResumeProcessor()
            logger.info("Starting resume processing")
            results = processor.process_resume(
                filepath, 
                target_location=target_location if target_location else None,
                desired_position=desired_position if desired_position else None
            )
            
            logger.info("Resume processing completed successfully")
            
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
            
            logger.info(f"Resume processing results: {len(results.get('keywords', {}))} keywords extracted")
            return render_template('results.html', data=session_data)
            
        except Exception as e:
            logger.error(f"Error processing resume: {str(e)}", exc_info=True)
            flash(f'Error processing resume: {str(e)}')
            # Clean up uploaded file on error
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"Cleaned up uploaded file after error: {filepath}")
            return redirect(url_for('index'))
    
    else:
        logger.warning(f"Invalid file type uploaded: {file.filename}")
        flash('Invalid file type. Please upload a .txt, .pdf, or .docx file.')
        return redirect(url_for('index'))

@app.route('/search_jobs', methods=['POST'])
def search_jobs():
    """Handle job search with processed resume data"""
    logger.info("Job search request received")
    
    try:
        # Get data from form
        data = request.get_json()
        
        search_terms = data.get('search_terms', {})
        desired_position = data.get('desired_position', '')
        target_location = data.get('target_location', '')
        results_wanted = int(data.get('results_wanted', 10))
        filename = data.get('filename', 'resume')
        
        logger.info(f"Job search parameters - Position: {desired_position}, Location: {target_location}, Results: {results_wanted}")
        
        # Prepare search parameters
        primary_terms = search_terms.get("primary_search_terms", ["software engineer"])
        search_term = primary_terms[0] if primary_terms else "software engineer"
        
        # If desired position was specified, prioritize it in the search
        if desired_position and desired_position.lower() not in search_term.lower():
            search_term = f"{desired_position} {search_term}".strip()
        
        location = search_terms.get("location", target_location or "Remote")
        google_search = search_terms.get("google_search_string", f"{search_term} jobs near {location}")
        
        logger.info(f"Executing job search - Term: '{search_term}', Location: '{location}'")
        
        # Perform job search
        jobs = scrape_jobs(
            site_name=["indeed", "linkedin"],
            search_term=search_term,
            google_search_term=google_search,
            location=location,
            results_wanted=results_wanted,
            hours_old=72,
            country_indeed='USA'
        )
        
        logger.info(f"Job search completed - Found {len(jobs)} jobs")
        
        # Save results to CSV
        resume_name = os.path.splitext(filename.split('_', 1)[1] if '_' in filename else filename)[0]
        position_suffix = f"_{desired_position.replace(' ', '_').lower()}" if desired_position else ""
        output_file = f"ai_generated_jobs_{resume_name}{position_suffix}.csv"
        jobs.to_csv(output_file, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
        
        logger.info(f"Job results saved to: {output_file}")
        
        # Convert jobs DataFrame to list of dictionaries for JSON response
        jobs_list = []
        for i, job in jobs.iterrows():
            # Safely handle description field that might be float/NaN
            description = job.get('description', '')
            if not isinstance(description, str):
                # Convert non-string values (like float/NaN) to empty string
                if pd.isna(description):
                    description = ''
                else:
                    description = str(description)
            
            jobs_list.append({
                'title': job.get('title', 'N/A'),
                'company': job.get('company', 'N/A'),
                'location': job.get('location', 'N/A'),
                'site': job.get('site', 'N/A'),
                'job_url': job.get('job_url', ''),
                'description': description[:500] + '...' if description else '',
                'salary_min': job.get('salary_min', ''),
                'salary_max': job.get('salary_max', ''),
                'date_posted': str(job.get('date_posted', ''))
            })
        
        logger.info(f"Returning {len(jobs_list)} jobs to client")
        
        return jsonify({
            'success': True,
            'jobs': jobs_list,
            'count': len(jobs_list),
            'search_params': {
                'search_term': search_term,
                'location': location,
                'results_wanted': results_wanted
            },
            'output_file': output_file
        })
        
    except Exception as e:
        logger.error(f"Error during job search: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/download/<filename>')
def download_file(filename):
    """Download generated CSV file"""
    logger.info(f"File download requested: {filename}")
    try:
        return send_file(filename, as_attachment=True)
    except FileNotFoundError:
        logger.error(f"Download requested for non-existent file: {filename}")
        flash('File not found')
        return redirect(url_for('index'))

@app.route('/cache')
def cache_info():
    """Display cache information"""
    logger.info("Cache info page requested")
    processor = ResumeProcessor()
    cache_info = processor.get_cache_info()
    return render_template('cache.html', cache_info=cache_info)

@app.route('/clear_cache', methods=['POST'])
def clear_cache():
    """Clear the cache"""
    logger.info("Cache clear requested")
    processor = ResumeProcessor()
    processor.clear_cache()
    logger.info("Cache cleared successfully")
    flash('Cache cleared successfully')
    return redirect(url_for('cache_info'))

@app.errorhandler(413)
def too_large(e):
    logger.warning(f"File upload too large: {request.content_length} bytes")
    flash('File is too large. Maximum size is 16MB.')
    return redirect(url_for('index'))

@app.errorhandler(404)
def not_found(e):
    logger.warning(f"404 error for path: {request.path}")
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"500 internal server error: {str(e)}", exc_info=True)
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Check if OpenAI API key is set
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY not found in environment variables!")
        print("❌ Warning: OPENAI_API_KEY not found in environment variables!")
        print("Please set your OpenAI API key in the .env file")
    else:
        logger.info("OpenAI API key found in environment")
    
    logger.info("Starting SeekrAI application")
    logger.info(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    logger.info(f"Max content length: {app.config['MAX_CONTENT_LENGTH']} bytes")
    
    app.run(debug=True, host='0.0.0.0', port=5000) 