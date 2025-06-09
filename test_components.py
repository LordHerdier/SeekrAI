#!/usr/bin/env python3
"""
Test script for individual components of the resume processing pipeline.
This helps debug each part separately.
"""

import json
from dotenv import load_dotenv
from resume_processor import ResumeProcessor

load_dotenv()

def test_resume_reading():
    """Test just the resume reading functionality"""
    print("Testing resume reading...")
    processor = ResumeProcessor()
    
    try:
        content = processor.read_resume_file("sample_resume.txt")
        print(f"✅ Resume loaded successfully ({len(content)} characters)")
        print("First 200 characters:")
        print("-" * 40)
        print(content[:200] + "...")
        return True
    except Exception as e:
        print(f"❌ Resume reading failed: {e}")
        return False

def test_keyword_extraction():
    """Test just the keyword extraction"""
    print("\nTesting keyword extraction...")
    processor = ResumeProcessor()
    
    try:
        content = processor.read_resume_file("sample_resume.txt")
        keywords = processor.extract_keywords(content)
        
        print("✅ Keywords extracted successfully:")
        print(json.dumps(keywords, indent=2))
        return keywords
    except Exception as e:
        print(f"❌ Keyword extraction failed: {e}")
        return None

def test_search_term_generation(keywords_data):
    """Test search term generation with sample keywords"""
    print("\nTesting search term generation...")
    processor = ResumeProcessor()
    
    try:
        search_terms = processor.generate_search_terms(keywords_data, "St. Louis, MO")
        
        print("✅ Search terms generated successfully:")
        print(json.dumps(search_terms, indent=2))
        return search_terms
    except Exception as e:
        print(f"❌ Search term generation failed: {e}")
        return None

def run_component_tests():
    """Run all component tests individually"""
    print("="*50)
    print("COMPONENT-BY-COMPONENT TESTING")
    print("="*50)
    
    # Test 1: Resume reading
    if not test_resume_reading():
        return
    
    # Test 2: Keyword extraction
    keywords = test_keyword_extraction()
    if not keywords:
        return
    
    # Test 3: Search term generation
    search_terms = test_search_term_generation(keywords)
    if not search_terms:
        return
    
    print("\n" + "="*50)
    print("ALL COMPONENT TESTS PASSED! ✅")
    print("="*50)
    
    return {
        "keywords": keywords,
        "search_terms": search_terms
    }

if __name__ == "__main__":
    results = run_component_tests()
    
    if results:
        print("\nYou can now run the full pipeline with: python main.py") 