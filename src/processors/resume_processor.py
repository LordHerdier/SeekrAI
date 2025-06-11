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
    """Central orchestrator for processing resumes into structured keywords and search terms.

    Integrates file reading, PII anonymization, AI-powered keyword extraction, caching,
    and search-term generation. Designed for batch or single-file workflows.
    """
    
    def __init__(self, cache_dir: str = None):
        """Initialize all components: config, OpenAI client, file reader, PII anonymizer, and cache manager.

        Args:
            cache_dir (str, optional): Path for cache storage. Defaults to the app’s configured cache directory.

        Raises:
            ConfigurationError: If loading configuration fails.
            AuthenticationError: If the OpenAI API key is invalid or missing.
            OSError: If the cache directory can’t be created or accessed.
        """
        self.config = get_config()
        self.client = OpenAI(api_key=self.config.get_openai_api_key())
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Initialize component processors
        self.file_reader = FileReader()
        self.pii_anonymizer = PIIAnonymizer()
        self.cache_manager = CacheManager(cache_dir)
    
    def process_resume(self, resume_file_path: str, target_location: str = None, desired_position: str = None) -> Dict:
        """Run a resume through the full pipeline: read → anonymize → extract keywords → generate search terms.

        Args:
            resume_file_path (str): Path to a PDF, DOCX or TXT resume.
            target_location (str, optional): If set, tailors search-term generation (e.g. "Remote", "NYC"). Defaults to None.
            desired_position (str, optional): If set, focuses search terms on that title. Defaults to None.

        Returns:
            dict: {
                "keywords": { … },       # structured AI-extracted info
                "search_terms": { … }    # optimized job-search keywords
            }

        Raises:
            FileNotFoundError: If resume_file_path doesn’t exist.
            ValueError: On failed keyword extraction or search-term generation.
            PermissionError: If file isn’t readable.
            OpenAIError: On API failures.
            ProcessingError: For any other pipeline error.
        """
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
        """Use OpenAI (with caching) to pull out skills, experience level, education, etc., from resume text.

        Args:
            resume_content (str): Plain-text resume (PII already anonymized).

        Returns:
            dict: {
                "technical_skills": List[str],
                "soft_skills": List[str],
                "programming_languages": List[str],
                "frameworks_libraries": List[str],
                "tools_technologies": List[str],
                "industries": List[str],
                "experience_level": str,
                "education": List[str],
                "certifications": List[str],
                "job_titles": List[str],
                "companies": List[str],
                "location_preferences": List[str],
                "years_experience": str
            }

        Raises:
            ValueError: If input is empty or parsing fails.
            OpenAIError: On API errors (auth, rate limit, network).
            json.JSONDecodeError: If AI response isn’t valid JSON.
            CacheError: If cache read/write fails (logged but non-fatal).
        """
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
        """
        Produce job-search queries from resume keywords, with caching.

        Examines the structured `keywords_data`, builds a prompt, and calls OpenAI
        to return a dict of search terms.  Uses an internal cache key derived from
        `keywords_data`, `target_location`, and `desired_position` to avoid repeated
        API calls for the same inputs.

        Args:
            keywords_data (Dict): Output of `extract_keywords()`, e.g. with keys
                like 'technical_skills', 'experience_level', etc.
            target_location (str, optional): Geographic filter (e.g. "Remote",
                "NYC, NY"). Defaults to None.
            desired_position (str, optional): Job title to bias results (e.g.
                "Senior Data Scientist"). Defaults to None.

        Returns:
            Dict: {
                'primary_search_terms': List[str],
                'secondary_search_terms': List[str],
                'location': str,
                'google_search_string': str,
                'job_titles_to_search': List[str],
                'keywords_for_filtering': List[str],
            }

        Raises:
            ValueError: If the AI response can’t be parsed into valid search terms.
            TypeError: If `keywords_data` isn’t a dict.
            Any exceptions raised by the OpenAI client, JSON parsing, or cache
            operations (e.g., `OpenAIError`, `JSONDecodeError`, `CacheError`).
        """
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
        """
        Score and sort job posts by how well they match resume keywords.

        If job-analysis is disabled in config, returns `jobs_data` unmodified.
        Otherwise, takes up to `max_jobs` (or config’s default), runs AI-powered
        analysis in batches (parallel or sequential), and appends any leftover
        postings with a default “not analyzed” explanation.  Optionally
        sorts by similarity score if enabled.

        Args:
            jobs_data (List[Dict]): Each dict should have keys like
                'title', 'description', 'company', 'location', etc.
            resume_keywords (Dict): Keywords from the candidate’s resume.
            max_jobs (int, optional): How many postings to analyze in depth.
                If None, uses `config.get_max_jobs_to_analyze()`. Defaults to None.

        Returns:
            List[Dict]: Each job dict is augmented with:
                - 'analyzed' (bool)
                - 'similarity_score' (float 0.0–1.0)
                - 'similarity_explanation' (str)
                - 'salary_min_extracted' (float)
                - 'salary_max_extracted' (float)
                - 'salary_confidence' (float)
                - 'key_matches' (List[str])
                - 'missing_requirements' (List[str])
            Jobs beyond the analysis limit get `analyzed=False` and a default
            explanation, and are included last before sorting.

        Raises:
            TypeError: If `jobs_data` is not a list or `resume_keywords` is not a dict.
            Any exceptions from batch processing or underlying AI calls.
        """
        if not self.config.get_job_analysis_enabled():
            self.logger.info("Job analysis disabled in configuration")
            return jobs_data
        
        # **FIX: Better coordination of job limits**
        # If max_jobs is specified, use it; otherwise use config or analyze all
        if max_jobs is None:
            analysis_limit = self.config.get_max_jobs_to_analyze()
            if analysis_limit <= 0:  # If config says 0 or negative, analyze all
                analysis_limit = len(jobs_data)
        else:
            analysis_limit = max_jobs
        
        # **FIX: Don't analyze more jobs than we actually have**
        analysis_limit = min(analysis_limit, len(jobs_data))
        
        # Limit the number of jobs to analyze
        jobs_to_analyze = jobs_data[:analysis_limit]
        remaining_jobs = jobs_data[analysis_limit:]
        
        self.logger.info(f"Analyzing {len(jobs_to_analyze)} jobs, {len(remaining_jobs)} will get default analysis")
        
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
        
        # Add remaining jobs that weren't analyzed with default analysis
        if remaining_jobs:
            self.logger.info(f"Adding {len(remaining_jobs)} unanalyzed jobs with default analysis")
            default_analyzed_jobs = self._create_default_analysis(remaining_jobs)
            for job in default_analyzed_jobs:
                job['similarity_explanation'] = 'Not analyzed - beyond analysis limit'
            analyzed_jobs.extend(default_analyzed_jobs)
        
        # Sort by similarity score if enabled
        if self.config.get_similarity_ranking_enabled():
            analyzed_jobs.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
            self.logger.info("Jobs sorted by similarity score")
        
        # FIXME Ensure we return exactly the expected number of jobs**
        if len(analyzed_jobs) != len(jobs_data):
            self.logger.warning(f"Job count mismatch: input {len(jobs_data)}, output {len(analyzed_jobs)}")
        
        return analyzed_jobs
    
    def clear_cache(self) -> None:
        """Clear all cached responses from the resume processing cache.
        
        This method provides a convenient interface to clear all cached AI responses
        and processing results. It delegates to the underlying cache manager and
        can be useful for debugging, testing, or when processing requirements change.
        
        The cache clearing operation removes all cached keyword extractions, search
        term generations, and job analyses. This will force fresh AI API calls for
        all subsequent processing operations.
        
        Returns:
            None: The method has no return value.
        
        Raises:
            CacheError: If there are issues accessing or clearing the cache directory.
            PermissionError: If the cache files cannot be deleted due to permissions.
            OSError: If there are file system errors during cache clearing.
        
        Example:
            >>> processor = ResumeProcessor()
            >>> 
            >>> # Clear all cached responses
            >>> processor.clear_cache()
            >>> 
            >>> # Subsequent processing will make fresh API calls
            >>> results = processor.process_resume("resume.pdf")
        
        Note:
            - This operation cannot be undone
            - Clearing cache will increase API usage and processing time
            - Use sparingly and primarily for debugging or testing purposes
            - The cache directory structure is preserved, only cached files are removed
        """
        return self.cache_manager.clear_cache()
    
    def get_cache_info(self) -> Dict:
        """Get comprehensive information about the current cache state and usage.
        
        This method provides detailed statistics about cached responses, including
        file counts, storage usage, and individual file information. It's useful
        for monitoring cache performance, debugging caching issues, and understanding
        storage usage.
        
        Returns:
            Dict: Comprehensive cache information containing:
                - cache_directory (str): Path to the cache directory
                - cache_files_count (int): Total number of cached response files
                - total_size_mb (float): Total storage used by cache files in MB
                - files (List[Dict]): Detailed information about each cache file:
                    - name (str): Cache file name
                    - size_bytes (int): File size in bytes
                    - modified (float): Last modification timestamp
                    - age_days (float): Age of the cache file in days
        
        Raises:
            CacheError: If there are issues accessing the cache directory or files.
            OSError: If there are file system errors while gathering cache information.
        
        Example:
            >>> processor = ResumeProcessor()
            >>> cache_info = processor.get_cache_info()
            >>> 
            >>> print(f"Cache directory: {cache_info['cache_directory']}")
            >>> print(f"Total files: {cache_info['cache_files_count']}")
            >>> print(f"Storage used: {cache_info['total_size_mb']} MB")
            >>> 
            >>> # Show information about recent cache files
            >>> for file_info in cache_info['files'][:5]:
            ...     print(f"File: {file_info['name']}")
            ...     print(f"  Size: {file_info['size_bytes']} bytes")
            ...     print(f"  Age: {file_info['age_days']:.1f} days")
        
        Note:
            - File information is sorted by modification time (newest first)
            - Storage size calculations include all cache metadata
            - Age calculations are based on file modification time
            - Individual file errors are logged but don't prevent overall info gathering
        """
        return self.cache_manager.get_cache_info()
    
    def _create_keyword_extraction_prompt(self, resume_content: str) -> str:
        """Create the AI prompt for extracting structured keywords from resume content.
        
        This private method constructs a detailed prompt that instructs the AI model
        to analyze resume content and extract professional information in a specific
        JSON format. The prompt is designed to ensure consistent, comprehensive
        extraction of various professional categories.
        
        Args:
            resume_content (str): The resume text content to be analyzed.
        
        Returns:
            str: Formatted prompt for the AI model including instructions and content.
        
        Note:
            This is an internal method used by extract_keywords(). The prompt
            structure is optimized for current AI models and may be updated
            based on model capabilities and extraction requirements.
        """
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
        """Create the AI prompt for generating optimized job search terms.
        
        This private method constructs a detailed prompt that instructs the AI model
        to generate targeted job search terms based on extracted resume keywords
        and optional location/position preferences.
        
        Args:
            keywords_data (Dict): Extracted professional information from resume.
            target_location (str, optional): Desired job location.
            desired_position (str, optional): Target job title or position.
        
        Returns:
            str: Formatted prompt for search term generation including all context.
        
        Note:
            This is an internal method used by generate_search_terms(). The prompt
            incorporates job market intelligence and search optimization strategies.
        """
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
        """Parse JSON response from AI model with robust error handling.
        
        This private method handles various JSON response formats that AI models
        might return, including responses wrapped in markdown code blocks or
        containing additional text. It implements multiple parsing strategies
        to extract valid JSON data.
        
        Args:
            content (str): Raw response content from the AI model.
        
        Returns:
            Dict: Parsed JSON data as a Python dictionary.
        
        Raises:
            ValueError: If no valid JSON can be extracted from the response.
            JSONDecodeError: If the extracted content is not valid JSON.
        
        Note:
            This is an internal utility method that makes AI response parsing
            more robust by handling various response formats and edge cases.
        """
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
        """Process job analysis batches in parallel using a thread pool.

        This private method splits `jobs_to_analyze` into chunks of `batch_size`
        and submits each chunk to a ThreadPoolExecutor for concurrent processing
        via `_analyze_job_batch`.

        Args:
            jobs_to_analyze (List[Dict]): List of job postings to analyze.
            batch_size (int): Number of jobs in each batch.
            resume_keywords (Dict): Keywords from the resume for matching.

        Returns:
            List[Dict]: All analyzed jobs combined, in no guaranteed order.

        Note:
            - Max workers is driven by `self.config['job_analysis.parallel_workers']`.
            - Any exception raised during a batch’s analysis will bubble up
            when retrieving its result, potentially aborting the whole run.
        """
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
        """Process job analysis batches sequentially for controlled processing.
        
        This private method implements sequential processing of job analysis batches,
        which is more conservative on resources and easier to debug than parallel
        processing. It processes one batch at a time with comprehensive error handling.
        
        Args:
            jobs_to_analyze (List[Dict]): Jobs to analyze in sequential batches.
            batch_size (int): Number of jobs per batch.
            resume_keywords (Dict): Resume keywords for job matching.
        
        Returns:
            List[Dict]: Combined results from all sequential batch processing.
        
        Note:
            Failed batches are replaced with default analysis to maintain
            consistency in the returned job list structure.
        """
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
        """Analyze a batch of jobs for compatibility with resume keywords.
        
        This private method would contain the core AI-powered job analysis logic,
        comparing job requirements against resume keywords and generating compatibility
        scores and detailed explanations.
        
        Args:
            jobs_batch (List[Dict]): Batch of job postings to analyze.
            resume_keywords (Dict): Resume keywords for compatibility analysis.
        
        Returns:
            List[Dict]: Jobs with added analysis fields.
        
        Note:
            This is currently a simplified implementation that returns default
            analysis. The full implementation would include AI-powered analysis
            of job descriptions, requirement matching, and salary extraction.
        """
        # For now, return jobs with default analysis
        # This would contain the full job analysis logic from the original file
        return self._create_default_analysis(jobs_batch)
    
    def _create_default_analysis(self, jobs_batch: List[Dict]) -> List[Dict]:
        """Create default analysis fields for jobs when AI analysis is not performed.
        
        This private method adds standard analysis fields to job postings with
        default values when detailed AI analysis is not performed (e.g., due to
        limits, errors, or configuration settings).
        
        Args:
            jobs_batch (List[Dict]): Batch of jobs to add default analysis to.
        
        Returns:
            List[Dict]: Jobs with added default analysis fields.
        
        Note:
            Default analysis provides consistent data structure while indicating
            that detailed analysis was not performed. All jobs maintain the
            same field structure regardless of analysis depth.
        """
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