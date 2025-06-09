import os
import logging
import PyPDF2
from docx import Document
from pathlib import Path


class FileReader:
    """Handles reading content from various file formats"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def read_resume_file(self, file_path: str) -> str:
        """Read resume content from various file formats"""
        self.logger.info(f"Reading resume file: {file_path}")
        file_extension = file_path.lower().split('.')[-1]
        
        try:
            if file_extension == 'txt':
                self.logger.debug("Processing TXT file")
                return self._read_txt_file(file_path)
            elif file_extension == 'pdf':
                self.logger.debug("Processing PDF file")
                return self._read_pdf_file(file_path)
            elif file_extension in ['doc', 'docx']:
                self.logger.debug(f"Processing {file_extension.upper()} file")
                return self._read_docx_file(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")
                
        except Exception as e:
            self.logger.error(f"Error reading file {file_path}: {str(e)}")
            raise
    
    def _read_txt_file(self, file_path: str) -> str:
        """Read content from TXT file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                self.logger.debug(f"Successfully read TXT file, {len(content)} characters")
                return content
        except UnicodeDecodeError:
            # Try with different encoding if UTF-8 fails
            with open(file_path, 'r', encoding='latin-1') as file:
                content = file.read()
                self.logger.debug(f"Successfully read TXT file with latin-1 encoding, {len(content)} characters")
                return content
    
    def _read_pdf_file(self, file_path: str) -> str:
        """Read content from PDF file"""
        content = []
        
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            num_pages = len(pdf_reader.pages)
            self.logger.debug(f"PDF has {num_pages} pages")
            
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text.strip():  # Only add non-empty pages
                        content.append(page_text)
                        self.logger.debug(f"Extracted text from page {page_num + 1}: {len(page_text)} characters")
                    else:
                        self.logger.warning(f"Page {page_num + 1} appears to be empty or image-only")
                except Exception as e:
                    self.logger.warning(f"Could not extract text from page {page_num + 1}: {e}")
        
        full_content = '\n'.join(content)
        self.logger.debug(f"Successfully read PDF file, total {len(full_content)} characters")
        
        if not full_content.strip():
            raise ValueError("PDF appears to contain no extractable text. It may be image-based or corrupted.")
        
        return full_content
    
    def _read_docx_file(self, file_path: str) -> str:
        """Read content from DOCX file"""
        try:
            doc = Document(file_path)
            content = []
            
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():  # Only add non-empty paragraphs
                    content.append(paragraph.text)
            
            full_content = '\n'.join(content)
            self.logger.debug(f"Successfully read DOCX file, {len(doc.paragraphs)} paragraphs, {len(full_content)} characters")
            
            if not full_content.strip():
                raise ValueError("DOCX file appears to contain no text content.")
            
            return full_content
            
        except Exception as e:
            self.logger.error(f"Error reading DOCX file: {e}")
            raise ValueError(f"Could not read DOCX file: {str(e)}") 