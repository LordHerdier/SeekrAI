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
        
        # **FIX: Ensure we don't return more jobs than requested**
        initial_job_count = len(jobs)
        if len(jobs) > results_wanted:
            logging.info(f"Job scraper returned {len(jobs)} jobs, truncating to requested {results_wanted}")
            jobs = jobs.head(results_wanted)
        
        logging.info(f"Job search completed - Found {initial_job_count} jobs, using {len(jobs)} jobs (requested: {results_wanted})")
        
        # **FIX: Validate that we have the expected number of jobs**
        final_job_count = len(jobs)
        if final_job_count != results_wanted:
            logging.warning(f"Job count mismatch after truncation: requested {results_wanted}, have {final_job_count}")
        
        # Job Analysis Step (NEW) - Analyze and rank jobs if enabled
        jobs_analyzed = False
        analysis_summary = None
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
                    
                    # **FIX: Set analysis limit to match the actual job count we're returning**
                    # This ensures all jobs get analyzed (or none do), eliminating partial analysis
                    analysis_limit = len(jobs_list)  # Analyze all jobs we're returning
                    max_configured_analysis = config.get_max_jobs_to_analyze()
                    
                    if max_configured_analysis > 0 and analysis_limit > max_configured_analysis:
                        logging.info(f"Analysis limit ({max_configured_analysis}) is less than job count ({analysis_limit})")
                        logging.info(f"Will analyze first {max_configured_analysis} jobs, others will get default analysis")
                        analysis_limit = max_configured_analysis
                    
                    # **FIX: Additional validation to ensure configuration consistency**
                    if analysis_limit != len(jobs_list):
                        logging.warning(f"Analysis limit ({analysis_limit}) differs from job count ({len(jobs_list)})")
                        logging.warning("This may result in some jobs not being analyzed")
                    
                    logging.info(f"Starting job analysis: {len(jobs_list)} jobs total, analyzing {analysis_limit}")
                    
                    # Analyze and rank jobs
                    analyzed_jobs_list = processor.analyze_and_rank_jobs(
                        jobs_list, 
                        keywords, 
                        max_jobs=analysis_limit
                    )
                    
                    # **FIX: Validate job count after analysis**
                    if len(analyzed_jobs_list) != len(jobs_list):
                        logging.error(f"Job count changed during analysis: before={len(jobs_list)}, after={len(analyzed_jobs_list)}")
                        # This should not happen, but if it does, we need to know
                        
                    # Convert back to DataFrame
                    jobs = pd.DataFrame(analyzed_jobs_list)
                    jobs_analyzed = True
                    
                    analyzed_count = sum(1 for job in analyzed_jobs_list if job.get('analyzed', False))
                    salary_extracted_count = sum(1 for job in analyzed_jobs_list 
                                               if job.get('salary_min_extracted') or job.get('salary_max_extracted'))
                    
                    analysis_summary = {
                        'analyzed_count': analyzed_count,
                        'total_count': len(analyzed_jobs_list),
                        'salary_extracted_count': salary_extracted_count
                    }
                    
                    logging.info(f"Job analysis completed - {analyzed_count}/{len(jobs)} jobs analyzed, {salary_extracted_count} with salary data")
                    
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
        
        # **FIX: Final validation before returning response**
        if len(jobs_list) != results_wanted:
            logging.warning(f"Final job count validation: requested {results_wanted}, returning {len(jobs_list)}")
            if len(jobs_list) > results_wanted:
                logging.error(f"Still returning more jobs than requested! Truncating {len(jobs_list)} to {results_wanted}")
                jobs_list = jobs_list[:results_wanted]
        
        # Prepare response data
        response_data = {
            'success': True,
            'jobs': jobs_list,
            'count': len(jobs_list),
            'search_params': {
                'search_term': search_term,
                'location': location,
                'results_wanted': results_wanted,
                'initial_scraped_count': initial_job_count,  # Add visibility into what happened
                'final_returned_count': len(jobs_list)
            },
            'output_file': output_filename,
            'analysis_enabled': config.get_job_analysis_enabled(),
            'jobs_analyzed': jobs_analyzed,
            'analysis_summary': analysis_summary
        }
        
        # **FIX: Log comprehensive summary of what we're returning**
        logging.info(f"Job search summary - Requested: {results_wanted}, Scraped: {initial_job_count}, Returned: {len(jobs_list)}")
        if jobs_analyzed and analysis_summary:
            logging.info(f"Analysis summary - Analyzed: {analysis_summary.get('analyzed_count', 0)}/{analysis_summary.get('total_count', 0)}, Salary extracted: {analysis_summary.get('salary_extracted_count', 0)}")
        
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