#!/usr/bin/env python3
"""
Demonstration script for PII removal and caching features
"""

from resume_processor import ResumeProcessor
import time

def test_pii_removal():
    """Test the PII removal functionality"""
    print("🛡️  Testing PII Removal")
    print("=" * 50)
    
    # Create a test resume with obvious PII
    test_resume = """
John Doe
Senior Software Engineer
Email: john.doe@gmail.com
Phone: (555) 123-4567
Address: 123 Main Street, Springfield, IL 62701

Personal Website: https://johndoe-portfolio.com
LinkedIn: https://linkedin.com/in/johndoe
GitHub: https://github.com/johndoe

PROFESSIONAL SUMMARY
Experienced software engineer with 5+ years...
"""
    
    processor = ResumeProcessor()
    
    print("Original content (first 200 chars):")
    print("-" * 30)
    print(test_resume[:200] + "...")
    print()
    
    anonymized = processor.anonymize_resume(test_resume)
    
    print("Anonymized content (first 200 chars):")
    print("-" * 30)
    print(anonymized[:200] + "...")
    print()

def test_caching():
    """Test the caching functionality"""
    print("💾 Testing Caching System")
    print("=" * 50)
    
    processor = ResumeProcessor()
    
    # Clear cache to start fresh
    processor.clear_cache()
    
    # Show initial cache info
    cache_info = processor.get_cache_info()
    print(f"Initial cache: {cache_info['cache_files']} files")
    
    # Test with sample resume
    print("\n🔄 First run (should hit API):")
    start_time = time.time()
    try:
        results = processor.process_resume("sample_resume.txt")
        first_run_time = time.time() - start_time
        print(f"⏱️  First run took {first_run_time:.2f} seconds")
        
        # Show cache info after first run
        cache_info = processor.get_cache_info()
        print(f"💾 Cache after first run: {cache_info['cache_files']} files, {cache_info['total_size']} bytes")
        
    except Exception as e:
        print(f"❌ Error in first run: {e}")
        return
    
    print("\n🔄 Second run (should use cache):")
    start_time = time.time()
    try:
        results = processor.process_resume("sample_resume.txt")
        second_run_time = time.time() - start_time
        print(f"⏱️  Second run took {second_run_time:.2f} seconds")
        
        speedup = first_run_time / second_run_time if second_run_time > 0 else float('inf')
        print(f"🚀 Speedup: {speedup:.1f}x faster with cache!")
        
    except Exception as e:
        print(f"❌ Error in second run: {e}")
    
    # Show final cache info
    cache_info = processor.get_cache_info()
    print(f"\n📊 Final cache stats:")
    print(f"   Files: {cache_info['cache_files']}")
    print(f"   Total size: {cache_info['total_size']} bytes")
    print(f"   Directory: {cache_info['cache_dir']}")

def main():
    print("🧪 Testing New Features: PII Removal & Caching")
    print("=" * 60)
    print()
    
    # Test 1: PII Removal
    test_pii_removal()
    print()
    
    # Test 2: Caching (requires API key)
    import os
    if os.getenv("OPENAI_API_KEY"):
        test_caching()
    else:
        print("⚠️  Skipping cache test - OPENAI_API_KEY not found")
        print("   Set your API key to test caching functionality")
    
    print()
    print("✅ Feature testing completed!")
    print()
    print("💡 Tips:")
    print("   - Use 'python main.py --cache-info' to see cache status")
    print("   - Use 'python main.py --clear-cache' to clear cache")
    print("   - Use 'python main.py --no-cache' to force fresh API calls")

if __name__ == "__main__":
    main() 