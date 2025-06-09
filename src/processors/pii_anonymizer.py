import re
import logging
from config_loader import get_config


class PIIAnonymizer:
    """Handles PII removal and anonymization from resume content"""
    
    def __init__(self):
        self.config = get_config()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def anonymize_resume(self, resume_content: str) -> str:
        """Remove or anonymize PII from resume content"""
        self.logger.debug("Starting PII anonymization process")
        content = resume_content
        
        # Check if PII removal is enabled
        if not self.config.get('resume_processing.pii_removal.enabled', True):
            self.logger.info("PII removal disabled in configuration")
            return content
        
        # Track what we're removing for debugging
        pii_removed = []
        
        # 1. Email addresses
        content, emails_count = self._remove_emails(content)
        if emails_count > 0:
            pii_removed.append(f"{emails_count} email(s)")
        
        # 2. Phone numbers
        content, phones_count = self._remove_phone_numbers(content)
        if phones_count > 0:
            pii_removed.append(f"{phones_count} phone number(s)")
        
        # 3. Physical addresses
        content, addresses_count = self._remove_addresses(content)
        if addresses_count > 0:
            pii_removed.append(f"{addresses_count} address(es)")
        
        # 4. Personal websites/portfolios
        content, urls_count = self._remove_personal_urls(content)
        if urls_count > 0:
            pii_removed.append(f"{urls_count} personal website(s)")
        
        # 5. Names (try to identify the name at the top of resume)
        content, name_removed = self._remove_candidate_name(content)
        if name_removed:
            pii_removed.append("name")
        
        if pii_removed:
            self.logger.info(f"PII removed: {', '.join(pii_removed)}")
        else:
            self.logger.info("No PII detected in resume")
        
        self.logger.debug("PII anonymization process completed")
        return content
    
    def _remove_emails(self, content: str) -> tuple[str, int]:
        """Remove email addresses from content"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails_found = re.findall(email_pattern, content)
        if emails_found:
            content = re.sub(email_pattern, '[EMAIL_REDACTED]', content)
            self.logger.debug(f"Found and redacted {len(emails_found)} email addresses")
        return content, len(emails_found)
    
    def _remove_phone_numbers(self, content: str) -> tuple[str, int]:
        """Remove phone numbers from content"""
        phone_patterns = [
            r'\b\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})\b',  # (555) 123-4567, 555-123-4567, 555.123.4567
            r'\b(\d{3})[-.\s](\d{3})[-.\s](\d{4})\b',          # 555 123 4567
            r'\+1[-.\s]?\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})\b'  # +1 (555) 123-4567
        ]
        
        total_phones_found = 0
        for i, pattern in enumerate(phone_patterns):
            phones_found = re.findall(pattern, content)
            if phones_found:
                content = re.sub(pattern, '[PHONE_REDACTED]', content)
                total_phones_found += len(phones_found)
                self.logger.debug(f"Found and redacted {len(phones_found)} phone numbers with pattern {i+1}")
        
        return content, total_phones_found
    
    def _remove_addresses(self, content: str) -> tuple[str, int]:
        """Remove physical addresses from content"""
        address_patterns = [
            r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Place|Pl)\b.*',
            r'\b[A-Za-z\s]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?\b'  # City, ST 12345 or City, ST 12345-6789
        ]
        
        total_addresses_found = 0
        for i, pattern in enumerate(address_patterns):
            addresses_found = re.findall(pattern, content)
            if addresses_found:
                content = re.sub(pattern, '[ADDRESS_REDACTED]', content)
                total_addresses_found += len(addresses_found)
                self.logger.debug(f"Found and redacted {len(addresses_found)} addresses with pattern {i+1}")
        
        return content, total_addresses_found
    
    def _remove_personal_urls(self, content: str) -> tuple[str, int]:
        """Remove personal URLs while preserving professional ones"""
        url_pattern = r'https?://(?:www\.)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/[^\s]*)?'
        urls_found = re.findall(url_pattern, content)
        
        if not urls_found:
            return content, 0
        
        personal_urls_count = 0
        
        # Only redact personal domains if preserve_professional_urls is enabled
        if self.config.get('resume_processing.pii_removal.preserve_professional_urls', True):
            professional_domains = self.config.get_professional_domains()
            for url in urls_found:
                is_professional = any(domain in url.lower() for domain in professional_domains)
                if not is_professional:
                    content = content.replace(url, '[WEBSITE_REDACTED]')
                    personal_urls_count += 1
            
            if personal_urls_count > 0:
                self.logger.debug(f"Redacted {personal_urls_count} personal URLs, preserved {len(urls_found) - personal_urls_count} professional URLs")
        else:
            # Redact all URLs
            for url in urls_found:
                content = content.replace(url, '[WEBSITE_REDACTED]')
            personal_urls_count = len(urls_found)
            self.logger.debug(f"Redacted all {len(urls_found)} URLs")
        
        return content, personal_urls_count
    
    def _remove_candidate_name(self, content: str) -> tuple[str, bool]:
        """Remove candidate name from the top of the resume"""
        lines = content.split('\n')
        if not lines:
            return content, False
        
        first_line = lines[0].strip()
        # If first line looks like a name (2-3 words, title case, no numbers)
        if (len(first_line.split()) in [2, 3] and 
            first_line.replace(' ', '').isalpha() and 
            first_line.istitle() and
            len(first_line) < 50):
            lines[0] = '[NAME_REDACTED]'
            content = '\n'.join(lines)
            self.logger.debug(f"Redacted candidate name from first line: {first_line}")
            return content, True
        
        return content, False 