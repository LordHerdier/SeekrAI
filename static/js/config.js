// SeekrAI Client-Side Configuration
// This file contains all configurable values for the frontend

window.SeekrAIConfig = {
    // File upload settings
    files: {
        maxSizeMB: 16,
        allowedTypes: [
            'text/plain',
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/msword'
        ],
        allowedExtensions: ['txt', 'pdf', 'docx', 'doc']
    },
    
    // UI behavior settings
    ui: {
        autoDismissAlertsMs: 5000,
        loadingButtonTimeoutMs: 10000,
        animationDurationMs: 300,
        buttonReEnableTimeoutMs: 10000,
        jobResultsPerPage: 20
    },
    
    // Form validation settings
    validation: {
        enableRealTimeValidation: true,
        showFieldErrors: true
    },
    
    // Animation and UX settings
    animations: {
        fadeInDuration: 500,
        slideInDuration: 300,
        enabled: true
    },
    
    // File size formatting
    fileSizes: {
        units: ['Bytes', 'KB', 'MB', 'GB'],
        base: 1024
    },
    
    // Default messages
    messages: {
        fileUpload: {
            invalidType: 'Please select a valid file type (PDF, Word, or Text)',
            tooLarge: 'File size must be less than {maxSize}MB',
            success: 'File selected successfully',
            copySuccess: 'Copied to clipboard!',
            copyFailure: 'Failed to copy to clipboard'
        },
        validation: {
            required: 'This field is required',
            invalidFormat: 'Invalid format'
        }
    },
    
    // API endpoints (relative to base URL)
    api: {
        upload: '/upload',
        searchJobs: '/search_jobs',
        download: '/download',
        files: '/files',
        cleanup: '/cleanup_files',
        cache: '/cache',
        clearCache: '/clear_cache'
    },
    
    // Development settings
    development: {
        enableDebugLogs: false,
        showPerformanceMetrics: false
    }
};

// Helper function to get nested config values with defaults
window.SeekrAIConfig.get = function(path, defaultValue = null) {
    const keys = path.split('.');
    let current = this;
    
    for (const key of keys) {
        if (current && typeof current === 'object' && key in current) {
            current = current[key];
        } else {
            return defaultValue;
        }
    }
    
    return current;
};

// Helper function to format file size using config
window.SeekrAIConfig.formatFileSize = function(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = this.get('fileSizes.base', 1024);
    const sizes = this.get('fileSizes.units', ['Bytes', 'KB', 'MB', 'GB']);
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

// Helper function to get max file size in bytes
window.SeekrAIConfig.getMaxFileSizeBytes = function() {
    return this.get('files.maxSizeMB', 16) * 1024 * 1024;
};

// Helper function to check if file type is allowed
window.SeekrAIConfig.isFileTypeAllowed = function(fileType) {
    const allowedTypes = this.get('files.allowedTypes', []);
    return allowedTypes.includes(fileType);
};

// Helper function to get allowed extensions as string
window.SeekrAIConfig.getAllowedExtensionsString = function() {
    const extensions = this.get('files.allowedExtensions', []);
    return extensions.map(ext => `.${ext}`).join(', ');
};

// Helper function to get message with placeholder replacement
window.SeekrAIConfig.getMessage = function(path, replacements = {}) {
    let message = this.get(`messages.${path}`, '');
    
    // Replace placeholders like {maxSize}
    for (const [key, value] of Object.entries(replacements)) {
        message = message.replace(new RegExp(`\\{${key}\\}`, 'g'), value);
    }
    
    return message;
}; 