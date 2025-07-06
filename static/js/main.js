// Main JavaScript for Loss Prevention System

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeFileUpload();
    initializeVideoPlayers();
    initializeNotifications();
    initializeSearchFilters();
    initializeTooltips();
});

// File upload functionality
function initializeFileUpload() {
    const fileInput = document.getElementById('file');
    const uploadArea = document.querySelector('.file-upload-area');
    
    if (fileInput && uploadArea) {
        // Drag and drop functionality
        uploadArea.addEventListener('dragover', function(e) {
            e.preventDefault();
            uploadArea.classList.add('drag-over');
        });
        
        uploadArea.addEventListener('dragleave', function(e) {
            e.preventDefault();
            uploadArea.classList.remove('drag-over');
        });
        
        uploadArea.addEventListener('drop', function(e) {
            e.preventDefault();
            uploadArea.classList.remove('drag-over');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                fileInput.files = files;
                validateFile(files[0]);
            }
        });
        
        // File input change
        fileInput.addEventListener('change', function(e) {
            if (e.target.files.length > 0) {
                validateFile(e.target.files[0]);
            }
        });
    }
}

// File validation
function validateFile(file) {
    const allowedTypes = ['text/csv', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'];
    const maxSize = 16 * 1024 * 1024; // 16MB
    
    if (!allowedTypes.includes(file.type)) {
        showNotification('Please select a CSV or Excel file.', 'error');
        return false;
    }
    
    if (file.size > maxSize) {
        showNotification('File size exceeds 16MB limit.', 'error');
        return false;
    }
    
    showNotification('File selected: ' + file.name, 'success');
    return true;
}

// Video player initialization
function initializeVideoPlayers() {
    const videoElements = document.querySelectorAll('.video-js');
    
    videoElements.forEach(function(videoElement) {
        if (window.videojs) {
            const player = videojs(videoElement, {
                responsive: true,
                fluid: true,
                playbackRates: [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2],
                controls: true,
                preload: 'metadata'
            });
            
            // Add keyboard shortcuts
            player.ready(function() {
                // Space bar to play/pause
                player.on('keydown', function(e) {
                    if (e.which === 32) { // Space bar
                        e.preventDefault();
                        if (player.paused()) {
                            player.play();
                        } else {
                            player.pause();
                        }
                    }
                });
                
                // Arrow keys for seeking
                player.on('keydown', function(e) {
                    if (e.which === 37) { // Left arrow
                        e.preventDefault();
                        player.currentTime(Math.max(0, player.currentTime() - 5));
                    } else if (e.which === 39) { // Right arrow
                        e.preventDefault();
                        player.currentTime(Math.min(player.duration(), player.currentTime() + 5));
                    }
                });
            });
        }
    });
}

// Notification system
function initializeNotifications() {
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
        if (alert.classList.contains('alert-success')) {
            setTimeout(function() {
                alert.classList.add('fade');
                setTimeout(function() {
                    alert.remove();
                }, 300);
            }, 5000);
        }
    });
}

