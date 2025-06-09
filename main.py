import csv
import json
import argparse
from jobspy import scrape_jobs
from dotenv import load_dotenv
import os
from resume_processor import ResumeProcessor

load_dotenv()

def test_resume_processing_pipeline(resume_file="sample_resume.txt", target_location=None, results_wanted=5, desired_position=None):
    """Test the complete pipeline: resume -> keywords -> search terms -> job scraping"""
    
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
        results = processor.process_resume(resume_file, target_location, desired_position)
        
        print("\n" + "="*40)
        print("EXTRACTED KEYWORDS:")
        print("="*40)
        print(json.dumps(results["keywords"], indent=2))
        
        print("\n" + "="*40)
        print("GENERATED SEARCH TERMS:")
        print("="*40)
        print(json.dumps(results["search_terms"], indent=2))
        
        # Test job scraping with generated search terms
        if "search_terms" in results and results["search_terms"]:
            search_data = results["search_terms"]
            
            # Use primary search term for job scraping test
            primary_terms = search_data.get("primary_search_terms", ["software engineer"])
            search_term = primary_terms[0] if primary_terms else "software engineer"
            
            # If desired position was specified, prioritize it in the search
            if desired_position and desired_position.lower() not in search_term.lower():
                search_term = f"{desired_position} {search_term}".strip()
            
            location = search_data.get("location", target_location or "Remote")
            google_search = search_data.get("google_search_string", f"{search_term} jobs near {location}")
            
            print("\n" + "="*40)
            print("TESTING JOB SCRAPING:")
            print("="*40)
            print(f"Search Term: {search_term}")
            print(f"Location: {location}")
            print(f"Google Search: {google_search}")
            
            # Run a small test scrape
            print("\nStarting job scrape...")
            jobs = scrape_jobs(
                site_name=["indeed", "linkedin"],  # Limiting to 2 sites for testing
                search_term=search_term,
                google_search_term=google_search,
                location=location,
                results_wanted=results_wanted,
                hours_old=72,
                country_indeed='USA'
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

def test_openai_connection():
    """Test if OpenAI API is working"""
    print("Testing OpenAI API connection...")
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ OPENAI_API_KEY not found in environment variables!")
        return False
    
    print(f"✅ API Key found: {api_key[:10]}...{api_key[-5:]}")
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        # Test with a simple completion
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'API test successful'"}],
            max_tokens=10
        )
        
        print(f"✅ OpenAI API test successful: {response.choices[0].message.content}")
        return True
        
    except Exception as e:
        print(f"❌ OpenAI API test failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Resume-to-Job-Search Pipeline Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                                          # Use default sample_resume.txt
  python main.py -r my_resume.pdf                        # Test with PDF resume
  python main.py -r resume.docx -l "New York, NY"        # Specify location
  python main.py -r resume.txt -l "Remote" -n 10         # Get 10 job results
  python main.py -r resume.pdf -p "Data Scientist"       # Target specific position
  python main.py -r resume.txt -p "Senior DevOps Engineer" -l "Austin, TX" -n 8
  python main.py --test-api-only                         # Only test OpenAI connection
        """
    )
    
    parser.add_argument(
        "-r", "--resume", 
        type=str, 
        default="sample_resume.txt",
        help="Path to resume file (supports .txt, .pdf, .docx). Default: sample_resume.txt"
    )
    
    parser.add_argument(
        "-l", "--location", 
        type=str, 
        help="Target job location (overrides location from resume). Example: 'New York, NY' or 'Remote'"
    )
    
    parser.add_argument(
        "-p", "--position", 
        type=str, 
        help="Desired position/role to target (influences search term generation). Example: 'Data Scientist' or 'Senior Backend Engineer'"
    )
    
    parser.add_argument(
        "-n", "--num-jobs", 
        type=int, 
        default=5,
        help="Number of job results to fetch for testing. Default: 5"
    )
    
    parser.add_argument(
        "--test-api-only", 
        action="store_true",
        help="Only test OpenAI API connection, don't run full pipeline"
    )
    
    parser.add_argument(
        "--skip-scraping", 
        action="store_true",
        help="Skip job scraping, only test resume processing and keyword extraction"
    )
    
    args = parser.parse_args()
    
    # Check if resume file exists
    if not os.path.exists(args.resume):
        print(f"❌ Resume file not found: {args.resume}")
        print("Available files in current directory:")
        for file in os.listdir("."):
            if file.endswith((".txt", ".pdf", ".docx")):
                print(f"  - {file}")
        return
    
    # Test OpenAI connection first
    if not test_openai_connection():
        print("Please check your OpenAI API key and try again.")
        return
    
    if args.test_api_only:
        print("✅ API test completed successfully!")
        return
    
    print("\n")
    
    # Run the complete pipeline test
    if args.skip_scraping:
        print("Note: Skipping job scraping as requested")
        processor = ResumeProcessor()
        try:
            results = processor.process_resume(args.resume, args.location, args.position)
            print("\n" + "="*40)
            print("EXTRACTED KEYWORDS:")
            print("="*40)
            print(json.dumps(results["keywords"], indent=2))
            
            print("\n" + "="*40)
            print("GENERATED SEARCH TERMS:")
            print("="*40)
            print(json.dumps(results["search_terms"], indent=2))
            print("\n✅ Resume processing completed successfully!")
        except Exception as e:
            print(f"❌ Error processing resume: {e}")
    else:
        test_resume_processing_pipeline(args.resume, args.location, args.num_jobs, args.position)

if __name__ == "__main__":
    main()
    
    # Original job scraping code (commented out for reference)
    # jobs = scrape_jobs(
    #     site_name=["indeed", "linkedin", "zip_recruiter", "glassdoor", "google", "bayt", "naukri"],
    #     search_term="software engineer",
    #     google_search_term="software engineer jobs near St. Louis, MO since yesterday",
    #     location="St. Louis, MO",
    #     results_wanted=20,
    #     hours_old=72,
    #     country_indeed='USA',
        
    #     # linkedin_fetch_description=True # gets more info such as description, direct job url (slower)
    #     # proxies=["208.195.175.46:65095", "208.195.175.45:65095", "localhost"],
    # )
    # print(f"Found {len(jobs)} jobs")
    # print(jobs.head())
    # jobs.to_csv("jobs.csv", quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False) # to_excel