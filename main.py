import csv
import json
from jobspy import scrape_jobs
from dotenv import load_dotenv
import os
from resume_processor import ResumeProcessor

load_dotenv()

def test_resume_processing_pipeline():
    """Test the complete pipeline: resume -> keywords -> search terms -> job scraping"""
    
    # Initialize the resume processor
    processor = ResumeProcessor()
    
    # Test with our sample resume
    resume_file = "sample_resume.txt"
    target_location = "St. Louis, MO"  # You can change this or make it None to use resume location
    
    print("="*60)
    print("TESTING RESUME PROCESSING PIPELINE")
    print("="*60)
    
    try:
        # Process the resume
        results = processor.process_resume(resume_file, target_location)
        
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
            
            location = search_data.get("location", target_location)
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
                results_wanted=5,  # Small number for testing
                hours_old=72,
                country_indeed='USA'
            )
            
            print(f"\nFound {len(jobs)} jobs")
            if len(jobs) > 0:
                print("\nFirst few job results:")
                print("-" * 40)
                for i, job in jobs.head(3).iterrows():
                    print(f"Title: {job.get('title', 'N/A')}")
                    print(f"Company: {job.get('company', 'N/A')}")
                    print(f"Location: {job.get('location', 'N/A')}")
                    print(f"Site: {job.get('site', 'N/A')}")
                    print("-" * 40)
                
                # Save results
                output_file = "ai_generated_jobs.csv"
                jobs.to_csv(output_file, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
                print(f"\nResults saved to {output_file}")
                
        print("\n" + "="*60)
        print("PIPELINE TEST COMPLETED SUCCESSFULLY!")
        print("="*60)
        
    except Exception as e:
        print(f"Error in pipeline: {e}")
        import traceback
        traceback.print_exc()

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

if __name__ == "__main__":
    # Test OpenAI connection first
    if test_openai_connection():
        print("\n")
        # Run the complete pipeline test
        test_resume_processing_pipeline()
    else:
        print("Please check your OpenAI API key and try again.")
        
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