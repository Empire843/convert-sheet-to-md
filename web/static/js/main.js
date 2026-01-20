// Global state
let uploadedFiles = [];
let convertedFiles = [];

// DOM Elements
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const uploadedFilesList = document.getElementById('uploadedFilesList');
const uploadedFilesSection = document.getElementById('uploadedFiles');
const executeBtn = document.getElementById('executeBtn');
const clearBtn = document.getElementById('clearBtn');
const progressContainer = document.getElementById('progress');
const resultsSection = document.getElementById('resultsSection');
const resultsList = document.getElementById('resultsList');
const downloadAllBtn = document.getElementById('downloadAllBtn');

// DOM Elements (New)
const aiConfigSection = document.getElementById('aiConfigSection');
const customConfigToggle = document.getElementById('customConfigToggle');
const customConfigForm = document.getElementById('customConfigForm');
const toggleKeyBtn = document.getElementById('toggleKeyBtn');
const apiKeyInput = document.getElementById('apiKey');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadConvertedFiles();
    checkAIAvailability();
    setupAIConfigListeners();
});

// Setup event listeners
function setupEventListeners() {
    // Drag and drop - only trigger if not clicking the file button
    dropZone.addEventListener('click', (e) => {
        // Don't trigger if clicking the file button or its label
        if (!e.target.closest('.file-button') && !e.target.closest('input[type="file"]') && !e.target.closest('select') && !e.target.closest('input') && !e.target.closest('textarea')) {
            fileInput.click();
        }
    });
    dropZone.addEventListener('dragover', handleDragOver);
    dropZone.addEventListener('dragleave', handleDragLeave);
    dropZone.addEventListener('drop', handleDrop);

    // File input
    fileInput.addEventListener('change', handleFileSelect);

    // Buttons
    executeBtn.addEventListener('click', executeConversion);
    clearBtn.addEventListener('click', clearAll);
    downloadAllBtn.addEventListener('click', downloadAll);
}

function setupAIConfigListeners() {
    // Radio buttons for mode change
    document.querySelectorAll('input[name="conversionMode"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            if (e.target.value === 'ai') {
                aiConfigSection.style.display = 'block';
            } else {
                aiConfigSection.style.display = 'none';
            }
        });
    });

    // Custom config toggle
    customConfigToggle.addEventListener('change', (e) => {
        if (e.target.checked) {
            customConfigForm.style.display = 'block';
        } else {
            customConfigForm.style.display = 'none';
        }
    });

    // Toggle password visibility
    toggleKeyBtn.addEventListener('click', () => {
        if (apiKeyInput.type === 'password') {
            apiKeyInput.type = 'text';
            toggleKeyBtn.textContent = '🔒';
        } else {
            apiKeyInput.type = 'password';
            toggleKeyBtn.textContent = '👁️';
        }
    });
}
// Drag and drop handlers
function handleDragOver(e) {
    e.preventDefault();
    dropZone.classList.add('drag-over');
}

function handleDragLeave(e) {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    dropZone.classList.remove('drag-over');

    const files = Array.from(e.dataTransfer.files);
    uploadFiles(files);
}

// File selection handler
function handleFileSelect(e) {
    const files = Array.from(e.target.files);
    uploadFiles(files);
}

// Upload files to server
async function uploadFiles(files) {
    if (files.length === 0) return;

    const formData = new FormData();
    files.forEach(file => {
        formData.append('files[]', file);
    });

    try {
        showToast('Đang upload file...', 'info');

        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            uploadedFiles = [...uploadedFiles, ...data.uploaded];
            updateUploadedFilesList();
            showToast(data.message, 'success');
            executeBtn.disabled = false;
        } else {
            showToast(data.error || 'Upload thất bại', 'error');
        }

        if (data.errors && data.errors.length > 0) {
            data.errors.forEach(error => showToast(error, 'error'));
        }
    } catch (error) {
        console.error('Upload error:', error);
        showToast('Lỗi khi upload file', 'error');
    }

    // Reset input
    fileInput.value = '';
}


