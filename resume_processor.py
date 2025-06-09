import os
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime
from openai import OpenAI
from typing import List, Dict
import PyPDF2
from docx import Document

class ResumeProcessor:
    def __init__(self, cache_dir: str = ".cache"):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
    def _generate_cache_key(self, content: str, operation: str, **kwargs) -> str:
        """Generate a unique cache key based on content and parameters"""
        # Create a string that includes content + operation + any additional parameters
        cache_input = f"{operation}:{content}"
        for key, value in sorted(kwargs.items()):
            cache_input += f":{key}={value}"
        
        # Create SHA-256 hash of the input
        return hashlib.sha256(cache_input.encode()).hexdigest()[:16]
    
    def _get_cached_response(self, cache_key: str) -> Dict:
        """Retrieve cached response if it exists and is valid"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                
                # Check if cache is less than 24 hours old (optional expiration)
                cache_time = datetime.fromisoformat(cached_data.get('timestamp', ''))
                if (datetime.now() - cache_time).days < 7:  # 7 day cache expiration
                    print(f"✅ Using cached response for {cache_key[:8]}...")
                    return cached_data.get('response', {})
            except (json.JSONDecodeError, KeyError, ValueError):
                # Invalid cache file, will regenerate
                pass
        
        return {}
    
    def _save_cached_response(self, cache_key: str, response: Dict) -> None:
        """Save response to cache"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'response': response
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2)
        
        print(f"💾 Cached response for {cache_key[:8]}...")
    
    def anonymize_resume(self, resume_content: str) -> str:
        """Remove or anonymize PII from resume content"""
        content = resume_content
        
        # Track what we're removing for debugging
        pii_removed = []
        
        # 1. Email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails_found = re.findall(email_pattern, content)
        if emails_found:
            content = re.sub(email_pattern, '[EMAIL_REDACTED]', content)
            pii_removed.append(f"{len(emails_found)} email(s)")
        
        # 2. Phone numbers (various formats)
        phone_patterns = [
            r'\b\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})\b',  # (555) 123-4567, 555-123-4567, 555.123.4567
            r'\b(\d{3})[-.\s](\d{3})[-.\s](\d{4})\b',          # 555 123 4567
            r'\+1[-.\s]?\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})\b'  # +1 (555) 123-4567
        ]
        
        for pattern in phone_patterns:
            phones_found = re.findall(pattern, content)
            if phones_found:
                content = re.sub(pattern, '[PHONE_REDACTED]', content)
                pii_removed.append(f"{len(phones_found)} phone number(s)")
        
        # 3. Physical addresses (basic patterns)
        # Remove lines that look like addresses (number + street + city/state/zip patterns)
        address_patterns = [
            r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Place|Pl)\b.*',
            r'\b[A-Za-z\s]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?\b'  # City, ST 12345 or City, ST 12345-6789
        ]
        
        for pattern in address_patterns:
            addresses_found = re.findall(pattern, content)
            if addresses_found:
                content = re.sub(pattern, '[ADDRESS_REDACTED]', content)
                pii_removed.append(f"{len(addresses_found)} address(es)")
        
        # 4. Personal websites/portfolios (optional - might be relevant for job applications)
        url_pattern = r'https?://(?:www\.)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/[^\s]*)?'
        urls_found = re.findall(url_pattern, content)
        if urls_found:
            # Only redact personal domains, keep professional ones like GitHub, LinkedIn
            professional_domains = ['github.com', 'linkedin.com', 'stackoverflow.com']
            for url in urls_found:
                is_professional = any(domain in url.lower() for domain in professional_domains)
                if not is_professional:
                    content = content.replace(url, '[WEBSITE_REDACTED]')
            pii_removed.append(f"{len([u for u in urls_found if not any(d in u.lower() for d in professional_domains)])} personal website(s)")
        
        # 5. Names (more complex - try to identify the name at the top of resume)
        lines = content.split('\n')
        if lines:
            first_line = lines[0].strip()
            # If first line looks like a name (2-3 words, title case, no numbers)
            if (len(first_line.split()) in [2, 3] and 
                first_line.replace(' ', '').isalpha() and 
                first_line.istitle() and
                len(first_line) < 50):
                lines[0] = '[NAME_REDACTED]'
                content = '\n'.join(lines)
                pii_removed.append("name")
        
        if pii_removed:
            print(f"🛡️  PII removed: {', '.join(pii_removed)}")
        else:
            print("🛡️  No PII detected in resume")
        
        return content
    
    def read_resume_file(self, file_path: str) -> str:
        """Read resume content from various file formats"""
        file_extension = file_path.lower().split('.')[-1]
        
        if file_extension == 'txt':
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        
        elif file_extension == 'pdf':
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text()
            return text
        
        elif file_extension in ['docx', 'doc']:
            doc = Document(file_path)
            text = []
            for paragraph in doc.paragraphs:
                text.append(paragraph.text)
            return '\n'.join(text)
        
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
    
    def extract_keywords(self, resume_content: str) -> Dict:
        """Extract relevant keywords and information from resume using OpenAI"""
        
        # Anonymize the resume content before sending to API
        anonymized_content = self.anonymize_resume(resume_content)
        
        # Check cache first
        cache_key = self._generate_cache_key(anonymized_content, "extract_keywords")
        cached_response = self._get_cached_response(cache_key)
        if cached_response:
            return cached_response
        
        prompt = f"""
        Analyze the following resume and extract key information that would be useful for job searching:

        Resume Content:
        {anonymized_content}

        Please extract and categorize the following information in JSON format:
        1. Technical skills (programming languages, frameworks, tools, databases, cloud platforms)
        2. Job titles/roles the person has held or would be suitable for
        3. Years of experience (estimate if not explicitly stated)
        4. Industry/domain expertise
        5. Key achievements or specializations
        6. Location preferences (if mentioned, otherwise use "Not specified")

        Format your response as a JSON object with the following structure:
        {{
            "technical_skills": ["skill1", "skill2", ...],
            "job_titles": ["title1", "title2", ...],
            "years_of_experience": "X years",
            "industries": ["industry1", "industry2", ...],
            "specializations": ["spec1", "spec2", ...],
            "location": "location if mentioned or Not specified"
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert HR professional and career counselor. Extract key information from resumes accurately and format it as requested. Note that some PII has been redacted for privacy."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            # Try to parse JSON from the response
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract JSON from markdown code blocks
                import re
                json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    # If still fails, return the raw content for debugging
                    result = {"raw_response": content}
            
            # Cache the result
            self._save_cached_response(cache_key, result)
            return result
                    
        except Exception as e:
            print(f"Error extracting keywords: {e}")
            return {}
    
    def generate_search_terms(self, keywords_data: Dict, target_location: str = None, desired_position: str = None) -> Dict:
        """Generate optimized search terms for job boards based on extracted keywords"""
        
        # Check cache first
        cache_key = self._generate_cache_key(
            json.dumps(keywords_data, sort_keys=True), 
            "generate_search_terms",
            location=target_location or "",
            position=desired_position or ""
        )
        cached_response = self._get_cached_response(cache_key)
        if cached_response:
            return cached_response
        
        desired_position_context = f"\nDesired Position: {desired_position}" if desired_position else ""
        
        prompt = f"""
        Based on the following extracted resume information, generate optimized search terms for job board scraping:

        Resume Data:
        {json.dumps(keywords_data, indent=2)}

        Target Location: {target_location or "Not specified"}{desired_position_context}

        Please generate the following search parameters in JSON format:
        1. Primary search terms (2-3 most relevant job titles/roles{' - prioritize the desired position if provided' if desired_position else ''})
        2. Secondary search terms (broader terms that might capture relevant jobs)
        3. Skills-based search terms (combinations of key technical skills)
        4. Suggested location (use target_location if provided, otherwise extract from resume)
        5. Experience level filter suggestions
        6. Google search optimization string (for sites that support it)

        {f'IMPORTANT: The user specifically wants to target "{desired_position}" roles. Please prioritize this position in your search terms while still considering the resume skills and experience.' if desired_position else ''}

        Format your response as a JSON object:
        {{
            "primary_search_terms": ["term1", "term2", "term3"],
            "secondary_search_terms": ["term1", "term2", "term3"],
            "skills_based_terms": ["skill combo 1", "skill combo 2"],
            "location": "suggested location",
            "experience_level": "junior/mid/senior",
            "google_search_string": "optimized search string for Google job search"
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert recruiter who understands how to optimize job search queries for maximum relevant results. When a desired position is specified, prioritize it while leveraging the candidate's existing skills."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                import re
                json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    result = {"raw_response": content}
            
            # Cache the result
            self._save_cached_response(cache_key, result)
            return result
                    
        except Exception as e:
            print(f"Error generating search terms: {e}")
            return {}
    
    def clear_cache(self) -> None:
        """Clear all cached responses"""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir()
            print("🗑️  Cache cleared")
    
    def get_cache_info(self) -> Dict:
        """Get information about cached responses"""
        if not self.cache_dir.exists():
            return {"cache_files": 0, "total_size": 0}
        
        cache_files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in cache_files)
        
        return {
            "cache_files": len(cache_files),
            "total_size": total_size,
            "cache_dir": str(self.cache_dir)
        }
    
    def process_resume(self, resume_file_path: str, target_location: str = None, desired_position: str = None) -> Dict:
        """Complete pipeline: read resume, extract keywords, generate search terms"""
        
        print(f"Processing resume: {resume_file_path}")
        if desired_position:
            print(f"Targeting position: {desired_position}")
        
        # Show cache info
        cache_info = self.get_cache_info()
        if cache_info["cache_files"] > 0:
            print(f"💾 Cache: {cache_info['cache_files']} files, {cache_info['total_size']} bytes")
        
        # Step 1: Read resume content
        resume_content = self.read_resume_file(resume_file_path)
        print(f"Resume content loaded ({len(resume_content)} characters)")
        
        # Step 2: Extract keywords
        print("Extracting keywords...")
        keywords_data = self.extract_keywords(resume_content)
        
        # Step 3: Generate search terms
        print("Generating search terms...")
        search_terms = self.generate_search_terms(keywords_data, target_location, desired_position)
        
        return {
            "keywords": keywords_data,
            "search_terms": search_terms,
            "resume_length": len(resume_content),
            "desired_position": desired_position
        } 