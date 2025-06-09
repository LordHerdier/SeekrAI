import os
import csv
import json
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
from jobspy import scrape_jobs
from resume_processor import ResumeProcessor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'doc'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Main page with upload form"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_resume():
    """Handle resume upload and initial processing"""
    if 'resume' not in request.files:
        flash('No file selected')
        return redirect(request.url)
    
    file = request.files['resume']
    if file.filename == '':
        flash('No file selected')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        # Save uploaded file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Get form data
        desired_position = request.form.get('desired_position', '').strip()
        target_location = request.form.get('target_location', '').strip()
        
        try:
            # Process the resume
            processor = ResumeProcessor()
            results = processor.process_resume(
                filepath, 
                target_location=target_location if target_location else None,
                desired_position=desired_position if desired_position else None
            )
            
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
            
            return render_template('results.html', data=session_data)
            
        except Exception as e:
            flash(f'Error processing resume: {str(e)}')
            # Clean up uploaded file on error
            if os.path.exists(filepath):
                os.remove(filepath)
            return redirect(url_for('index'))
    
    else:
        flash('Invalid file type. Please upload a .txt, .pdf, or .docx file.')
        return redirect(url_for('index'))

@app.route('/search_jobs', methods=['POST'])
def search_jobs():
    """Handle job search with processed resume data"""
    try:
        # Get data from form
        data = request.get_json()
        
        search_terms = data.get('search_terms', {})
        desired_position = data.get('desired_position', '')
        target_location = data.get('target_location', '')
        results_wanted = int(data.get('results_wanted', 10))
        filename = data.get('filename', 'resume')
        
        # Prepare search parameters
        primary_terms = search_terms.get("primary_search_terms", ["software engineer"])
        search_term = primary_terms[0] if primary_terms else "software engineer"
        
        # If desired position was specified, prioritize it in the search
        if desired_position and desired_position.lower() not in search_term.lower():
            search_term = f"{desired_position} {search_term}".strip()
        
        location = search_terms.get("location", target_location or "Remote")
        google_search = search_terms.get("google_search_string", f"{search_term} jobs near {location}")
        
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
        
        # Save results to CSV
        resume_name = os.path.splitext(filename.split('_', 1)[1] if '_' in filename else filename)[0]
        position_suffix = f"_{desired_position.replace(' ', '_').lower()}" if desired_position else ""
        output_file = f"ai_generated_jobs_{resume_name}{position_suffix}.csv"
        jobs.to_csv(output_file, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
        
        # Convert jobs DataFrame to list of dictionaries for JSON response
        jobs_list = []
        for i, job in jobs.iterrows():
            jobs_list.append({
                'title': job.get('title', 'N/A'),
                'company': job.get('company', 'N/A'),
                'location': job.get('location', 'N/A'),
                'site': job.get('site', 'N/A'),
                'job_url': job.get('job_url', ''),
                'description': job.get('description', '')[:500] + '...' if job.get('description', '') else '',
                'salary_min': job.get('salary_min', ''),
                'salary_max': job.get('salary_max', ''),
                'date_posted': str(job.get('date_posted', ''))
            })
        
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
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/download/<filename>')
def download_file(filename):
    """Download generated CSV file"""
    try:
        return send_file(filename, as_attachment=True)
    except FileNotFoundError:
        flash('File not found')
        return redirect(url_for('index'))

@app.route('/cache')
def cache_info():
    """Display cache information"""
    processor = ResumeProcessor()
    cache_info = processor.get_cache_info()
    return render_template('cache.html', cache_info=cache_info)

@app.route('/clear_cache', methods=['POST'])
def clear_cache():
    """Clear the cache"""
    processor = ResumeProcessor()
    processor.clear_cache()
    flash('Cache cleared successfully')
    return redirect(url_for('cache_info'))

@app.errorhandler(413)
def too_large(e):
    flash('File is too large. Maximum size is 16MB.')
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Check if OpenAI API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Warning: OPENAI_API_KEY not found in environment variables!")
        print("Please set your OpenAI API key in the .env file")
    
    app.run(debug=True, host='0.0.0.0', port=5000) 