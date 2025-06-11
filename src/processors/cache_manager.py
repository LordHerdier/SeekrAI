import os
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict
from config_loader import get_config


class CacheManager:
    """
    Manages caching for resume processing operations to improve performance and reduce API calls.
    
    This class provides functionality to cache responses from various operations like AI API calls,
    file processing results, and other computationally expensive operations. It implements
    cache expiration, corruption handling, and provides utilities for cache management.
    
    Attributes:
        config: Configuration object containing cache settings
        cache_dir (Path): Directory where cache files are stored
        logger (logging.Logger): Logger instance for this class
    
    Example:
        >>> cache_manager = CacheManager()
        >>> key = cache_manager.generate_cache_key("resume content", "analysis")
        >>> cached_result = cache_manager.get_cached_response(key)
        >>> if not cached_result:
        ...     # Perform expensive operation
        ...     result = expensive_operation()
        ...     cache_manager.save_cached_response(key, result)
    """
    
    def __init__(self, cache_dir: str = None):
        """
        Initialize the CacheManager with optional custom cache directory.
        
        Args:
            cache_dir (str, optional): Custom cache directory path. If None, uses
                the directory from configuration. Defaults to None.
        
        Note:
            If the specified cache directory cannot be created, falls back to
            the current working directory.
        """
        self.config = get_config()
        self.cache_dir = Path(cache_dir or self.config.get_cache_directory())
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._ensure_cache_directory()
    
    def _ensure_cache_directory(self):
        """
        Ensure the cache directory exists and is accessible.
        
        Creates the cache directory if it doesn't exist. If creation fails,
        falls back to using the current working directory and logs a warning.
        
        Raises:
            No exceptions are raised; errors are logged and handled gracefully.
        """
        try:
            self.cache_dir.mkdir(exist_ok=True)
            self.logger.debug(f"Cache directory ensured: {self.cache_dir}")
        except Exception as e:
            self.logger.warning(f"Could not create cache directory {self.cache_dir}: {e}")
            # Fall back to current directory if cache creation fails
            self.cache_dir = Path(".")
            self.logger.info(f"Falling back to current directory for cache: {self.cache_dir}")
    
    def generate_cache_key(self, content: str, operation: str, **kwargs) -> str:
        """
        Generate a unique cache key based on content, operation, and additional parameters.
        
        Creates a deterministic cache key by combining the operation type, content,
        and any additional parameters into a SHA-256 hash. This ensures that
        identical inputs always produce the same cache key.
        
        Args:
            content (str): The main content to be cached (e.g., resume text)
            operation (str): The type of operation being performed (e.g., "analysis", "parsing")
            **kwargs: Additional parameters that affect the operation result
        
        Returns:
            str: A 16-character hexadecimal cache key
        
        Example:
            >>> manager = CacheManager()
            >>> key = manager.generate_cache_key("resume text", "gpt_analysis", model="gpt-4")
            >>> print(key)  # e.g., "a1b2c3d4e5f67890"
        """
        # Create a string that includes content + operation + any additional parameters
        cache_input = f"{operation}:{content}"
        for key, value in sorted(kwargs.items()):
            cache_input += f":{key}={value}"
        
        # Create SHA-256 hash of the input
        cache_key = hashlib.sha256(cache_input.encode()).hexdigest()[:16]
        self.logger.debug(f"Generated cache key {cache_key} for operation: {operation}")
        return cache_key
    
    def get_cached_response(self, cache_key: str) -> Dict:
        """
        Retrieve a cached response if it exists and is still valid.
        
        Checks for a cached response with the given key, validates its age
        against the configured expiration time, and returns the cached data
        if valid. Expired or corrupted cache files are automatically removed.
        
        Args:
            cache_key (str): The cache key to look up
        
        Returns:
            Dict: The cached response data if found and valid, empty dict otherwise
        
        Note:
            Returns an empty dictionary if:
            - No cache file exists for the key
            - The cache file is expired
            - The cache file is corrupted or unreadable
        
        Example:
            >>> manager = CacheManager()
            >>> result = manager.get_cached_response("a1b2c3d4e5f67890")
            >>> if result:
            ...     print("Cache hit!")
            ... else:
            ...     print("Cache miss or expired")
        """
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if not cache_file.exists():
            self.logger.debug(f"No cache file found for key: {cache_key}")
            return {}
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            # Check if cache is expired
            cache_time = datetime.fromisoformat(cached_data.get('timestamp', ''))
            expiration_days = self.config.get_cache_expiration_days()
            if (datetime.now() - cache_time).days < expiration_days:
                self.logger.info(f"Using cached response for {cache_key[:8]}...")
                self.logger.debug(f"Cache hit - file: {cache_file}, age: {(datetime.now() - cache_time).days} days")
                return cached_data.get('response', {})
            else:
                # Cache expired, remove it
                cache_file.unlink()
                self.logger.info(f"Expired cache removed for {cache_key[:8]} (age: {(datetime.now() - cache_time).days} days)")
        except (json.JSONDecodeError, KeyError, ValueError, OSError) as e:
            # Invalid or corrupted cache file, remove it
            try:
                cache_file.unlink()
                self.logger.warning(f"Corrupted cache removed for {cache_key[:8]}: {e}")
            except OSError:
                self.logger.error(f"Failed to remove corrupted cache file: {cache_file}")
        
        return {}
    
    def save_cached_response(self, cache_key: str, response: Dict) -> None:
        """
        Save a response to the cache with the current timestamp.
        
        Stores the response data along with a timestamp in a JSON file
        named after the cache key. The timestamp is used for expiration
        checking when retrieving cached responses.
        
        Args:
            cache_key (str): The cache key to store the response under
            response (Dict): The response data to cache
        
        Raises:
            No exceptions are raised; errors are logged and handled gracefully.
        
        Note:
            If saving fails (e.g., due to disk space or permissions),
            the error is logged but the operation continues normally.
        
        Example:
            >>> manager = CacheManager()
            >>> response = {"analysis": "Professional resume", "score": 85}
            >>> manager.save_cached_response("a1b2c3d4e5f67890", response)
        """
        try:
            cache_file = self.cache_dir / f"{cache_key}.json"
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'response': response
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
            
            self.logger.info(f"Cached response for {cache_key[:8]}...")
            self.logger.debug(f"Cache saved to: {cache_file}")
        except Exception as e:
            self.logger.error(f"Could not save cache for {cache_key[:8]}: {e}")
    
    def clear_cache(self) -> Dict:
        """
        Clear all cached responses from the cache directory.
        
        Removes all JSON cache files from the cache directory and returns
        statistics about the clearing operation including number of files
        removed and disk space freed.
        
        Returns:
            Dict: Dictionary containing clearing statistics with keys:
                - files_removed (int): Number of cache files removed
                - space_freed_mb (float): Disk space freed in megabytes
        
        Raises:
            Exception: Re-raises any exception that occurs during the clearing process
                after logging the error.
        
        Example:
            >>> manager = CacheManager()
            >>> stats = manager.clear_cache()
            >>> print(f"Removed {stats['files_removed']} files, "
            ...       f"freed {stats['space_freed_mb']} MB")
        """
        self.logger.info("Clearing all cached responses")
        
        if not self.cache_dir.exists():
            self.logger.info("Cache directory doesn't exist - nothing to clear")
            return {'files_removed': 0, 'space_freed_mb': 0}
        
        files_removed = 0
        total_size_freed = 0
        
        try:
            for cache_file in self.cache_dir.glob('*.json'):
                try:
                    file_size = cache_file.stat().st_size
                    cache_file.unlink()
                    files_removed += 1
                    total_size_freed += file_size
                    self.logger.debug(f"Removed cache file: {cache_file.name}")
                except Exception as e:
                    self.logger.error(f"Could not remove cache file {cache_file}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error clearing cache: {e}")
            raise
        
        space_freed_mb = round(total_size_freed / (1024 * 1024), 2)
        self.logger.info(f"Cache cleared: {files_removed} files removed, {space_freed_mb} MB freed")
        
        return {
            'files_removed': files_removed,
            'space_freed_mb': space_freed_mb
        }
    
    def get_cache_info(self) -> Dict:
        """
        Get comprehensive information about cached files and cache directory status.
        
        Scans the cache directory and returns detailed information about all
        cache files including their sizes, modification times, and ages.
        Files are sorted by modification time (newest first).
        
        Returns:
            Dict: Dictionary containing cache information with keys:
                - cache_directory (str): Path to the cache directory
                - cache_files_count (int): Number of cache files
                - total_size_mb (float): Total size of all cache files in MB
                - files (List[Dict]): List of file information dictionaries, each containing:
                    - name (str): Filename
                    - size_bytes (int): File size in bytes
                    - modified (float): Modification timestamp
                    - age_days (float): Age of file in days
        
        Note:
            If the cache directory doesn't exist, returns information indicating
            an empty cache. Individual file errors are logged but don't prevent
            the function from returning information about other files.
        
        Example:
            >>> manager = CacheManager()
            >>> info = manager.get_cache_info()
            >>> print(f"Cache has {info['cache_files_count']} files "
            ...       f"using {info['total_size_mb']} MB")
            >>> for file_info in info['files'][:5]:  # Show first 5 files
            ...     print(f"  {file_info['name']}: {file_info['age_days']:.1f} days old")
        """
        self.logger.debug("Getting cache information")
        
        if not self.cache_dir.exists():
            return {
                'cache_directory': str(self.cache_dir),
                'cache_files_count': 0,
                'total_size_mb': 0,
                'files': []
            }
        
        cache_files = []
        total_size = 0
        
        try:
            for cache_file in self.cache_dir.glob('*.json'):
                try:
                    stat = cache_file.stat()
                    file_info = {
                        'name': cache_file.name,
                        'size_bytes': stat.st_size,
                        'modified': stat.st_mtime,
                        'age_days': (datetime.now().timestamp() - stat.st_mtime) / (24 * 60 * 60)
                    }
                    cache_files.append(file_info)
                    total_size += stat.st_size
                except Exception as e:
                    self.logger.warning(f"Could not get info for cache file {cache_file}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error getting cache info: {e}")
        
        # Sort by modification time (newest first)
        cache_files.sort(key=lambda x: x['modified'], reverse=True)
        
        cache_info = {
            'cache_directory': str(self.cache_dir),
            'cache_files_count': len(cache_files),
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'files': cache_files
        }
        
        self.logger.debug(f"Cache info: {len(cache_files)} files, {cache_info['total_size_mb']} MB")
        return cache_info 