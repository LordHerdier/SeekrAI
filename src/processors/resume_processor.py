import os
import json
import logging
from datetime import datetime
from typing import List, Dict
from openai import OpenAI
from config_loader import get_config
from .file_reader import FileReader
from .pii_anonymizer import PIIAnonymizer
from .cache_manager import CacheManager
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import time


class ResumeProcessor:
    """Main orchestrator for resume processing operations"""
    
    def __init__(self, cache_dir: str = None):
        self.config = get_config()
        self.client = OpenAI(api_key=self.config.get_openai_api_key())
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Initialize component processors
        self.file_reader = FileReader()
        self.pii_anonymizer = PIIAnonymizer()
        self.cache_manager = CacheManager(cache_dir)
    
    def process_resume(self, resume_file_path: str, target_location: str = None, desired_position: str = None) -> Dict:
        """Main entry point for processing a resume file"""
        self.logger.info(f"Starting resume processing for: {resume_file_path}")
        
        try:
            # Step 1: Read resume file
            self.logger.info("Step 1: Reading resume file")
            resume_content = self.file_reader.read_resume_file(resume_file_path)
            self.logger.info(f"Resume content read successfully: {len(resume_content)} characters")
            
            # Step 2: Anonymize PII if enabled
            self.logger.info("Step 2: Anonymizing PII")
            anonymized_content = self.pii_anonymizer.anonymize_resume(resume_content)
            
            # Step 3: Extract keywords using AI
            self.logger.info("Step 3: Extracting keywords from resume")
            keywords_data = self.extract_keywords(anonymized_content)
            
            if not keywords_data:
                raise ValueError("Failed to extract keywords from resume")
            
            # Step 4: Generate search terms
            self.logger.info("Step 4: Generating job search terms")
            search_terms = self.generate_search_terms(keywords_data, target_location, desired_position)
            
            if not search_terms:
                raise ValueError("Failed to generate search terms")
            
            results = {
                "keywords": keywords_data,
                "search_terms": search_terms
            }
            
            self.logger.info("Resume processing completed successfully")
            return results
            
        except Exception as e:
            self.logger.error(f"Error processing resume: {str(e)}", exc_info=True)
            raise
    
    def extract_keywords(self, resume_content: str) -> Dict:
        """Extract keywords from resume content using AI"""
        self.logger.debug("Starting keyword extraction")
        
        # Check cache first
        cache_key = self.cache_manager.generate_cache_key(resume_content, "extract_keywords")
        cached_response = self.cache_manager.get_cached_response(cache_key)
        
        if cached_response:
            return cached_response
        
        # Prepare the prompt for keyword extraction
        prompt = self._create_keyword_extraction_prompt(resume_content)
        
        try:
            self.logger.info("Sending keyword extraction request to OpenAI")
            response = self.client.chat.completions.create(
                model=self.config.get_openai_model(),
                messages=[
                    {"role": "system", "content": "You are an expert resume analyzer and job search specialist."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config.get_openai_temperature(),
                max_tokens=self.config.get_openai_max_tokens()
            )
            
            # Parse the response
            content = response.choices[0].message.content.strip()
            self.logger.debug(f"OpenAI response received: {len(content)} characters")
            
            # Extract JSON from the response
            keywords_data = self._parse_json_response(content)
            
            if keywords_data:
                # Cache the successful response
                self.cache_manager.save_cached_response(cache_key, keywords_data)
                self.logger.info(f"Keywords extracted successfully: {len(keywords_data)} categories")
                return keywords_data
            else:
                raise ValueError("Failed to parse keyword extraction response")
                
        except Exception as e:
            self.logger.error(f"Error in keyword extraction: {str(e)}")
            raise
    
    def generate_search_terms(self, keywords_data: Dict, target_location: str = None, desired_position: str = None) -> Dict:
        """Generate search terms based on extracted keywords"""
        self.logger.debug("Starting search term generation")
        
        # Create cache key including location and position
        cache_input = json.dumps(keywords_data, sort_keys=True)
        cache_key = self.cache_manager.generate_cache_key(
            cache_input, 
            "generate_search_terms",
            target_location=target_location or "",
            desired_position=desired_position or ""
        )
        
        cached_response = self.cache_manager.get_cached_response(cache_key)
        if cached_response:
            return cached_response
        
        # Prepare the prompt for search term generation
        prompt = self._create_search_terms_prompt(keywords_data, target_location, desired_position)
        
        try:
            self.logger.info("Sending search term generation request to OpenAI")
            response = self.client.chat.completions.create(
                model=self.config.get_openai_model(),
                messages=[
                    {"role": "system", "content": "You are an expert job search strategist and recruiter."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config.get_openai_temperature(),
                max_tokens=self.config.get_openai_max_tokens()
            )
            
            # Parse the response
            content = response.choices[0].message.content.strip()
            self.logger.debug(f"OpenAI response received: {len(content)} characters")
            
            # Extract JSON from the response
            search_terms = self._parse_json_response(content)
            
            if search_terms:
                # Cache the successful response
                self.cache_manager.save_cached_response(cache_key, search_terms)
                self.logger.info("Search terms generated successfully")
                return search_terms
            else:
                raise ValueError("Failed to parse search terms response")
                
        except Exception as e:
            self.logger.error(f"Error in search term generation: {str(e)}")
            raise
    
    def analyze_and_rank_jobs(self, jobs_data: List[Dict], resume_keywords: Dict, max_jobs: int = None) -> List[Dict]:
        """Analyze and rank jobs based on resume keywords"""
        if not self.config.get_job_analysis_enabled():
            self.logger.info("Job analysis disabled in configuration")
            return jobs_data
        
        if max_jobs is None:
            max_jobs = self.config.get_max_jobs_to_analyze()
        
        # Limit the number of jobs to analyze
        jobs_to_analyze = jobs_data[:max_jobs] if max_jobs > 0 else jobs_data
        self.logger.info(f"Analyzing {len(jobs_to_analyze)} out of {len(jobs_data)} jobs")
        
        # Process jobs in batches
        batch_size = self.config.get('job_analysis.batch_size', 5)
        analyzed_jobs = []
        
        # Check if parallel processing is enabled and we have multiple batches
        total_batches = (len(jobs_to_analyze) + batch_size - 1) // batch_size
        if self.config.get('job_analysis.parallel_processing', True) and total_batches > 1:
            self.logger.info(f"Using parallel processing for {total_batches} batches")
            analyzed_jobs = self._process_batches_parallel(jobs_to_analyze, batch_size, resume_keywords)
        else:
            self.logger.info("Using sequential processing")
            analyzed_jobs = self._process_batches_sequential(jobs_to_analyze, batch_size, resume_keywords)
        
        # Add remaining jobs that weren't analyzed
        if max_jobs > 0 and len(jobs_data) > max_jobs:
            remaining_jobs = jobs_data[max_jobs:]
            analyzed_jobs.extend(self._create_default_analysis(remaining_jobs))
        
        # Sort by similarity score if enabled
        if self.config.get_similarity_ranking_enabled():
            analyzed_jobs.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
            self.logger.info("Jobs sorted by similarity score")
        
        return analyzed_jobs
    
    def clear_cache(self) -> None:
        """Clear the resume processing cache"""
        return self.cache_manager.clear_cache()
    
    def get_cache_info(self) -> Dict:
        """Get cache information"""
        return self.cache_manager.get_cache_info()
    
    def _create_keyword_extraction_prompt(self, resume_content: str) -> str:
        """Create the prompt for keyword extraction"""
        return f"""
        Analyze this resume and extract key information in the following JSON format:
        
        {{
            "technical_skills": ["skill1", "skill2", ...],
            "soft_skills": ["skill1", "skill2", ...],
            "programming_languages": ["language1", "language2", ...],
            "frameworks_libraries": ["framework1", "framework2", ...],
            "tools_technologies": ["tool1", "tool2", ...],
            "industries": ["industry1", "industry2", ...],
            "experience_level": "junior/mid/senior",
            "education": ["degree1", "degree2", ...],
            "certifications": ["cert1", "cert2", ...],
            "job_titles": ["title1", "title2", ...],
            "companies": ["company1", "company2", ...],
            "location_preferences": ["location1", "location2", ...],
            "years_experience": "number or range"
        }}
        
        Resume content:
        {resume_content}
        
        Return only the JSON object, no additional text.
        """
    
    def _create_search_terms_prompt(self, keywords_data: Dict, target_location: str = None, desired_position: str = None) -> str:
        """Create the prompt for search term generation"""
        location_text = f"Target location: {target_location}" if target_location else "Location: flexible/remote preferred"
        position_text = f"Desired position: {desired_position}" if desired_position else "Position: based on resume analysis"
        
        return f"""
        Based on the extracted resume keywords below, generate optimized job search terms in the following JSON format:
        
        {{
            "primary_search_terms": ["term1", "term2", "term3"],
            "secondary_search_terms": ["term1", "term2", "term3"],
            "location": "optimal_location_string",
            "google_search_string": "complete search string for Google",
            "job_titles_to_search": ["title1", "title2", "title3"],
            "keywords_for_filtering": ["keyword1", "keyword2", ...]
        }}
        
        {location_text}
        {position_text}
        
        Keywords from resume:
        {json.dumps(keywords_data, indent=2)}
        
        Generate search terms that will find the most relevant job opportunities. Return only the JSON object.
        """
    
    def _parse_json_response(self, content: str) -> Dict:
        """Parse JSON response from OpenAI, handling various formats"""
        try:
            # Try direct JSON parsing
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                if end != -1:
                    json_content = content[start:end].strip()
                    return json.loads(json_content)
            
            # Try to extract JSON from any code blocks
            if "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                if end != -1:
                    json_content = content[start:end].strip()
                    return json.loads(json_content)
            
            # Last resort: try to find JSON-like content
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                json_content = content[start:end]
                return json.loads(json_content)
            
            raise ValueError(f"Could not parse JSON from response: {content[:200]}...")
    
    def _process_batches_parallel(self, jobs_to_analyze: List[Dict], batch_size: int, resume_keywords: Dict) -> List[Dict]:
        """Process batches of jobs in parallel"""
        analyzed_jobs = []
        futures = []
        
        with ThreadPoolExecutor(max_workers=self.config.get('job_analysis.parallel_workers', 5)) as executor:
            for i in range(0, len(jobs_to_analyze), batch_size):
                batch = jobs_to_analyze[i:i + batch_size]
                futures.append(executor.submit(self._analyze_job_batch, batch, resume_keywords))
            
            for future in as_completed(futures):
                analyzed_jobs.extend(future.result())
        
        return analyzed_jobs
    
    def _process_batches_sequential(self, jobs_to_analyze: List[Dict], batch_size: int, resume_keywords: Dict) -> List[Dict]:
        """Process batches of jobs sequentially"""
        analyzed_jobs = []
        
        for i in range(0, len(jobs_to_analyze), batch_size):
            batch = jobs_to_analyze[i:i + batch_size]
            self.logger.debug(f"Processing job batch {i//batch_size + 1}: jobs {i+1}-{min(i+batch_size, len(jobs_to_analyze))}")
            
            try:
                analyzed_batch = self._analyze_job_batch(batch, resume_keywords)
                analyzed_jobs.extend(analyzed_batch)
            except Exception as e:
                self.logger.error(f"Error analyzing job batch {i//batch_size + 1}: {str(e)}")
                # Add unanalyzed jobs to maintain list completeness
                analyzed_jobs.extend(self._create_default_analysis(batch))
        
        return analyzed_jobs
    
    def _analyze_job_batch(self, jobs_batch: List[Dict], resume_keywords: Dict) -> List[Dict]:
        """Analyze a batch of jobs (simplified version)"""
        # For now, return jobs with default analysis
        # This would contain the full job analysis logic from the original file
        return self._create_default_analysis(jobs_batch)
    
    def _create_default_analysis(self, jobs_batch: List[Dict]) -> List[Dict]:
        """Create default analysis for jobs when AI analysis is not available"""
        for job in jobs_batch:
            job.update({
                'analyzed': False,
                'similarity_score': 0.0,
                'similarity_explanation': 'Analysis not performed',
                'salary_min_extracted': None,
                'salary_max_extracted': None,
                'salary_confidence': 0.0,
                'key_matches': [],
                'missing_requirements': []
            })
        return jobs_batch 