// Show notification
function showNotification(message, type = 'info') {
    const alertClass = type === 'error' ? 'alert-danger' : `alert-${type}`;
    const alertHtml = `
        <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    const container = document.querySelector('.container');
    if (container) {
        container.insertAdjacentHTML('afterbegin', alertHtml);
        
        // Auto-dismiss after 5 seconds
        setTimeout(function() {
            const alert = container.querySelector('.alert');
            if (alert) {
                alert.remove();
            }
        }, 5000);
    }
}

// Search and filter functionality
function initializeSearchFilters() {
    const filterForm = document.querySelector('form[method="GET"]');
    const filterInputs = document.querySelectorAll('select[name="status"], select[name="type"]');
    
    if (filterForm && filterInputs.length > 0) {
        filterInputs.forEach(function(input) {
            input.addEventListener('change', function() {
                // Auto-submit form when filter changes
                filterForm.submit();
            });
        });
    }
}

// Initialize tooltips
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Transaction review functionality
function updateTransactionStatus(transactionId, status) {
    const formData = new FormData();
    formData.append('status', status);
    
    fetch(`/update_review/${transactionId}`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Transaction status updated successfully.', 'success');
            location.reload();
        } else {
            showNotification('Error updating transaction status.', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Error updating transaction status.', 'error');
    });
}

// Export functionality
function exportData(format = 'csv') {
    const url = `/export_${format}`;
    window.location.href = url;
}

// Utility functions
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}

function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

function formatTime(dateString) {
    return new Date(dateString).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

// Loading state management
function showLoadingState(element) {
    element.disabled = true;
    element.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Loading...';
}

function hideLoadingState(element, originalText) {
    element.disabled = false;
    element.innerHTML = originalText;
}

// Form validation
function validateForm(form) {
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;
    
    requiredFields.forEach(function(field) {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

// Search functionality
function searchTransactions(query) {
    const tableRows = document.querySelectorAll('tbody tr');
    
    tableRows.forEach(function(row) {
        const text = row.textContent.toLowerCase();
        if (text.includes(query.toLowerCase())) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl+U for upload
    if (e.ctrlKey && e.key === 'u') {
        e.preventDefault();
        const uploadLink = document.querySelector('a[href*="upload"]');
        if (uploadLink) {
            uploadLink.click();
        }
    }
    
    // Ctrl+R for reports
    if (e.ctrlKey && e.key === 'r') {
        e.preventDefault();
        const reportsLink = document.querySelector('a[href*="reports"]');
        if (reportsLink) {
            reportsLink.click();
        }
    }
    
    // Escape key to close modals
    if (e.key === 'Escape') {
        const modals = document.querySelectorAll('.modal.show');
        modals.forEach(function(modal) {
            const bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) {
                bsModal.hide();
            }
        });
    }
});

// Auto-refresh functionality for pending transactions
function autoRefreshPending() {
    const pendingBadges = document.querySelectorAll('.badge');
    const hasPending = Array.from(pendingBadges).some(badge => badge.textContent.includes('Pending'));
    
    if (hasPending) {
        // Refresh every 30 seconds if there are pending transactions
        setTimeout(function() {
            location.reload();
        }, 30000);
    }
}

// Initialize auto-refresh
autoRefreshPending();

// Mobile-specific enhancements
if (window.innerWidth <= 768) {
    // Add mobile-specific functionality
    document.body.classList.add('mobile-view');
    
    // Swipe navigation for mobile
    let startX = 0;
    let startY = 0;
    
    document.addEventListener('touchstart', function(e) {
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
    });
    
    document.addEventListener('touchmove', function(e) {
        if (!startX || !startY) {
            return;
        }
        
        const xDiff = startX - e.touches[0].clientX;
        const yDiff = startY - e.touches[0].clientY;
        
        if (Math.abs(xDiff) > Math.abs(yDiff)) {
            // Horizontal swipe
            if (xDiff > 50) {
                // Left swipe - next page
                const nextBtn = document.querySelector('.pagination .page-item:last-child a');
                if (nextBtn && !nextBtn.parentElement.classList.contains('disabled')) {
                    nextBtn.click();
                }
            } else if (xDiff < -50) {
                // Right swipe - previous page
                const prevBtn = document.querySelector('.pagination .page-item:first-child a');
                if (prevBtn && !prevBtn.parentElement.classList.contains('disabled')) {
                    prevBtn.click();
                }
            }
        }
        
        startX = 0;
        startY = 0;
    });
}

// Debug mode
if (localStorage.getItem('debug') === 'true') {
    console.log('Loss Prevention System Debug Mode Enabled');
    
    // Add debug panel
    const debugPanel = document.createElement('div');
    debugPanel.innerHTML = `
        <div style="position: fixed; top: 10px; right: 10px; background: #000; color: #fff; padding: 10px; border-radius: 5px; z-index: 9999; font-family: monospace; font-size: 12px;">
            <div>Screen: ${window.innerWidth}x${window.innerHeight}</div>
            <div>User Agent: ${navigator.userAgent.split(' ')[0]}</div>
            <div>Timestamp: ${new Date().toISOString()}</div>
        </div>
    `;
    document.body.appendChild(debugPanel);
}
