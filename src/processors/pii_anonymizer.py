import re
import logging
from config_loader import get_config


class PIIAnonymizer:
    """Handles PII (Personally Identifiable Information) removal and anonymization from resume content.
    
    This class provides comprehensive functionality to identify and anonymize various types of
    personally identifiable information commonly found in resumes and job-related documents.
    The anonymization process helps protect candidate privacy while preserving the document
    structure and professional content for analysis.
    
    Supported PII types include:
    - Email addresses
    - Phone numbers (various formats including US and international)
    - Physical addresses (street addresses and city/state/zip combinations)
    - Personal websites and portfolios (with option to preserve professional domains)
    - Candidate names (typically found at the top of resumes)
    
    The class uses configurable patterns and settings loaded from the application configuration
    to customize the anonymization behavior. All anonymization operations are logged for 
    audit and debugging purposes.
    
    Attributes:
        config (ConfigLoader): Configuration loader instance for accessing anonymization settings
        logger (logging.Logger): Logger instance for tracking anonymization operations and results
    
    Example:
        >>> anonymizer = PIIAnonymizer()
        >>> content = "John Doe\\nSoftware Engineer\\njohn.doe@email.com\\n(555) 123-4567"
        >>> anonymized = anonymizer.anonymize_resume(content)
        >>> print(anonymized)
        [NAME_REDACTED]
        Software Engineer
        [EMAIL_REDACTED]
        [PHONE_REDACTED]
    
    Note:
        The anonymization process is designed to be conservative, preferring to redact
        information that might be PII rather than risk exposing actual personal data.
        Configuration settings allow fine-tuning of the anonymization behavior.
    """
    
    def __init__(self):
        """Initialize the PIIAnonymizer.

        Loads the application configuration and sets up a class-specific logger.
        The config determines whether PII removal is active and how URLs are treated.

        Attributes:
            config: Loaded config object (via get_config()).
            logger: Logger named "{module}.{class}" for anonymization events.

        Note:
            Any errors from config_loader.get_config() will bubble up if loading fails.
        """
        self.config = get_config()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def anonymize_resume(self, resume_content: str) -> str:
        """Anonymize PII in the given resume text.

        Applies redaction in this fixed order:
        1. Emails
        2. Phone numbers
        3. Physical addresses
        4. Personal URLs
        5. Candidate name (first line)

        If 'resume_processing.pii_removal.enabled' is False, returns the input unchanged.
        Personal URL handling is governed by
        'resume_processing.pii_removal.preserve_professional_urls'.

        Args:
            resume_content: Original resume text to redact.

        Returns:
            The same text with found PII replaced by markers like [EMAIL_REDACTED].

        Note:
            - Idempotent: running it twice won’t double-redact.
            - Logs a summary of how many items of each type were removed.
            - Underlying regex or config errors will propagate as exceptions.
        """
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
        """Remove email addresses from content using regex pattern matching.
        
        Identifies and redacts email addresses using a comprehensive regex pattern
        that matches standard email formats including various TLD lengths and
        special characters commonly used in email addresses. The pattern is designed
        to be inclusive while avoiding false positives.
        
        Args:
            content (str): Text content to process for email address removal.
        
        Returns:
            tuple[str, int]: A tuple containing:
                - str: Content with email addresses replaced by [EMAIL_REDACTED]
                - int: Count of email addresses that were found and redacted
        
        Raises:
            re.error: If the regex pattern compilation fails (should not occur with
                the current pattern but included for completeness).
        
        Example:
            >>> anonymizer = PIIAnonymizer()
            >>> content = "Contact me at john.doe@company.com or jane_smith@example.org"
            >>> result, count = anonymizer._remove_emails(content)
            >>> print(f"Result: {result}")
            >>> print(f"Count: {count}")
            Result: Contact me at [EMAIL_REDACTED] or [EMAIL_REDACTED]
            Count: 2
        
        Note:
            - The regex pattern matches most standard email formats including subdomains
            - Special characters like dots, underscores, plus signs, and hyphens are supported
            - The pattern requires a valid TLD of at least 2 characters
            - Email addresses within larger URLs or complex formatting may not be detected
        """
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails_found = re.findall(email_pattern, content)
        if emails_found:
            content = re.sub(email_pattern, '[EMAIL_REDACTED]', content)
            self.logger.debug(f"Found and redacted {len(emails_found)} email addresses")
        return content, len(emails_found)
    
    def _remove_phone_numbers(self, content: str) -> tuple[str, int]:
        """Remove phone numbers from content using multiple regex patterns.
        
        Identifies and redacts phone numbers using several regex patterns to cover
        common US and international phone number formats. The method applies multiple
        patterns sequentially to ensure comprehensive coverage of different formatting
        styles commonly found in resumes.
        
        Supported formats include:
        - (555) 123-4567
        - 555-123-4567
        - 555.123.4567
        - 555 123 4567
        - +1 (555) 123-4567
        - +1-555-123-4567
        
        Args:
            content (str): Text content to process for phone number removal.
        
        Returns:
            tuple[str, int]: A tuple containing:
                - str: Content with phone numbers replaced by [PHONE_REDACTED]
                - int: Total count of phone numbers found and redacted across all patterns
        
        Raises:
            re.error: If any of the regex patterns fail to compile (should not occur
                with current patterns but included for completeness).
        
        Example:
            >>> anonymizer = PIIAnonymizer()
            >>> content = "Call me at (555) 123-4567 or 555.987.6543"
            >>> result, count = anonymizer._remove_phone_numbers(content)
            >>> print(f"Result: {result}")
            >>> print(f"Count: {count}")
            Result: Call me at [PHONE_REDACTED] or [PHONE_REDACTED]
            Count: 2
        
        Note:
            - The method uses word boundaries to avoid matching numbers that are part of other data
            - International formats with country codes (+1) are supported
            - The patterns are applied sequentially, so a phone number should only be matched once
            - Very non-standard formats may not be detected and would require pattern updates
        """
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
        """Remove physical addresses from content using multiple regex patterns.
        
        Identifies and redacts physical addresses using patterns that match common
        US address formats. The method uses two complementary patterns: one for
        street addresses with common street type suffixes, and another for
        city/state/ZIP combinations.
        
        Supported formats include:
        - Street addresses: "123 Main Street", "456 Oak Ave", "789 First Blvd"
        - City/State/ZIP: "Anytown, CA 90210", "New York, NY 10001-1234"
        
        Args:
            content (str): Text content to process for address removal.
        
        Returns:
            tuple[str, int]: A tuple containing:
                - str: Content with addresses replaced by [ADDRESS_REDACTED]
                - int: Total count of addresses found and redacted across all patterns
        
        Raises:
            re.error: If any of the regex patterns fail to compile.
        
        Example:
            >>> anonymizer = PIIAnonymizer()
            >>> content = "I live at 123 Main Street in Springfield, IL 62701"
            >>> result, count = anonymizer._remove_addresses(content)
            >>> print(f"Result: {result}")
            >>> print(f"Count: {count}")
            Result: I live at [ADDRESS_REDACTED] in [ADDRESS_REDACTED]
            Count: 2
        
        Note:
            - The street address pattern matches common US street suffixes (Street, Ave, Road, etc.)
            - The city/state/ZIP pattern requires the two-letter state abbreviation format
            - Both 5-digit and 9-digit (ZIP+4) postal codes are supported
            - International address formats are not currently supported
            - Partial matches (like standalone ZIP codes) may not be detected
        """
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
        """Remove personal URLs while optionally preserving professional ones.
        
        Identifies and processes URLs found in the content, with configurable behavior
        for preserving professional domains (like LinkedIn, GitHub) while redacting
        personal websites and portfolios. The method can operate in two modes based
        on configuration settings.
        
        When preserve_professional_urls is enabled (default), URLs are checked against
        a whitelist of professional domains loaded from configuration. Professional
        URLs are preserved while personal ones are redacted.
        
        When preserve_professional_urls is disabled, all URLs are redacted regardless
        of domain.
        
        Args:
            content (str): Text content to process for URL removal/filtering.
        
        Returns:
            tuple[str, int]: A tuple containing:
                - str: Content with personal URLs replaced by [WEBSITE_REDACTED]
                - int: Count of personal URLs that were redacted (professional URLs
                  preserved are not counted in this number)
        
        Raises:
            re.error: If the URL regex pattern fails to compile.
            AttributeError: If the configuration method get_professional_domains()
                is not available (should not occur with proper config setup).
        
        Example:
            >>> anonymizer = PIIAnonymizer()
            >>> content = "Visit my site at https://johnsmith.com or find me on https://linkedin.com/in/johnsmith"
            >>> result, count = anonymizer._remove_personal_urls(content)
            >>> print(f"Result: {result}")
            >>> print(f"Count: {count}")
            # Assuming LinkedIn is in professional domains:
            Result: Visit my site at [WEBSITE_REDACTED] or find me on https://linkedin.com/in/johnsmith
            Count: 1
        
        Note:
            - The URL pattern matches both HTTP and HTTPS protocols
            - Subdomains (www.) are handled correctly
            - Professional domains are configured in the application config file
            - Common professional domains typically include: linkedin.com, github.com, etc.
            - The domain matching is case-insensitive for better reliability
        """
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
        """Remove candidate name from the top of the resume using heuristic detection.
        
        Attempts to identify and redact the candidate's name from the first line of
        the resume using heuristic analysis. The method assumes that resumes typically
        start with the candidate's name as the header/title.
        
        The detection algorithm checks if the first line meets the following criteria:
        - Contains 2-3 words (typical for names)
        - Contains only alphabetic characters and spaces
        - Uses title case formatting (first letter of each word capitalized)
        - Is shorter than 50 characters (to avoid matching long titles or headers)
        
        This heuristic approach is designed to be conservative and may not catch all
        name variations, but it minimizes false positives on professional titles or
        other header content.
        
        Args:
            content (str): Resume text content to process for name removal.
        
        Returns:
            tuple[str, bool]: A tuple containing:
                - str: Content with the first line replaced by [NAME_REDACTED] if a
                  name was detected, otherwise unchanged content
                - bool: True if a name was detected and redacted, False otherwise
        
        Raises:
            None: This method handles all edge cases gracefully and does not raise exceptions.
        
        Example:
            >>> anonymizer = PIIAnonymizer()
            >>> content = '''John Smith
            ... Software Engineer
            ... 5 years experience'''
            >>> result, was_removed = anonymizer._remove_candidate_name(content)
            >>> print(f"Name removed: {was_removed}")
            >>> print(result.split('\\n')[0])
            Name removed: True
            [NAME_REDACTED]
        
        Note:
            - Only processes the first line of the document
            - The heuristic may miss names that don't follow typical formatting
            - Names with titles (Dr., Jr., etc.) may not be detected
            - Non-English names or unusual formatting may not match the criteria
            - The method errs on the side of caution to avoid redacting professional titles
        """
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