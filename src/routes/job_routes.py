import os
import csv
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from jobspy import scrape_jobs
from resume_processor import ResumeProcessor
from config_loader import get_config
import pandas as pd
import logging
import unicodedata
import re

# Create blueprint
job_bp = Blueprint('jobs', __name__)

def sanitize_string_for_json(value):
    """Sanitize a string value for safe JSON serialization"""
    if not isinstance(value, str):
        return value
    
    # First, normalize Unicode characters to ASCII where possible
    try:
        # Try to normalize unicode to ASCII equivalents
        normalized = unicodedata.normalize('NFKD', value)
        ascii_value = normalized.encode('ascii', 'ignore').decode('ascii')
    except:
        # If normalization fails, use original value
        ascii_value = value
    
    # Replace problematic characters and whitespace
    sanitized = (ascii_value.replace('\r\n', ' ')
                           .replace('\n', ' ')
                           .replace('\r', ' ')
                           .replace('\t', ' ')
                           .replace('"', "'")
                           .replace('\\', '/')
                           .replace('\x00', '')  # Remove null bytes
                           .strip())
    
    # Remove any remaining control characters
    sanitized = ''.join(char for char in sanitized if ord(char) >= 32 or char in ['\n', '\r', '\t'])
    
    # Collapse multiple spaces into single space
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    
    # Limit string length to prevent overly long values
    max_length = 1000
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "..."
    
    return sanitized

def sanitize_job_for_json(job_dict):
    """Sanitize a job dictionary for JSON serialization"""
    sanitized_job = {}
    for key, value in job_dict.items():
        if isinstance(value, str):
            sanitized_job[key] = sanitize_string_for_json(value)
        elif isinstance(value, list):
            # Handle list of strings
            sanitized_job[key] = [sanitize_string_for_json(item) if isinstance(item, str) else item for item in value]
        else:
            sanitized_job[key] = value
    return sanitized_job

