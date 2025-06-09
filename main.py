import csv
import json
import argparse
from jobspy import scrape_jobs
from dotenv import load_dotenv
import os
from resume_processor import ResumeProcessor
from config_loader import get_config

load_dotenv()
config = get_config()

def test_resume_processing_pipeline(resume_file="sample_resume.txt", target_location=None, results_wanted=None, desired_position=None):
    """Test the complete pipeline: resume -> keywords -> search terms -> job scraping"""
    
    # Use config defaults if not specified
    if results_wanted is None:
        results_wanted = config.get_default_job_results()
    
    # Initialize the resume processor
    processor = ResumeProcessor()
    
    print("="*60)
    print("TESTING RESUME PROCESSING PIPELINE")
    print("="*60)
    print(f"Resume File: {resume_file}")
    print(f"Target Location: {target_location or 'From resume'}")
    print(f"Desired Position: {desired_position or 'From resume analysis'}")
    print(f"Job Results Limit: {results_wanted}")
    print("="*60)
    
    try:
        # Process the resume
        results = processor.process_resume(
            resume_file, 
            target_location=target_location,
            desired_position=desired_position
        )
        
        if not results:
            print("❌ Failed to process resume")
            return None
            
        keywords_data = results["keywords"]
        search_terms = results["search_terms"]
        
        print("\n" + "="*40)
        print("EXTRACTED KEYWORDS")
        print("="*40)
        print(json.dumps(keywords_data, indent=2))
        
        print("\n" + "="*40)
        print("GENERATED SEARCH TERMS") 
        print("="*40)
        print(json.dumps(search_terms, indent=2))
        
        # Use the search terms for job scraping
        if search_terms:
            primary_terms = search_terms.get("primary_search_terms", ["software engineer"])
            search_term = primary_terms[0] if primary_terms else "software engineer"
            
            # If desired position was specified, prioritize it in the search
            if desired_position and desired_position.lower() not in search_term.lower():
                search_term = f"{desired_position} {search_term}".strip()
            
            location = search_terms.get("location", target_location or config.get('job_search.default_location', 'Remote'))
            google_search = search_terms.get("google_search_string", f"{search_term} jobs near {location}")
            
            print(f"\n🔍 Searching for jobs...")
            print(f"Search Term: {search_term}")
            print(f"Location: {location}")
            print(f"Google Search: {google_search}")
            
            jobs = scrape_jobs(
                site_name=config.get_job_search_sites(),
                search_term=search_term,
                google_search_term=google_search,
                location=location,
                results_wanted=results_wanted,
                hours_old=config.get_job_hours_old(),
                country_indeed=config.get('job_search.default_country', 'USA')
            )
            
            print(f"\nFound {len(jobs)} jobs")
            if len(jobs) > 0:
                print("\nFirst few job results:")
                print("-" * 40)
                for i, job in jobs.head(min(3, len(jobs))).iterrows():
                    print(f"Title: {job.get('title', 'N/A')}")
                    print(f"Company: {job.get('company', 'N/A')}")
                    print(f"Location: {job.get('location', 'N/A')}")
                    print(f"Site: {job.get('site', 'N/A')}")
                    print("-" * 40)
                
                # Save results with resume-specific filename
                resume_name = os.path.splitext(os.path.basename(resume_file))[0]
                position_suffix = f"_{desired_position.replace(' ', '_').lower()}" if desired_position else ""
                output_file = f"ai_generated_jobs_{resume_name}{position_suffix}.csv"
                jobs.to_csv(output_file, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
                print(f"\nResults saved to {output_file}")
                
        print("\n" + "="*60)
        print("PIPELINE TEST COMPLETED SUCCESSFULLY!")
        print("="*60)
        
        return results
        
    except Exception as e:
        print(f"Error in pipeline: {e}")
        import traceback
        traceback.print_exc()
        return None

def simple_resume_test(resume_file="sample_resume.txt", target_location=None, desired_position=None):
    """Simple test that only processes the resume without job scraping"""
    print("="*50)
    print("RESUME PROCESSING TEST (NO JOB SCRAPING)")
    print("="*50)
    
    try:
        processor = ResumeProcessor()
        results = processor.process_resume(
            resume_file,
            target_location=target_location,
            desired_position=desired_position
        )
        
        if results:
            print("\n✅ Resume processing successful!")
            print(f"Keywords extracted: {len(results.get('keywords', {}))}")
            print(f"Search terms generated: {len(results.get('search_terms', {}))}")
            print("\nKeywords:")
            print(json.dumps(results.get("keywords", {}), indent=2))
            print("\nSearch Terms:")
            print(json.dumps(results.get("search_terms", {}), indent=2))
        else:
            print("❌ Resume processing failed")
            
        return results
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def show_cache_info():
    """Display cache information"""
    processor = ResumeProcessor()
    cache_info = processor.get_cache_info()
    
    print("="*40)
    print("CACHE INFORMATION")
    print("="*40)
    print(f"Cache Directory: {cache_info['cache_directory']}")
    print(f"Cache Files: {cache_info['cache_files_count']}")
    print(f"Total Size: {cache_info['total_size_mb']} MB")
    print(f"Expiration: {config.get_cache_expiration_days()} days")
    
    if cache_info['cache_files']:
        print("\nCache Files:")
        for file_info in cache_info['cache_files']:
            status = "EXPIRED" if file_info['is_expired'] else "VALID"
            print(f"  {file_info['key'][:12]}... | {file_info['size_kb']} KB | {file_info['created']} | {status}")
    
    print("="*40)
    return cache_info

def clear_cache():
    """Clear the cache"""
    processor = ResumeProcessor()
    processor.clear_cache()

def main():
    parser = argparse.ArgumentParser(description="SeekrAI - AI-powered resume processing and job search")
    parser.add_argument("-r", "--resume", type=str, help="Path to resume file")
    parser.add_argument("-p", "--position", type=str, help="Desired job position")
    parser.add_argument("-l", "--location", type=str, help="Target location")
    parser.add_argument("-n", "--num-jobs", type=int, help=f"Number of jobs to search (default: {config.get_default_job_results()})")
    parser.add_argument("--skip-scraping", action="store_true", help="Skip job scraping, only process resume")
    parser.add_argument("--cache-info", action="store_true", help="Show cache information")
    parser.add_argument("--clear-cache", action="store_true", help="Clear the cache")
    parser.add_argument("--no-cache", action="store_true", help="Force fresh API calls (bypass cache)")
    parser.add_argument("--config-test", action="store_true", help="Test configuration loading")
    
    args = parser.parse_args()
    
    # Configuration test
    if args.config_test:
        print("="*50)
        print("CONFIGURATION TEST")
        print("="*50)
        print(f"OpenAI Model: {config.get_openai_model()}")
        print(f"OpenAI Temperature: {config.get_openai_temperature()}")
        print(f"Cache Directory: {config.get_cache_directory()}")
        print(f"Cache Expiration: {config.get_cache_expiration_days()} days")
        print(f"Upload Folder: {config.get_upload_folder()}")
        print(f"Max File Size: {config.get('files.max_file_size_mb', 16)} MB")
        print(f"Allowed Extensions: {config.get_allowed_extensions()}")
        print(f"Job Search Sites: {config.get_job_search_sites()}")
        print(f"Default Job Results: {config.get_default_job_results()}")
        print(f"Job Hours Old: {config.get_job_hours_old()}")
        print(f"Professional Domains: {config.get_professional_domains()}")
        print(f"PII Removal Enabled: {config.get('resume_processing.pii_removal.enabled', True)}")
        print("="*50)
        return
    
    # Cache operations
    if args.cache_info:
        show_cache_info()
        return
        
    if args.clear_cache:
        clear_cache()
        print("✅ Cache cleared")
        return
    
    # Resume processing
    if args.resume:
        if not os.path.exists(args.resume):
            print(f"❌ Resume file not found: {args.resume}")
            return
            
        if args.skip_scraping:
            simple_resume_test(
                resume_file=args.resume,
                target_location=args.location,
                desired_position=args.position
            )
        else:
            test_resume_processing_pipeline(
                resume_file=args.resume,
                target_location=args.location,
                results_wanted=args.num_jobs,
                desired_position=args.position
            )
    else:
        # Default test with sample resume if it exists
        sample_resume = "sample_resume.txt"
        if os.path.exists(sample_resume):
            print("No resume specified, using sample_resume.txt")
            test_resume_processing_pipeline(
                resume_file=sample_resume,
                target_location=args.location,
                results_wanted=args.num_jobs,
                desired_position=args.position
            )
        else:
            print("❌ No resume file specified and sample_resume.txt not found")
            print("Usage: python main.py -r <resume_file> [-p <position>] [-l <location>] [-n <num_jobs>]")
            print("       python main.py --cache-info")
            print("       python main.py --clear-cache")
            print("       python main.py --config-test")

if __name__ == "__main__":
    main()