// SeekrAI JavaScript functionality

// Global variables
let currentUploadedFile = null;
let jobSearchInProgress = false;

// Get configuration
const Config = window.SeekrAIConfig;

// Document ready functions
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    // Initialize tooltips if Bootstrap tooltips are available
    if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
    
    // Initialize file upload validation
    initializeFileUpload();
    
    // Initialize form enhancements
    initializeFormEnhancements();
    
    // Initialize job search functionality
    initializeJobSearch();
    
    // Initialize UI enhancements
    initializeUIEnhancements();
}

function initializeFileUpload() {
    const fileInput = document.getElementById('resume');
    if (!fileInput) return;
    
    // File validation
    fileInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (!file) return;
        
        // Validate file type
        if (!Config.isFileTypeAllowed(file.type)) {
            showAlert(Config.getMessage('fileUpload.invalidType'), 'danger');
            e.target.value = '';
            return;
        }
        
        // Validate file size
        const maxSize = Config.getMaxFileSizeBytes();
        if (file.size > maxSize) {
            const maxSizeMB = Config.get('files.maxSizeMB', 16);
            showAlert(Config.getMessage('fileUpload.tooLarge', { maxSize: maxSizeMB }), 'danger');
            e.target.value = '';
            return;
        }
        
        // Show file info
        showFileInfo(file);
        currentUploadedFile = file;
    });
    
    // Drag and drop functionality
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadForm.addEventListener(eventName, preventDefaults, false);
        });
        
        ['dragenter', 'dragover'].forEach(eventName => {
            uploadForm.addEventListener(eventName, highlight, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            uploadForm.addEventListener(eventName, unhighlight, false);
        });
        
        uploadForm.addEventListener('drop', handleDrop, false);
    }
}

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

function highlight(e) {
    e.currentTarget.classList.add('drag-over');
}

function unhighlight(e) {
    e.currentTarget.classList.remove('drag-over');
}

function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    
    if (files.length > 0) {
        const fileInput = document.getElementById('resume');
        fileInput.files = files;
        fileInput.dispatchEvent(new Event('change'));
    }
}

function showFileInfo(file) {
    const fileSize = Config.formatFileSize(file.size);
    
    const infoHtml = `
        <div class="alert alert-success mt-2" id="fileInfo">
            <i class="fas fa-check-circle me-2"></i>
            <strong>${file.name}</strong> (${fileSize}) ${Config.getMessage('fileUpload.success')}
        </div>
    `;
    
    // Remove existing file info
    const existingInfo = document.getElementById('fileInfo');
    if (existingInfo) {
        existingInfo.remove();
    }
    
    // Add new file info
    const fileInput = document.getElementById('resume');
    fileInput.parentNode.insertAdjacentHTML('afterend', infoHtml);
}

function initializeFormEnhancements() {
    // Auto-resize textareas
    const textareas = document.querySelectorAll('textarea');
    textareas.forEach(textarea => {
        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });
    });
    
    // Form validation enhancement
    if (Config.get('validation.enableRealTimeValidation', true)) {
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            form.addEventListener('submit', function(e) {
                if (!validateForm(this)) {
                    e.preventDefault();
                    e.stopPropagation();
                }
                this.classList.add('was-validated');
            });
        });
    }
}

function validateForm(form) {
    let isValid = true;
    
    // Check required fields
    const requiredFields = form.querySelectorAll('[required]');
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            isValid = false;
            field.classList.add('is-invalid');
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

function initializeJobSearch() {
    // Job search form handling is done in results.html template
    // This function can be extended for additional job search features
}

function initializeUIEnhancements() {
    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Auto-dismiss alerts after configured time
    const autoDismissTime = Config.get('ui.autoDismissAlertsMs', 5000);
    setTimeout(() => {
        const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(alert => {
            if (alert.querySelector('.btn-close')) {
                alert.classList.add('fade');
                setTimeout(() => alert.remove(), 500);
            }
        });
    }, autoDismissTime);
    
    // Loading button states with configurable timeout
    const loadingButtons = document.querySelectorAll('[data-loading-text]');
    const buttonTimeout = Config.get('ui.loadingButtonTimeoutMs', 10000);
    
    loadingButtons.forEach(button => {
        button.addEventListener('click', function() {
            const loadingText = this.getAttribute('data-loading-text');
            const originalText = this.innerHTML;
            
            this.innerHTML = loadingText;
            this.disabled = true;
            
            // Re-enable after configured timeout as fallback
            setTimeout(() => {
                this.innerHTML = originalText;
                this.disabled = false;
            }, buttonTimeout);
        });
    });
}

// Utility functions
function showAlert(message, type = 'info', permanent = false) {
    const alertHtml = `
        <div class="alert alert-${type} alert-dismissible fade show ${permanent ? 'alert-permanent' : ''}" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    // Insert at the top of the main container
    const container = document.querySelector('main.container');
    if (container) {
        container.insertAdjacentHTML('afterbegin', alertHtml);
    }
}

function setLoadingState(element, loading = true) {
    if (loading) {
        element.disabled = true;
        element.dataset.originalText = element.innerHTML;
        element.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Loading...';
    } else {
        element.disabled = false;
        element.innerHTML = element.dataset.originalText || element.innerHTML;
    }
}

function formatFileSize(bytes) {
    return Config.formatFileSize(bytes);
}

function copyToClipboard(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
            showAlert(Config.getMessage('fileUpload.copySuccess'), 'success');
        }).catch(err => {
            console.error('Failed to copy: ', err);
            showAlert(Config.getMessage('fileUpload.copyFailure'), 'danger');
        });
    } else {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        
        try {
            document.execCommand('copy');
            showAlert(Config.getMessage('fileUpload.copySuccess'), 'success');
        } catch (err) {
            console.error('Failed to copy: ', err);
            showAlert(Config.getMessage('fileUpload.copyFailure'), 'danger');
        }
        
        document.body.removeChild(textArea);
    }
}

// Export functions for use in templates
window.SeekrAI = {
    showAlert,
    setLoadingState,
    formatFileSize,
    copyToClipboard,
    validateForm,
    Config
};

// Add CSS for drag and drop styling with configurable colors
const style = document.createElement('style');
style.textContent = `
    .drag-over {
        border: 2px dashed #0d6efd !important;
        background-color: rgba(13, 110, 253, 0.05) !important;
    }
    
    .fade-in {
        animation: fadeIn ${Config.get('animations.fadeInDuration', 500)}ms ease-in;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    
    .slide-in {
        animation: slideIn ${Config.get('animations.slideInDuration', 300)}ms ease-out;
    }
    
    @keyframes slideIn {
        from {
            transform: translateY(-20px);
            opacity: 0;
        }
        to {
            transform: translateY(0);
            opacity: 1;
        }
    }
`;
document.head.appendChild(style); 