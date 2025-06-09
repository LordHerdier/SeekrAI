import os
from openai import OpenAI
from typing import List, Dict
import PyPDF2
from docx import Document
import json

class ResumeProcessor:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
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
        prompt = f"""
        Analyze the following resume and extract key information that would be useful for job searching:

        Resume Content:
        {resume_content}

        Please extract and categorize the following information in JSON format:
        1. Technical skills (programming languages, frameworks, tools, databases, cloud platforms)
        2. Job titles/roles the person has held or would be suitable for
        3. Years of experience (estimate if not explicitly stated)
        4. Industry/domain expertise
        5. Key achievements or specializations
        6. Location preferences (if mentioned)

        Format your response as a JSON object with the following structure:
        {{
            "technical_skills": ["skill1", "skill2", ...],
            "job_titles": ["title1", "title2", ...],
            "years_of_experience": "X years",
            "industries": ["industry1", "industry2", ...],
            "specializations": ["spec1", "spec2", ...],
            "location": "location if mentioned"
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert HR professional and career counselor. Extract key information from resumes accurately and format it as requested."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            # Try to parse JSON from the response
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract JSON from markdown code blocks
                import re
                json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))
                else:
                    # If still fails, return the raw content for debugging
                    return {"raw_response": content}
                    
        except Exception as e:
            print(f"Error extracting keywords: {e}")
            return {}
    
    def generate_search_terms(self, keywords_data: Dict, target_location: str = None) -> Dict:
        """Generate optimized search terms for job boards based on extracted keywords"""
        
        prompt = f"""
        Based on the following extracted resume information, generate optimized search terms for job board scraping:

        Resume Data:
        {json.dumps(keywords_data, indent=2)}

        Target Location: {target_location or "Not specified"}

        Please generate the following search parameters in JSON format:
        1. Primary search terms (2-3 most relevant job titles/roles)
        2. Secondary search terms (broader terms that might capture relevant jobs)
        3. Skills-based search terms (combinations of key technical skills)
        4. Suggested location (use target_location if provided, otherwise extract from resume)
        5. Experience level filter suggestions
        6. Google search optimization string (for sites that support it)

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
                    {"role": "system", "content": "You are an expert recruiter who understands how to optimize job search queries for maximum relevant results."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                import re
                json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))
                else:
                    return {"raw_response": content}
                    
        except Exception as e:
            print(f"Error generating search terms: {e}")
            return {}
    
    def process_resume(self, resume_file_path: str, target_location: str = None) -> Dict:
        """Complete pipeline: read resume, extract keywords, generate search terms"""
        
        print(f"Processing resume: {resume_file_path}")
        
        # Step 1: Read resume content
        resume_content = self.read_resume_file(resume_file_path)
        print(f"Resume content loaded ({len(resume_content)} characters)")
        
        # Step 2: Extract keywords
        print("Extracting keywords...")
        keywords_data = self.extract_keywords(resume_content)
        
        # Step 3: Generate search terms
        print("Generating search terms...")
        search_terms = self.generate_search_terms(keywords_data, target_location)
        
        return {
            "keywords": keywords_data,
            "search_terms": search_terms,
            "resume_length": len(resume_content)
        } 