@job_bp.route('/search_jobs', methods=['POST'])
def search_jobs():
    """Handle job search with processed resume data"""
    config = get_config()
    logging.info("Job search request received")
    
    try:
        # Get data from form
        data = request.get_json()
        
        search_terms = data.get('search_terms', {})
        desired_position = data.get('desired_position', '')
        target_location = data.get('target_location', '')
        results_wanted = int(data.get('results_wanted', config.get_default_job_results()))
        filename = data.get('filename', 'resume')
        
        logging.info(f"Job search parameters - Position: {desired_position}, Location: {target_location}, Results: {results_wanted}")
        
        # Prepare search parameters
        primary_terms = search_terms.get("primary_search_terms", ["software engineer"])
        search_term = primary_terms[0] if primary_terms else "software engineer"
        
        # If desired position was specified, prioritize it in the search
        if desired_position and desired_position.lower() not in search_term.lower():
            search_term = f"{desired_position} {search_term}".strip()
        
        location = search_terms.get("location", target_location or config.get('job_search.default_location', 'Remote'))
        google_search = search_terms.get("google_search_string", f"{search_term} jobs near {location}")
        
        logging.info(f"Executing job search - Term: '{search_term}', Location: '{location}'")
        
        # Perform job search
        jobs = scrape_jobs(
            site_name=config.get_job_search_sites(),
            search_term=search_term,
            google_search_term=google_search,
            location=location,
            results_wanted=results_wanted,
            hours_old=config.get_job_hours_old(),
            country_indeed=config.get('job_search.default_country', 'USA')
        )
        
        logging.info(f"Job search completed - Found {len(jobs)} jobs")
        
        # Job Analysis Step (NEW) - Analyze and rank jobs if enabled
        jobs_analyzed = False
        if config.get_job_analysis_enabled() and len(jobs) > 0:
            logging.info("Job analysis enabled - analyzing jobs for salary and similarity")
            
            try:
                # We need the keywords for analysis - get them from the data
                keywords = data.get('keywords', {})
                if not keywords:
                    logging.warning("No keywords available for job analysis")
                else:
                    # Initialize processor for job analysis
                    processor = ResumeProcessor()
                    
                    # Convert jobs DataFrame to list of dictionaries
                    jobs_list = jobs.to_dict('records')
                    
                    # Analyze and rank jobs
                    analyzed_jobs_list = processor.analyze_and_rank_jobs(
                        jobs_list, 
                        keywords, 
                        max_jobs=config.get_max_jobs_to_analyze()
                    )
                    
                    # Convert back to DataFrame
                    jobs = pd.DataFrame(analyzed_jobs_list)
                    jobs_analyzed = True
                    
                    analyzed_count = sum(1 for job in analyzed_jobs_list if job.get('analyzed', False))
                    logging.info(f"Job analysis completed - {analyzed_count}/{len(jobs)} jobs analyzed")
                    
            except Exception as e:
                logging.error(f"Error during job analysis: {str(e)}", exc_info=True)
                # Continue without analysis if it fails
        
        elif config.get_job_analysis_enabled():
            logging.info("Job analysis enabled but no jobs found to analyze")
        else:
            logging.info("Job analysis disabled in configuration")
        
        # Generate output filename and save to job results folder
        resume_name = os.path.splitext(filename.split('_', 1)[1] if '_' in filename else filename)[0]
        position_suffix = f"_{desired_position.replace(' ', '_').lower()}" if desired_position else ""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"jobs_{resume_name}{position_suffix}_{timestamp}.csv"
        output_path = os.path.join(current_app.config['JOB_RESULTS_FOLDER'], output_filename)
        
        # Save results to CSV
        jobs.to_csv(output_path, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
        
        logging.info(f"Job results saved to: {output_path}")
        
        # Convert jobs DataFrame to list of dictionaries for JSON response
        jobs_list = []
        description_max_length = config.get('job_search.description_max_length', 500)
        
        for i, job in jobs.iterrows():
            # Safely handle description field that might be float/NaN
            description = job.get('description', '')
            if not isinstance(description, str):
                # Convert non-string values (like float/NaN) to empty string
                if pd.isna(description):
                    description = ''
                else:
                    description = str(description)
            
            job_dict = {
                'title': job.get('title', 'N/A') if pd.notna(job.get('title', '')) else 'N/A',
                'company': job.get('company', 'N/A') if pd.notna(job.get('company', '')) else 'N/A',
                'location': job.get('location', 'N/A') if pd.notna(job.get('location', '')) else 'N/A',
                'site': job.get('site', 'N/A') if pd.notna(job.get('site', '')) else 'N/A',
                'job_url': job.get('job_url', '') if pd.notna(job.get('job_url', '')) else '',
                'description': description[:description_max_length] + '...' if description else '',
                'salary_min': job.get('salary_min', '') if pd.notna(job.get('salary_min', '')) else '',
                'salary_max': job.get('salary_max', '') if pd.notna(job.get('salary_max', '')) else '',
                'date_posted': str(job.get('date_posted', '')) if pd.notna(job.get('date_posted', '')) else ''
            }
            
            # Add analysis data if available
            if jobs_analyzed:
                job_dict.update({
                    'analyzed': job.get('analyzed', False),
                    'similarity_score': job.get('similarity_score', 0.0) if pd.notna(job.get('similarity_score', 0.0)) else 0.0,
                    'similarity_explanation': job.get('similarity_explanation', '') if pd.notna(job.get('similarity_explanation', '')) else '',
                    'salary_min_extracted': job.get('salary_min_extracted') if pd.notna(job.get('salary_min_extracted')) else None,
                    'salary_max_extracted': job.get('salary_max_extracted') if pd.notna(job.get('salary_max_extracted')) else None,
                    'salary_confidence': job.get('salary_confidence', 0.0) if pd.notna(job.get('salary_confidence', 0.0)) else 0.0,
                    'key_matches': job.get('key_matches', []) if isinstance(job.get('key_matches'), list) else [],
                    'missing_requirements': job.get('missing_requirements', []) if isinstance(job.get('missing_requirements'), list) else []
                })
            
            # Sanitize the job dictionary for JSON safety
            job_dict = sanitize_job_for_json(job_dict)
            jobs_list.append(job_dict)
        
        logging.info(f"Returning {len(jobs_list)} jobs to client")
        
        # Prepare response data
        response_data = {
            'success': True,
            'jobs': jobs_list,
            'count': len(jobs_list),
            'search_params': {
                'search_term': search_term,
                'location': location,
                'results_wanted': results_wanted
            },
            'output_file': output_filename,
            'analysis_enabled': config.get_job_analysis_enabled(),
            'jobs_analyzed': jobs_analyzed
        }
        
        # Add analysis summary if jobs were analyzed
        if jobs_analyzed:
            analyzed_count = sum(1 for job in jobs_list if job.get('analyzed', False))
            salary_extracted_count = sum(1 for job in jobs_list 
                                       if job.get('salary_min_extracted') or job.get('salary_max_extracted'))
            response_data['analysis_summary'] = {
                'analyzed_count': analyzed_count,
                'total_count': len(jobs_list),
                'salary_extracted_count': salary_extracted_count
            }
        
        # Try to serialize response and catch any JSON errors
        try:
            return jsonify(response_data)
        except (TypeError, ValueError) as e:
            logging.error(f"JSON serialization error: {str(e)}")
            logging.error("Response data structure causing the error:")
            
            # Log problematic fields for debugging
            for i, job in enumerate(jobs_list[:3]):  # Check first 3 jobs
                logging.error(f"Job {i} fields: {list(job.keys())}")
                for key, value in job.items():
                    if isinstance(value, str) and len(value) > 100:
                        logging.error(f"  Long field {key}: {repr(value[:100])}")
                    elif not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                        logging.error(f"  Non-serializable field {key}: {type(value)} = {repr(value)}")
            
            # Try to create a minimal safe response
            try:
                safe_response = {
                    'success': True,
                    'jobs': [],
                    'count': 0,
                    'search_params': response_data.get('search_params', {}),
                    'output_file': response_data.get('output_file', ''),
                    'analysis_enabled': response_data.get('analysis_enabled', False),
                    'jobs_analyzed': False,
                    'error_message': 'Job data contained characters that could not be displayed. Results saved to CSV file.'
                }
                logging.info("Returning safe fallback response due to serialization error")
                return jsonify(safe_response)
            except Exception as fallback_error:
                logging.error(f"Even fallback response failed: {str(fallback_error)}")
                # Return absolute minimal response
                return jsonify({
                    'success': False,
                    'error': 'Error formatting job results for display. Please check the CSV file for results.'
                }), 500
        
    except Exception as e:
        logging.error(f"Error during job search: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 