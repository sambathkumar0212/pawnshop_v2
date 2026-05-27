/**
 * Simple and Robust Camera Capture for ID Documents
 * Version 5.0 - Simplified implementation
 */

console.log('Loading camera capture script v5...');

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing camera...');
    
    // Get all required elements
    const captureBtn = document.getElementById('capture-id-button');
    const cameraModal = document.getElementById('camera-container');
    const video = document.getElementById('camera-video');
    const takeBtn = document.getElementById('take-picture-button');
    const retakeBtn = document.getElementById('retake-picture-button');
    const confirmBtn = document.getElementById('confirm-picture-button');
    const cancelBtn = document.getElementById('cancel-picture-button');
    const preview = document.getElementById('id-image-preview');
    const previewSection = document.getElementById('image-preview-section');
    const hiddenField = document.getElementById('camera_image_data');
    
    // Check if we have all required elements
    if (!captureBtn || !cameraModal || !video) {
        console.log('Missing camera elements, camera capture not available');
        return;
    }
    
    console.log('All camera elements found, setting up...');
    
    let currentStream = null;
    let capturedImageData = null;
    const config = window.cameraConfig || {};
    
    // Start camera function
    async function startCamera() {
        console.log('Starting camera...');
        
        try {
            // Request camera permission
            currentStream = await navigator.mediaDevices.getUserMedia({
                video: { 
                    facingMode: 'environment',
                    width: { ideal: config.width || 1920 },
                    height: { ideal: config.height || 1080 },
                    focusMode: 'continuous',
                    sharpness: { ideal: 1.0 },
                    contrast: { ideal: 1.0 }
                }
            });
            
            console.log('Camera stream obtained');
            
            // Connect to video element
            video.srcObject = currentStream;
            
            // Show the modal
            cameraModal.style.display = 'block';
            document.body.style.overflow = 'hidden';
            
            // Reset buttons
            takeBtn.style.display = 'inline-block';
            retakeBtn.style.display = 'none';
            confirmBtn.style.display = 'none';
            
            console.log('Camera started successfully');
            
        } catch (error) {
            console.error('Camera error:', error);
            
            let message = 'Unable to access camera. ';
            if (error.name === 'NotAllowedError') {
                message += 'Please allow camera access and try again.';
            } else if (error.name === 'NotFoundError') {
                message += 'No camera found on this device.';
            } else {
                message += error.message;
            }
            
            alert(message);
            closeCamera();
        }
    }
    
    // Stop camera function
    function closeCamera() {
        console.log('Closing camera...');
        
        if (currentStream) {
            currentStream.getTracks().forEach(track => {
                console.log('Stopping track:', track.kind);
                track.stop();
            });
            currentStream = null;
        }
        
        if (video) {
            video.srcObject = null;
        }
        
        cameraModal.style.display = 'none';
        document.body.style.overflow = '';
        
        console.log('Camera closed');
    }
    
    // Take picture function
    function takePicture() {
        console.log('Taking picture...');
        
        if (!video.videoWidth || !video.videoHeight) {
            alert('Camera is not ready. Please wait a moment and try again.');
            return;
        }
        
        // Create canvas
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        
        // Draw video frame to canvas
        const ctx = canvas.getContext('2d');
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';
        ctx.drawImage(video, 0, 0);
        
        // Get image data
        capturedImageData = canvas.toDataURL('image/jpeg', config.quality || 0.95);
        
        // Update preview
        if (preview && previewSection) {
            preview.src = capturedImageData;
            previewSection.style.display = 'block';
        }
        
        // Update buttons
        takeBtn.style.display = 'none';
        retakeBtn.style.display = 'inline-block';
        confirmBtn.style.display = 'inline-block';
        
        console.log('Picture taken successfully');
    }
    
    // Confirm picture function
    function confirmPicture() {
        console.log('Confirming picture...');
        
        if (capturedImageData && hiddenField) {
            hiddenField.value = capturedImageData;
            console.log('Image data saved to hidden field');
        }
        
        closeCamera();
        alert('ID document image captured successfully!');
    }
    
    // Retake picture function
    function retakePicture() {
        console.log('Retaking picture...');
        
        takeBtn.style.display = 'inline-block';
        retakeBtn.style.display = 'none';
        confirmBtn.style.display = 'none';
        
        if (previewSection) {
            previewSection.style.display = 'none';
        }
    }
    
    // Cancel function
    function cancelCapture() {
        console.log('Cancelling capture...');
        
        capturedImageData = null;
        
        if (hiddenField) {
            hiddenField.value = '';
        }
        
        if (previewSection) {
            previewSection.style.display = 'none';
        }
        
        closeCamera();
    }
    
    // Event listeners
    captureBtn.addEventListener('click', function(e) {
        e.preventDefault();
        console.log('Capture button clicked');
        startCamera();
    });
    
    if (takeBtn) {
        takeBtn.addEventListener('click', function(e) {
            e.preventDefault();
            takePicture();
        });
    }
    
    if (retakeBtn) {
        retakeBtn.addEventListener('click', function(e) {
            e.preventDefault();
            retakePicture();
        });
    }
    
    if (confirmBtn) {
        confirmBtn.addEventListener('click', function(e) {
            e.preventDefault();
            confirmPicture();
        });
    }
    
    if (cancelBtn) {
        cancelBtn.addEventListener('click', function(e) {
            e.preventDefault();
            cancelCapture();
        });
    }
    
    // Cleanup on page unload
    window.addEventListener('beforeunload', function() {
        if (currentStream) {
            currentStream.getTracks().forEach(track => track.stop());
        }
    });
    
    console.log('Camera capture initialized successfully');
});
