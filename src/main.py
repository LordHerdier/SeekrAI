#!/usr/bin/env python3
"""
SeekrAI - AI-Powered Job Search Tool
Command Line Interface for resume processing and job searching
"""

import csv
import json
import argparse
import os
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from jobspy import scrape_jobs
from processors.resume_processor import ResumeProcessor
from config_loader import get_config
from utils.logging_setup import setup_logging

# Load environment variables
load_dotenv()

# Initialize configuration and logging
config = get_config()
logger = setup_logging()

def test_resume_processing_pipeline(resume_file, target_location=None, desired_position=None, results_wanted=None):
    """
    Test the complete resume processing pipeline including job scraping
    
    Args:
        resume_file (str): Path to the resume file
        target_location (str, optional): Target job location
        desired_position (str, optional): Desired job position
        results_wanted (int, optional): Number of job results to return
    """
    logger.info(f"=== Starting Resume Processing Pipeline Test ===")
    logger.info(f"Resume file: {resume_file}")
    logger.info(f"Target location: {target_location}")
    logger.info(f"Desired position: {desired_position}")
    logger.info(f"Results wanted: {results_wanted}")
    
    try:
        # Initialize processor
        processor = ResumeProcessor()
        
        # Step 1: Process resume
        logger.info("Step 1: Processing resume...")
        resume_results = processor.process_resume(
            resume_file,
            target_location=target_location,
            desired_position=desired_position
        )
        
        keywords = resume_results.get('keywords', {})
        search_terms = resume_results.get('search_terms', {})
        
        logger.info(f"✓ Resume processed successfully")
        logger.info(f"  - Keywords extracted: {len(keywords)}")
        logger.info(f"  - Search terms generated: {len(search_terms)}")
        
        # Step 2: Perform job search
        logger.info("Step 2: Performing job search...")
        
        # Prepare search parameters
        primary_terms = search_terms.get("primary_search_terms", ["software engineer"])
        search_term = primary_terms[0] if primary_terms else "software engineer"
        
        # If desired position was specified, prioritize it in the search
        if desired_position and desired_position.lower() not in search_term.lower():
            search_term = f"{desired_position} {search_term}".strip()
        
        location = search_terms.get("location", target_location or config.get('job_search.default_location', 'Remote'))
        google_search = search_terms.get("google_search_string", f"{search_term} jobs near {location}")
        
        # Use provided results count or default from config
        if results_wanted is None:
            results_wanted = config.get_default_job_results()
        
        logger.info(f"  - Search term: '{search_term}'")
        logger.info(f"  - Location: '{location}'")
        logger.info(f"  - Results wanted: {results_wanted}")
        
        # Perform job search using jobspy
        jobs = scrape_jobs(
            site_name=config.get_job_search_sites(),
            search_term=search_term,
            google_search_term=google_search,
            location=location,
            results_wanted=results_wanted,
            hours_old=config.get_job_hours_old(),
            country_indeed=config.get('job_search.default_country', 'USA')
        )
        
        logger.info(f"✓ Job search completed - Found {len(jobs)} jobs")
        
        # Step 3: Job Analysis (if enabled)
        jobs_analyzed = False
        if config.get_job_analysis_enabled() and len(jobs) > 0:
            logger.info("Step 3: Analyzing jobs...")
            
            try:
                # Convert jobs DataFrame to list of dictionaries
                jobs_list = jobs.to_dict('records')
                
                # Analyze and rank jobs
                analyzed_jobs_list = processor.analyze_and_rank_jobs(
                    jobs_list, 
                    keywords, 
                    max_jobs=config.get_max_jobs_to_analyze()
                )
                
                # Convert back to DataFrame
                import pandas as pd
                jobs = pd.DataFrame(analyzed_jobs_list)
                jobs_analyzed = True
                
                analyzed_count = sum(1 for job in analyzed_jobs_list if job.get('analyzed', False))
                logger.info(f"✓ Job analysis completed - {analyzed_count}/{len(jobs)} jobs analyzed")
                
            except Exception as e:
                logger.error(f"Error during job analysis: {str(e)}", exc_info=True)
                logger.warning("Continuing without job analysis...")
        
        # Step 4: Save results
        logger.info("Step 4: Saving results...")
        
        # Generate output filename
        resume_name = Path(resume_file).stem
        position_suffix = f"_{desired_position.replace(' ', '_').lower()}" if desired_position else ""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"jobs_{resume_name}{position_suffix}_{timestamp}.csv"
        
        # Ensure job results directory exists
        job_results_folder = config.get('files.job_results_folder', 'job_results')
        os.makedirs(job_results_folder, exist_ok=True)
        
        output_path = os.path.join(job_results_folder, output_filename)
        
        # Save results to CSV
        jobs.to_csv(output_path, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
        
        logger.info(f"✓ Results saved to: {output_path}")
        
        # Summary
        logger.info(f"=== Pipeline Test Complete ===")
        logger.info(f"Total jobs found: {len(jobs)}")
        if jobs_analyzed:
            analyzed_count = sum(1 for _, job in jobs.iterrows() if job.get('analyzed', False))
            logger.info(f"Jobs analyzed: {analyzed_count}")
        logger.info(f"Results file: {output_filename}")
        
        return {
            'success': True,
            'jobs_count': len(jobs),
            'jobs_analyzed': jobs_analyzed,
            'output_file': output_path,
            'keywords': keywords,
            'search_terms': search_terms
        }
        
    except Exception as e:
        logger.error(f"Pipeline test failed: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }

def simple_resume_test(resume_file, target_location=None, desired_position=None):
    """
    Simple test to process resume without job searching
    
    Args:
        resume_file (str): Path to the resume file
        target_location (str, optional): Target job location
        desired_position (str, optional): Desired job position
    """
    logger.info(f"=== Starting Simple Resume Test ===")
    logger.info(f"Resume file: {resume_file}")
    
    try:
        # Initialize processor
        processor = ResumeProcessor()
        
        # Process resume
        logger.info("Processing resume...")
        results = processor.process_resume(
            resume_file,
            target_location=target_location,
            desired_position=desired_position
        )
        
        keywords = results.get('keywords', {})
        search_terms = results.get('search_terms', {})
        
        logger.info(f"✓ Resume processed successfully")
        logger.info(f"Keywords extracted: {len(keywords)}")
        logger.info(f"Search terms generated: {len(search_terms)}")
        
        # Display some results
        print("\n=== KEYWORDS ===")
        for category, items in keywords.items():
            if items:
                print(f"{category.upper()}: {', '.join(items[:5])}{'...' if len(items) > 5 else ''}")
        
        print("\n=== SEARCH TERMS ===")
        for category, items in search_terms.items():
            if isinstance(items, list):
                print(f"{category.upper()}: {', '.join(items[:3])}{'...' if len(items) > 3 else ''}")
            else:
                print(f"{category.upper()}: {items}")
        
        return {
            'success': True,
            'keywords': keywords,
            'search_terms': search_terms
        }
        
    except Exception as e:
        logger.error(f"Simple resume test failed: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }

def show_cache_info():
    """Display cache information"""
    logger.info("Displaying cache information")
    
    try:
        processor = ResumeProcessor()
        cache_info = processor.get_cache_info()
        
        print("\n=== CACHE INFORMATION ===")
        print(f"Cache Directory: {cache_info.get('cache_directory', 'N/A')}")
        print(f"Total Cache Files: {cache_info.get('total_files', 0)}")
        print(f"Total Cache Size: {cache_info.get('total_size_mb', 0):.2f} MB")
        
        if cache_info.get('files'):
            print("\nCache Files:")
            for file_info in cache_info['files'][:10]:  # Show first 10 files
                print(f"  - {file_info['name']} ({file_info['size_mb']:.2f} MB)")
            
            if len(cache_info['files']) > 10:
                print(f"  ... and {len(cache_info['files']) - 10} more files")
        
    except Exception as e:
        logger.error(f"Error displaying cache info: {str(e)}")
        print(f"Error: {str(e)}")

def clear_cache():
    """Clear the application cache"""
    logger.info("Clearing application cache")
    
    try:
        processor = ResumeProcessor()
        processor.clear_cache()
        logger.info("✓ Cache cleared successfully")
        print("Cache cleared successfully!")
        
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        print(f"Error clearing cache: {str(e)}")

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="SeekrAI - AI-Powered Job Search Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py test resume.pdf --position "Software Engineer" --location "San Francisco, CA" --results 50
  python main.py simple resume.pdf --position "Data Scientist"
  python main.py cache-info
  python main.py clear-cache
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Test command (full pipeline)
    test_parser = subparsers.add_parser('test', help='Test full resume processing pipeline with job search')
    test_parser.add_argument('resume_file', help='Path to resume file')
    test_parser.add_argument('--position', help='Desired job position')
    test_parser.add_argument('--location', help='Target job location')
    test_parser.add_argument('--results', type=int, help='Number of job results to fetch')
    
    # Simple command (resume processing only)
    simple_parser = subparsers.add_parser('simple', help='Simple resume processing without job search')
    simple_parser.add_argument('resume_file', help='Path to resume file')
    simple_parser.add_argument('--position', help='Desired job position')
    simple_parser.add_argument('--location', help='Target job location')
    
    # Cache commands
    subparsers.add_parser('cache-info', help='Show cache information')
    subparsers.add_parser('clear-cache', help='Clear application cache')
    
    args = parser.parse_args()
    
    if args.command == 'test':
        if not os.path.exists(args.resume_file):
            print(f"Error: Resume file '{args.resume_file}' not found")
            return 1
        
        result = test_resume_processing_pipeline(
            args.resume_file,
            target_location=args.location,
            desired_position=args.position,
            results_wanted=args.results
        )
        
        if result['success']:
            print("✓ Pipeline test completed successfully!")
            return 0
        else:
            print(f"✗ Pipeline test failed: {result['error']}")
            return 1
    
    elif args.command == 'simple':
        if not os.path.exists(args.resume_file):
            print(f"Error: Resume file '{args.resume_file}' not found")
            return 1
        
        result = simple_resume_test(
            args.resume_file,
            target_location=args.location,
            desired_position=args.position
        )
        
        if result['success']:
            print("✓ Simple resume test completed successfully!")
            return 0
        else:
            print(f"✗ Simple resume test failed: {result['error']}")
            return 1
    
    elif args.command == 'cache-info':
        show_cache_info()
        return 0
    
    elif args.command == 'clear-cache':
        clear_cache()
        return 0
    
    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    exit(main())