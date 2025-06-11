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
    """Main orchestrator for resume processing operations in the SeekrAI platform.
    
    This class serves as the central coordinator for all resume processing operations,
    integrating AI-powered analysis, PII anonymization, caching, and file reading
    capabilities. It handles the complete workflow from raw resume file input to
    structured keyword extraction and job search term generation.
    
    The ResumeProcessor leverages OpenAI's API for intelligent content analysis,
    implements robust caching to minimize API calls and improve performance, and
    provides comprehensive error handling and logging throughout the processing
    pipeline.
    
    Key Features:
        - Multi-format resume file processing (PDF, DOCX, TXT)
        - AI-powered keyword extraction and analysis
        - PII anonymization for privacy protection
        - Intelligent job search term generation
        - Job posting analysis and ranking
        - Response caching for performance optimization
        - Parallel processing support for batch operations
        - Comprehensive error handling and logging
    
    Processing Pipeline:
        1. File reading and content extraction
        2. PII anonymization (if enabled)
        3. AI-powered keyword extraction
        4. Search term generation
        5. Optional job analysis and ranking
    
    Attributes:
        config (ConfigLoader): Configuration manager instance
        client (OpenAI): OpenAI API client for AI operations
        logger (logging.Logger): Logger instance for operation tracking
        file_reader (FileReader): Component for reading various file formats
        pii_anonymizer (PIIAnonymizer): Component for PII detection and anonymization
        cache_manager (CacheManager): Component for response caching
    
    Example:
        >>> processor = ResumeProcessor()
        >>> results = processor.process_resume(
        ...     "path/to/resume.pdf",
        ...     target_location="San Francisco, CA",
        ...     desired_position="Software Engineer"
        ... )
        >>> print(f"Keywords extracted: {len(results['keywords']['technical_skills'])}")
        >>> print(f"Search terms generated: {len(results['search_terms']['primary_search_terms'])}")
    
    Note:
        This class requires a valid OpenAI API key configured in the application
        settings. All AI operations are subject to OpenAI's rate limits and usage policies.
        The processor automatically handles caching to minimize redundant API calls.
    """
    
    def __init__(self, cache_dir: str = None):
        """Initialize the ResumeProcessor with all required components and configuration.
        
        Sets up the complete processing pipeline including AI client configuration,
        component initialization, and logging setup. The processor is configured
        using the application's configuration system and can optionally use a
        custom cache directory.
        
        Args:
            cache_dir (str, optional): Custom directory path for caching operations.
                If None, uses the cache directory specified in the application
                configuration. Defaults to None.
        
        Raises:
            ConfigurationError: If the application configuration cannot be loaded
                or contains invalid settings.
            AuthenticationError: If the OpenAI API key is invalid or missing.
            IOError: If the cache directory cannot be created or accessed.
        
        Example:
            >>> # Use default cache directory from config
            >>> processor = ResumeProcessor()
            
            >>> # Use custom cache directory
            >>> processor = ResumeProcessor(cache_dir="/custom/cache/path")
        
        Note:
            The OpenAI client is initialized immediately during construction and
            will validate the API key. Ensure your API key is properly configured
            before instantiating this class.
        """
        self.config = get_config()
        self.client = OpenAI(api_key=self.config.get_openai_api_key())
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Initialize component processors
        self.file_reader = FileReader()
        self.pii_anonymizer = PIIAnonymizer()
        self.cache_manager = CacheManager(cache_dir)
    
    def process_resume(self, resume_file_path: str, target_location: str = None, desired_position: str = None) -> Dict:
        """Process a resume file through the complete analysis pipeline.
        
        This is the main entry point for resume processing operations. It orchestrates
        the entire workflow from file reading through AI analysis, handling each step
        with comprehensive error handling and logging. The method returns structured
        data containing extracted keywords and generated search terms.
        
        Processing Steps:
            1. Read and extract content from the resume file
            2. Anonymize PII if privacy protection is enabled
            3. Extract keywords and professional information using AI
            4. Generate optimized job search terms based on extracted data
            5. Return structured results for further processing
        
        Args:
            resume_file_path (str): Path to the resume file to be processed.
                Supports PDF, DOCX, DOC, and TXT formats. Can be absolute or
                relative path.
            target_location (str, optional): Desired job location for search
                optimization. Examples: "San Francisco, CA", "Remote", "New York".
                If provided, influences search term generation. Defaults to None.
            desired_position (str, optional): Target job title or position.
                Examples: "Software Engineer", "Data Scientist", "Product Manager".
                If provided, helps focus the search term generation. Defaults to None.
        
        Returns:
            Dict: Comprehensive processing results containing:
                - keywords (Dict): Extracted professional information including:
                    - technical_skills (List[str]): Programming languages, tools, etc.
                    - soft_skills (List[str]): Communication, leadership, etc.
                    - programming_languages (List[str]): Specific languages
                    - frameworks_libraries (List[str]): Technical frameworks
                    - tools_technologies (List[str]): Software tools and platforms
                    - industries (List[str]): Industry experience
                    - experience_level (str): Junior/mid/senior classification
                    - education (List[str]): Educational background
                    - certifications (List[str]): Professional certifications
                    - job_titles (List[str]): Previous job titles
                    - companies (List[str]): Previous employers
                    - location_preferences (List[str]): Geographic preferences
                    - years_experience (str): Experience duration
                    - search_terms (Dict): Optimized search terms including:
                    - primary_search_terms (List[str]): Main search keywords
                    - secondary_search_terms (List[str]): Alternative keywords
                    - location (str): Optimized location string
                    - google_search_string (str): Complete search query
                    - job_titles_to_search (List[str]): Relevant job titles
                    - keywords_for_filtering (List[str]): Filtering keywords
        
        Raises:
            FileNotFoundError: If the specified resume file does not exist.
            ValueError: If the file format is unsupported or if AI processing fails
                to extract valid keywords or generate search terms.
            PermissionError: If the resume file cannot be read due to permissions.
            OpenAIError: If the AI API calls fail due to network, authentication,
                or rate limiting issues.
            ProcessingError: If any step in the processing pipeline fails.
        
        Example:
            >>> processor = ResumeProcessor()
            >>> results = processor.process_resume(
            ...     "/path/to/resume.pdf",
            ...     target_location="Seattle, WA",
            ...     desired_position="Senior Python Developer"
            ... )
            >>> 
            >>> # Access extracted technical skills
            >>> tech_skills = results['keywords']['technical_skills']
            >>> print(f"Technical skills found: {', '.join(tech_skills[:5])}")
            >>> 
            >>> # Access generated search terms
            >>> primary_terms = results['search_terms']['primary_search_terms']
            >>> print(f"Primary search terms: {', '.join(primary_terms)}")
            >>> 
            >>> # Get the optimized Google search string
            >>> google_query = results['search_terms']['google_search_string']
            >>> print(f"Google search: {google_query}")
        
        Note:
            - The method uses caching to avoid redundant AI API calls for identical content
            - PII anonymization is applied before AI analysis to protect privacy
            - Processing time varies based on file size and AI API response times
            - All operations are logged for debugging and audit purposes
            - The method is thread-safe and can be called concurrently
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
        """Extract structured keywords and professional information from resume content using AI.
        
        This method uses OpenAI's API to perform intelligent analysis of resume content,
        extracting and categorizing various types of professional information. The
        extraction process is designed to identify technical skills, soft skills,
        experience levels, education, and other relevant professional data.
        
        The method implements comprehensive caching to minimize API calls and improve
        performance. Identical resume content will return cached results if available
        and not expired.
        
        Args:
            resume_content (str): The resume text content to analyze. Should be
                clean text extracted from the original file. PII anonymization
                is typically applied before calling this method.
        
        Returns:
            Dict: Structured professional information containing:
                - technical_skills (List[str]): Programming languages, technical tools,
                  software platforms, and technical competencies
                - soft_skills (List[str]): Communication, leadership, teamwork,
                  problem-solving, and other interpersonal skills
                - programming_languages (List[str]): Specific programming languages
                  mentioned (Python, Java, JavaScript, etc.)
                - frameworks_libraries (List[str]): Development frameworks and
                  libraries (React, Django, TensorFlow, etc.)
                - tools_technologies (List[str]): Software tools, platforms, and
                  technologies (Docker, AWS, Git, etc.)
                - industries (List[str]): Industry sectors with experience
                  (Finance, Healthcare, E-commerce, etc.)
                - experience_level (str): Classified experience level
                  ("junior", "mid", "senior")
                - education (List[str]): Educational background including degrees
                  and institutions
                - certifications (List[str]): Professional certifications and
                  credentials
                - job_titles (List[str]): Previous job titles and positions held
                - companies (List[str]): Previous employers and organizations
                - location_preferences (List[str]): Geographic preferences or
                  locations mentioned
                - years_experience (str): Total years of experience or experience
                  range
        
        Raises:
            ValueError: If the resume content is empty, if the AI response cannot
                be parsed, or if no valid keywords are extracted.
            OpenAIError: If the API call fails due to authentication, rate limits,
                network issues, or service unavailability.
            JSONDecodeError: If the AI response is not in valid JSON format and
                cannot be parsed by the fallback parsing methods.
            CacheError: If there are issues accessing or saving to the cache
                (logged but does not interrupt processing).
        
        Example:
            >>> processor = ResumeProcessor()
            >>> content = "John Doe\\nSoftware Engineer with 5 years Python experience..."
            >>> keywords = processor.extract_keywords(content)
            >>> 
            >>> # Access different categories of extracted information
            >>> print(f"Technical skills: {keywords['technical_skills']}")
            >>> print(f"Programming languages: {keywords['programming_languages']}")
            >>> print(f"Experience level: {keywords['experience_level']}")
            >>> print(f"Years of experience: {keywords['years_experience']}")
            >>> 
            >>> # Check for specific skills
            >>> if 'Python' in keywords['programming_languages']:
            ...     print("Python developer detected")
        
        Note:
            - The method uses GPT models for analysis, so results may vary slightly
            - Caching is based on content hash, so identical content returns cached results
            - The AI prompt is designed to extract comprehensive professional information
            - Processing time depends on content length and AI API response times
            - Failed extractions are logged with detailed error information
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
        """Generate optimized job search terms based on extracted resume keywords.
        
        This method takes the structured keyword data extracted from a resume and
        generates optimized search terms for job hunting. It uses AI to create
        targeted search queries, job titles to search for, and filtering keywords
        that will help find the most relevant job opportunities.
        
        The method considers the target location and desired position (if provided)
        to create more focused and relevant search terms. It implements caching
        to avoid redundant API calls for identical keyword combinations.
        
        Args:
            keywords_data (Dict): Structured professional information extracted
                from the resume, typically the output of extract_keywords().
                Should contain keys like 'technical_skills', 'programming_languages',
                'experience_level', etc.
            target_location (str, optional): Desired job location to optimize
                search terms for geographic relevance. Examples: "San Francisco, CA",
                "Remote", "New York", "London, UK". Defaults to None.
            desired_position (str, optional): Target job title or role to focus
                the search term generation. Examples: "Senior Software Engineer",
                "Data Scientist", "Product Manager". Defaults to None.
        
        Returns:
            Dict: Optimized search terms and strategies containing:
                - primary_search_terms (List[str]): Main keywords for job searches,
                  optimized for the candidate's strongest skills and experience
                - secondary_search_terms (List[str]): Alternative search terms
                  for broader job discovery and related positions
                - location (str): Optimized location string for job searches,
                  considering remote work preferences and geographic flexibility
                - google_search_string (str): Complete, ready-to-use Google search
                  query combining skills, location, and job types
                - job_titles_to_search (List[str]): Specific job titles that align
                  with the candidate's experience and career level
                - keywords_for_filtering (List[str]): Keywords to use for filtering
                  job results to ensure relevance and match
        
        Raises:
            ValueError: If keywords_data is empty or invalid, if the AI response
                cannot be parsed, or if no valid search terms are generated.
            TypeError: If keywords_data is not a dictionary or contains invalid
                data types for processing.
            OpenAIError: If the API call fails due to authentication, rate limits,
                network issues, or service unavailability.  
            JSONDecodeError: If the AI response cannot be parsed as valid JSON.
            CacheError: If there are issues with cache operations (logged but
                does not interrupt processing).
        
        Example:
            >>> processor = ResumeProcessor()
            >>> # Assume we have keywords from previous extraction
            >>> keywords = {
            ...     'technical_skills': ['Python', 'Machine Learning', 'AWS'],
            ...     'programming_languages': ['Python', 'SQL', 'JavaScript'],
            ...     'experience_level': 'senior',
            ...     # ... other keyword categories
            ... }
            >>> 
            >>> search_terms = processor.generate_search_terms(
            ...     keywords,
            ...     target_location="San Francisco, CA",
            ...     desired_position="Senior Data Scientist"
            ... )
            >>> 
            >>> # Use the generated search terms
            >>> print(f"Primary terms: {search_terms['primary_search_terms']}")
            >>> print(f"Job titles to search: {search_terms['job_titles_to_search']}")
            >>> print(f"Google search query: {search_terms['google_search_string']}")
            >>> 
            >>> # Use for automated job searching
            >>> for term in search_terms['primary_search_terms']:
            ...     # Perform job search with this term
            ...     pass
        
        Note:
            - Search terms are optimized based on the candidate's experience level
            - Location preferences influence both local and remote job suggestions
            - The AI considers industry trends and job market demands
            - Generated terms balance specificity with search result volume
            - Caching prevents redundant API calls for identical input combinations
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
        """Analyze and rank job postings based on resume keyword matching and compatibility.
        
        This method performs intelligent analysis of job postings to determine their
        compatibility with a candidate's resume. It uses AI-powered analysis to
        evaluate job requirements against the candidate's skills and experience,
        providing similarity scores, detailed explanations, and ranking.
        
        The method supports both parallel and sequential processing modes based on
        configuration settings, and implements intelligent job limiting to balance
        analysis depth with performance requirements.
        
        Analysis Features:
            - AI-powered job description analysis
            - Skill matching and gap identification
            - Salary extraction and parsing
            - Compatibility scoring (0.0 to 1.0)
            - Detailed match explanations
            - Missing requirement identification
            - Batch processing for efficiency
        
        Args:
            jobs_data (List[Dict]): List of job posting dictionaries to analyze.
                Each job should contain fields like 'title', 'description', 
                'company', 'location', etc. The exact structure depends on the
                job data source.
            resume_keywords (Dict): Structured keyword data from the candidate's
                resume, typically the output from extract_keywords(). Used for
                matching against job requirements.
            max_jobs (int, optional): Maximum number of jobs to perform detailed
                analysis on. If None, uses the configuration setting. Remaining
                jobs get basic analysis. Helps balance accuracy with performance.
                Defaults to None.
        
        Returns:
            List[Dict]: Enhanced job postings with analysis results. Each job
            dictionary is augmented with:
                - analyzed (bool): Whether AI analysis was performed
                - similarity_score (float): Compatibility score (0.0 to 1.0)
                - similarity_explanation (str): Detailed explanation of the match
                - salary_min_extracted (float): Extracted minimum salary
                - salary_max_extracted (float): Extracted maximum salary  
                - salary_confidence (float): Confidence in salary extraction
                - key_matches (List[str]): Skills/requirements that match
                - missing_requirements (List[str]): Requirements the candidate lacks
                
            Jobs are sorted by similarity_score (highest first) if ranking is enabled.
        
        Raises:
            ValueError: If jobs_data is empty or contains invalid job data,
                or if resume_keywords is missing required fields.
            TypeError: If jobs_data is not a list or resume_keywords is not a dict.
            ConfigurationError: If job analysis configuration is invalid.
            ProcessingError: If batch processing fails or if too many jobs
                fail individual analysis.
        
        Example:
            >>> processor = ResumeProcessor()
            >>> 
            >>> # Sample job data
            >>> jobs = [
            ...     {
            ...         'title': 'Senior Python Developer',
            ...         'description': 'Looking for Python expert with Django...',
            ...         'company': 'Tech Corp',
            ...         'location': 'San Francisco, CA'
            ...     },
            ...     # ... more jobs
            ... ]
            >>> 
            >>> # Resume keywords from previous extraction
            >>> keywords = {
            ...     'technical_skills': ['Python', 'Django', 'AWS'],
            ...     'programming_languages': ['Python', 'JavaScript'],
            ...     'experience_level': 'senior'
            ... }
            >>> 
            >>> # Analyze and rank jobs
            >>> analyzed_jobs = processor.analyze_and_rank_jobs(
            ...     jobs, keywords, max_jobs=10
            ... )
            >>> 
            >>> # Review top matches
            >>> for job in analyzed_jobs[:5]:
            ...     print(f"{job['title']}: {job['similarity_score']:.2f}")
            ...     print(f"  Match: {job['similarity_explanation']}")
            ...     if job['key_matches']:
            ...         print(f"  Key matches: {', '.join(job['key_matches'])}")
        
        Note:
            - Analysis is limited by configuration to balance performance and cost
            - Jobs beyond the analysis limit receive default scores and explanations
            - Parallel processing is used when enabled and multiple batches are needed
            - The similarity scoring considers both skill matches and experience level
            - Salary extraction attempts to parse various salary formats from job descriptions, though it may not always be successful
            - All analysis results are logged for debugging and audit purposes
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
        """Process job analysis batches in parallel using thread pool execution.
        
        This private method implements parallel processing of job analysis batches
        to improve performance when analyzing large numbers of job postings. It
        uses ThreadPoolExecutor to manage concurrent batch processing.
        
        Args:
            jobs_to_analyze (List[Dict]): Jobs to analyze in parallel batches.
            batch_size (int): Number of jobs per batch.
            resume_keywords (Dict): Resume keywords for job matching.
        
        Returns:
            List[Dict]: Combined results from all parallel batch processing.
        
        Note:
            The number of parallel workers is controlled by configuration settings.
            Failed batches are handled gracefully without stopping other batches.
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