// Update uploaded files list UI
function updateUploadedFilesList() {
    if (uploadedFiles.length === 0) {
        uploadedFilesSection.style.display = 'none';
        executeBtn.disabled = true;
        return;
    }

    uploadedFilesSection.style.display = 'block';
    uploadedFilesList.innerHTML = uploadedFiles.map((file, index) => `
        <li>
            <div class="file-info">
                <span class="file-name">📄 ${file.name}</span>
                <span class="file-size">(${file.size})</span>
            </div>
            <button class="remove-file-btn" onclick="removeFile(${index})" title="Xóa file">✕</button>
        </li>
    `).join('');
}

// Remove a file from uploaded files list
function removeFile(index) {
    uploadedFiles.splice(index, 1);
    updateUploadedFilesList();
    showToast(`Đã xóa file`, 'info');
}


// Execute conversion
async function executeConversion() {
    if (uploadedFiles.length === 0) {
        showToast('Vui lòng upload file trước', 'error');
        return;
    }

    // Get selected conversion mode
    const mode = document.querySelector('input[name="conversionMode"]:checked').value;

    // Prepare payload
    const payload = { mode: mode };

    if (mode === 'ai') {
        // Collect AI config
        const useCustomConfig = document.getElementById('customConfigToggle').checked;
        const systemPrompt = document.getElementById('systemPrompt').value;

        payload.ai_config = {
            use_custom_config: useCustomConfig,
            system_prompt: systemPrompt
        };

        if (useCustomConfig) {
            const provider = document.getElementById('aiProvider').value;
            const apiKey = document.getElementById('apiKey').value;
            const modelName = document.getElementById('modelName').value;

            if (!apiKey) {
                showToast('Vui lòng nhập API Key', 'error');
                return;
            }

            payload.ai_config.provider = provider;
            payload.ai_config.api_key = apiKey;
            payload.ai_config.model_name = modelName;
        }
    }

    try {
        // Show progress
        progressContainer.style.display = 'block';
        executeBtn.disabled = true;
        resultsSection.style.display = 'none';

        const response = await fetch('/api/convert', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (data.success || (data.files && data.files.length > 0)) {
            convertedFiles = data.files;
            displayResults(data.errors); // Pass errors to display function
            const modeText = mode === 'ai' ? 'AI' : 'Traditional';
            if (data.success) {
                showToast(data.message, 'success');
            } else {
                showToast(data.message || 'Có lỗi xảy ra', 'warning');
            }
        } else {
            // Handle case where ALL files failed
            if (data.errors && data.errors.length > 0) {
                convertedFiles = [];
                displayResults(data.errors);
                showToast('Chuyển đổi thất bại: Tất cả file đều gặp lỗi', 'error');
            } else {
                showToast(data.error || 'Conversion thất bại', 'error');
            }
        }
    } catch (error) {
        console.error('Conversion error:', error);
        showToast('Lỗi khi chuyển đổi', 'error');
    } finally {
        progressContainer.style.display = 'none';
        executeBtn.disabled = false;
    }
}

// Load converted files from server
async function loadConvertedFiles() {
    try {
        const response = await fetch('/api/files');
        const data = await response.json();

        if (data.success && data.files.length > 0) {
            convertedFiles = data.files;
            displayResults();
        }
    } catch (error) {
        console.error('Error loading files:', error);
    }
}

// Display conversion results (supports errors)
function displayResults(errors = []) {
    if (convertedFiles.length === 0 && errors.length === 0) {
        resultsSection.style.display = 'none';
        return;
    }

    resultsSection.style.display = 'block';

    let html = '';

    // Render errors first
    if (errors && errors.length > 0) {
        html += `<div class="error-list">`;
        errors.forEach(err => {
            html += `
                <div class="result-item error-item" style="border-left: 4px solid #e74c3c; background: #fff0f0;">
                    <div class="result-item-info">
                        <span class="result-item-icon">⚠️</span>
                        <div class="result-item-details">
                            <div class="result-item-name">${err.file}</div>
                            <div class="result-item-size" style="color: #c0392b;">${err.error}</div>
                        </div>
                    </div>
                </div>
            `;
        });
        html += `</div>`;
    }

    html += convertedFiles.map(file => {
        const icon = file.type === 'image' ? '🖼️' : '📝';
        return `
            <div class="result-item">
                <div class="result-item-info">
                    <span class="result-item-icon">${icon}</span>
                    <div class="result-item-details">
                        <div class="result-item-name">${file.name}</div>
                        <div class="result-item-size">${file.size}</div>
                    </div>
                </div>
                <div class="result-item-actions">
                    <button class="result-action-btn delete-btn" onclick="deleteFile('${file.path}')" title="Xóa file">🗑️</button>
                    <button class="result-action-btn download-btn" onclick="downloadFile('${file.path}')" title="Tải xuống">⬇️</button>
                </div>
            </div>
        `;
    }).join('');

    resultsList.innerHTML = html;
}

// Download a specific file
async function downloadFile(filepath) {
    try {
        window.location.href = `/api/download/${filepath}`;
        showToast('Đang tải file...', 'info');
    } catch (error) {
        console.error('Download error:', error);
        showToast('Lỗi khi tải file', 'error');
    }
}

// Delete a specific file
async function deleteFile(filepath) {
    if (!confirm(`Bạn có chắc muốn xóa file "${filepath}"?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/delete/${filepath}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            // Remove from UI
            convertedFiles = convertedFiles.filter(f => f.path !== filepath);
            displayResults();
            showToast('Đã xóa file', 'success');
        } else {
            showToast(data.error || 'Xóa file thất bại', 'error');
        }
    } catch (error) {
        console.error('Delete error:', error);
        showToast('Lỗi khi xóa file', 'error');
    }
}

// Download all files as ZIP
async function downloadAll() {
    try {
        window.location.href = '/api/download-all';
        showToast('Đang tạo file ZIP...', 'info');
    } catch (error) {
        console.error('Download all error:', error);
        showToast('Lỗi khi tải tất cả file', 'error');
    }
}

// Clear all files
async function clearAll() {
    if (!confirm('Bạn có chắc muốn xóa tất cả file?')) {
        return;
    }

    try {
        const response = await fetch('/api/clear', {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            uploadedFiles = [];
            convertedFiles = [];
            updateUploadedFilesList();
            resultsSection.style.display = 'none';
            executeBtn.disabled = true;
            showToast(data.message, 'success');
        } else {
            showToast(data.error || 'Xóa thất bại', 'error');
        }
    } catch (error) {
        console.error('Clear error:', error);
        showToast('Lỗi khi xóa file', 'error');
    }
}

// Show toast notification
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icons = {
        success: '✅',
        error: '❌',
        info: 'ℹ️'
    };

    toast.innerHTML = `
        <span class="toast-icon">${icons[type]}</span>
        <span class="toast-message">${message}</span>
    `;

    const container = document.getElementById('toastContainer');
    container.appendChild(toast);

    // Auto remove after 3 seconds
    setTimeout(() => {
        toast.style.animation = 'slideInRight 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Check AI availability
async function checkAIAvailability() {
    try {
        const response = await fetch('/api/check-ai');
        const data = await response.json();

        const aiRadio = document.getElementById('aiModeRadio');
        const aiLabel = aiRadio.nextElementSibling;

        if (!data.available) {
            aiRadio.disabled = true;
            aiLabel.title = data.message;

            // Add visual indicator
            const modeDesc = aiLabel.querySelector('.mode-desc');
            modeDesc.textContent = 'Chưa cấu hình API key';
        } else {
            console.log('AI conversion available');
        }
    } catch (error) {
        console.error('Error checking AI availability:', error);
    }
}
