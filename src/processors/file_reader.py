import os
import logging
import PyPDF2
from docx import Document
from pathlib import Path


class FileReader:
    """Read and extract text from various document formats.

    Supports plain-text (.txt), PDF (.pdf), and Microsoft Word (.docx) files.
    Uses robust error handling and logging to trace file operations and errors.
    Note: Legacy .doc files are not natively supported by python-docx and may fail.

    Attributes:
        logger (logging.Logger): Logger for recording operations and errors.

    Example:
        reader = FileReader()
        content = reader.read_resume_file("resume.pdf")
    """
    
    def __init__(self):
        """Initialize the FileReader with a configured logger.
        
        Sets up logging for the FileReader instance to track file processing
        operations, errors, and debug information.
        """
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def read_resume_file(self, file_path: str) -> str:
        """Extract text content based on file extension.

        Detects file type from the extension of `file_path` and delegates
        to the appropriate handler: `_read_txt_file`, `_read_pdf_file`,
        or `_read_docx_file`.

        Args:
            file_path (str): Path to the file to read.

        Returns:
            str: Extracted text.  
                - For .txt files, may be an empty string if there's no content.  
                - For .pdf and .docx, raises `ValueError` if no extractable text.

        Raises:
            FileNotFoundError: If `file_path` does not exist.
            PermissionError: If the file isn't accessible.
            ValueError: If the extension is unsupported, or if a .pdf/.docx
                contains no extractable text.
            Exception: Other I/O or parsing errors, as logged and re-raised.
        """
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
        """Read content from a plain text file with encoding fallback.
        
        Attempts to read the text file using UTF-8 encoding first, and falls back
        to Latin-1 encoding if UTF-8 fails. This approach handles most common
        encoding scenarios for text files.
        
        Args:
            file_path (str): Path to the text file to be read.
        
        Returns:
            str: The complete text content of the file as a string.
        
        Raises:
            FileNotFoundError: If the specified file does not exist.
            PermissionError: If the file cannot be read due to permissions.
            OSError: For other file system related errors.
        
        Example:
            >>> reader = FileReader()
            >>> content = reader._read_txt_file("resume.txt")
            >>> print(f"Read {len(content)} characters")
            Read 1500 characters
        
        Note:
            This method first attempts UTF-8 encoding (most common for modern text files)
            and automatically falls back to Latin-1 if a UnicodeDecodeError occurs.
            The encoding used is logged for debugging purposes.
        """
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
        """Read and extract text content from a PDF file.
        
        Uses PyPDF2 library to extract text from all pages of a PDF document.
        Handles multi-page documents and filters out empty pages. Provides detailed
        logging for each page processed and handles extraction errors gracefully.
        
        Args:
            file_path (str): Path to the PDF file to be read.
        
        Returns:
            str: Concatenated text content from all pages, with pages separated
                by newline characters. Only non-empty pages are included.
        
        Raises:
            ValueError: If the PDF contains no extractable text (may be image-based
                or corrupted), or if the file is not a valid PDF.
            FileNotFoundError: If the specified PDF file does not exist.
            PermissionError: If the PDF file cannot be opened due to permissions.
            PyPDF2.errors.PdfReadError: If the PDF file is corrupted or invalid.
        
        Example:
            >>> reader = FileReader()
            >>> content = reader._read_pdf_file("document.pdf")
            >>> pages = content.split('\n')
            >>> print(f"Extracted content from {len(pages)} pages")
            Extracted content from 3 pages
        
        Note:
            - Empty or image-only pages are skipped and logged as warnings
            - Text extraction failures on individual pages are logged but don't
              stop processing of remaining pages
            - The method validates that at least some text was extracted before returning
        """
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
        """Extract text from a .docx file using python-docx.

        Iterates through all non-empty paragraphs and joins them
        with newline separators.

        Args:
            file_path (str): Path to the .docx file.

        Returns:
            str: Text content composed of all non-empty paragraphs.

        Raises:
            FileNotFoundError: If the file is missing.
            PermissionError: If the file isn’t accessible.
            ValueError: If the document has no text, or if reading fails
                due to format issues or corruption.
        
        Example:
            >>> reader = FileReader()
            >>> content = reader._read_docx_file("document.docx")
            >>> print(f"Read {len(content)} characters")
            Read 1500 characters
        """
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