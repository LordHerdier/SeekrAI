#!/usr/bin/env python3
"""
Test script for individual components of the resume processing pipeline.
This helps debug each part separately.
"""

import json
import argparse
import os
from dotenv import load_dotenv
from resume_processor import ResumeProcessor

load_dotenv()

def test_resume_reading(resume_file):
    """Test just the resume reading functionality"""
    print(f"Testing resume reading: {resume_file}")
    processor = ResumeProcessor()
    
    try:
        content = processor.read_resume_file(resume_file)
        print(f"✅ Resume loaded successfully ({len(content)} characters)")
        print("First 200 characters:")
        print("-" * 40)
        print(content[:200] + "...")
        return True
    except Exception as e:
        print(f"❌ Resume reading failed: {e}")
        return False

def test_keyword_extraction(resume_file):
    """Test just the keyword extraction"""
    print(f"\nTesting keyword extraction: {resume_file}")
    processor = ResumeProcessor()
    
    try:
        content = processor.read_resume_file(resume_file)
        keywords = processor.extract_keywords(content)
        
        print("✅ Keywords extracted successfully:")
        print(json.dumps(keywords, indent=2))
        return keywords
    except Exception as e:
        print(f"❌ Keyword extraction failed: {e}")
        return None

def test_search_term_generation(keywords_data, target_location, desired_position):
    """Test search term generation with sample keywords"""
    location_text = target_location or "Not specified"
    position_text = desired_position or "Not specified"
    print(f"\nTesting search term generation (location: {location_text}, position: {position_text})...")
    processor = ResumeProcessor()
    
    try:
        search_terms = processor.generate_search_terms(keywords_data, target_location, desired_position)
        
        print("✅ Search terms generated successfully:")
        print(json.dumps(search_terms, indent=2))
        return search_terms
    except Exception as e:
        print(f"❌ Search term generation failed: {e}")
        return None

def run_component_tests(resume_file, target_location, desired_position):
    """Run all component tests individually"""
    print("="*50)
    print("COMPONENT-BY-COMPONENT TESTING")
    print("="*50)
    print(f"Resume File: {resume_file}")
    print(f"Target Location: {target_location or 'From resume'}")
    print(f"Desired Position: {desired_position or 'From resume analysis'}")
    print("="*50)
    
    # Test 1: Resume reading
    if not test_resume_reading(resume_file):
        return
    
    # Test 2: Keyword extraction
    keywords = test_keyword_extraction(resume_file)
    if not keywords:
        return
    
    # Test 3: Search term generation
    search_terms = test_search_term_generation(keywords, target_location, desired_position)
    if not search_terms:
        return
    
    print("\n" + "="*50)
    print("ALL COMPONENT TESTS PASSED! ✅")
    print("="*50)
    
    return {
        "keywords": keywords,
        "search_terms": search_terms
    }

def main():
    parser = argparse.ArgumentParser(
        description="Test individual components of the resume processing pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_components.py                               # Use default sample_resume.txt
  python test_components.py -r my_resume.pdf             # Test with PDF resume
  python test_components.py -r resume.docx -l "Remote"   # Test with location override
  python test_components.py -r resume.txt -p "Data Scientist"  # Test targeting specific position
  python test_components.py -r resume.pdf -p "ML Engineer" -l "San Francisco, CA"  # Full test
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
        help="Target job location for search term generation. Example: 'New York, NY' or 'Remote'"
    )
    
    parser.add_argument(
        "-p", "--position", 
        type=str, 
        help="Desired position/role to target. Example: 'Data Scientist' or 'Senior Backend Engineer'"
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
    
    results = run_component_tests(args.resume, args.location, args.position)
    
    if results:
        print(f"\nYou can now run the full pipeline with:")
        cmd = f"python main.py -r {args.resume}"
        if args.location:
            cmd += f' -l "{args.location}"'
        if args.position:
            cmd += f' -p "{args.position}"'
        print(cmd)

if __name__ == "__main__":
    main() 