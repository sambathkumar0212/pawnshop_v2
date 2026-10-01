/**
 * Unified Camera Capture for Customer Profile Photo and ID Documents
 * Version 6.0
 */

console.log('Loading unified camera capture script v6...');

document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing unified camera capture...');

    // Trigger buttons
    const captureProfileBtn = document.getElementById('capture-profile-button');
    const captureIdBtn = document.getElementById('capture-id-button');

    // Modal elements
    const cameraModal = document.getElementById('camera-container');
    const modalTitle = document.getElementById('camera-modal-title');
    const video = document.getElementById('camera-video');
    const canvas = document.getElementById('camera-canvas');
    const loading = document.getElementById('camera-loading');

    // Modal action buttons
    const takeBtn = document.getElementById('take-picture-button');
    const retakeBtn = document.getElementById('retake-picture-button');
    const confirmBtn = document.getElementById('confirm-picture-button');
    const cancelBtn = document.getElementById('cancel-picture-button');

    // Target elements for ID Document
    const idHiddenField = document.getElementById('camera_image_data');
    const idPreview = document.getElementById('id-image-preview');
    const idPreviewSection = document.getElementById('image-preview-section');
    const idDownloadBtn = document.getElementById('download-id-photo');
    const idDeleteBtn = document.getElementById('delete-id-photo');
    const idRemoveField = document.getElementById('remove_id_image');

    // Target elements for Profile Photo
    const profileHiddenField = document.getElementById('profile_photo_data');
    const profilePreview = document.getElementById('profile-photo-preview');
    const profilePreviewSection = document.getElementById('profile-photo-preview-section');
    const profileDownloadBtn = document.getElementById('download-profile-photo');
    const profileDeleteBtn = document.getElementById('delete-profile-photo');
    const profileRemoveField = document.getElementById('remove_profile_photo');

    if (!cameraModal || !video) {
        console.log('Camera modal elements not found');
        return;
    }

    let currentStream = null;
    let capturedImageData = null;
    let currentTarget = 'profile'; // 'profile' or 'id'

    function browserSupportsCamera() {
        return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
    }

    async function getCameraStream(target) {
        if (!browserSupportsCamera()) {
            throw new Error('Camera is not supported in this browser/device.');
        }

        const preferredFacing = target === 'profile' ? 'user' : 'environment';
        const fallbackFacing = target === 'profile' ? 'environment' : 'user';

        const constraintList = [
            {
                width: { ideal: 1280 },
                height: { ideal: 720 },
                facingMode: { ideal: preferredFacing }
            },
            {
                facingMode: { ideal: preferredFacing }
            },
            {
                facingMode: { ideal: fallbackFacing }
            },
            {
                width: { ideal: 640 },
                height: { ideal: 480 }
            },
            true
        ];

        let lastError = null;
        for (const videoConstraints of constraintList) {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    video: videoConstraints,
                    audio: false
                });
                return stream;
            } catch (err) {
                lastError = err;
                console.warn('Camera constraint failed:', videoConstraints, err);
            }
        }

        throw lastError || new Error('Unable to start camera.');
    }

    async function openCamera(target) {
        currentTarget = target;
        capturedImageData = null;

        if (modalTitle) {
            modalTitle.innerHTML = target === 'profile'
                ? '<i class="fas fa-user-circle me-2"></i>Capture Customer Photo'
                : '<i class="fas fa-id-card me-2"></i>Capture ID Document';
        }

        // Show modal and loading state
        cameraModal.style.display = 'block';
        document.body.style.overflow = 'hidden';

        if (loading) loading.style.display = 'block';
        if (canvas) canvas.style.display = 'none';
        video.style.display = 'block';

        takeBtn.style.display = 'none';
        retakeBtn.style.display = 'none';
        confirmBtn.style.display = 'none';

        try {
            currentStream = await getCameraStream(target);
            video.srcObject = currentStream;

            video.onloadedmetadata = () => {
                video.play()
                    .then(() => {
                        if (loading) loading.style.display = 'none';
                        takeBtn.style.display = 'inline-block';
                        console.log('Camera running smoothly');
                    })
                    .catch(err => {
                        console.error('Error playing video:', err);
                        if (loading) loading.style.display = 'none';
                        takeBtn.style.display = 'inline-block';
                    });
            };
        } catch (error) {
            console.error('Camera access error:', error);
            if (loading) loading.style.display = 'none';

            let msg = 'Unable to access camera. ';
            if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
                msg = 'Camera permission was denied. Please allow camera permissions in your browser and try again.';
            } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
                msg = 'No camera found on this device.';
            } else if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
                msg = 'Camera is in use by another application. Please close other camera apps and retry.';
            } else if (!window.isSecureContext && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
                msg = 'Camera requires a secure HTTPS connection or localhost.';
            } else {
                msg += error.message || '';
            }

            alert(msg);
            closeCamera();
        }
    }

    function closeCamera() {
        if (currentStream) {
            currentStream.getTracks().forEach(track => track.stop());
            currentStream = null;
        }

        if (video) {
            video.srcObject = null;
        }

        cameraModal.style.display = 'none';
        document.body.style.overflow = '';
        if (loading) loading.style.display = 'none';
        if (canvas) canvas.style.display = 'none';
    }

    function takePicture() {
        if (!video.videoWidth || !video.videoHeight) {
            alert('Camera is not ready yet. Please wait a moment.');
            return;
        }

        const targetCanvas = canvas || document.createElement('canvas');
        targetCanvas.width = video.videoWidth;
        targetCanvas.height = video.videoHeight;

        const ctx = targetCanvas.getContext('2d');
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';
        ctx.drawImage(video, 0, 0, targetCanvas.width, targetCanvas.height);

        capturedImageData = targetCanvas.toDataURL('image/jpeg', 0.92);

        // Display captured snapshot on canvas
        if (canvas) {
            canvas.style.display = 'block';
            video.style.display = 'none';
        }

        takeBtn.style.display = 'none';
        retakeBtn.style.display = 'inline-block';
        confirmBtn.style.display = 'inline-block';
    }

    function retakePicture() {
        capturedImageData = null;
        if (canvas) canvas.style.display = 'none';
        video.style.display = 'block';

        takeBtn.style.display = 'inline-block';
        retakeBtn.style.display = 'none';
        confirmBtn.style.display = 'none';
    }

    function confirmPicture() {
        if (!capturedImageData) return;

        if (currentTarget === 'profile') {
            if (profileHiddenField) profileHiddenField.value = capturedImageData;
            if (profilePreview) profilePreview.src = capturedImageData;
            if (profilePreviewSection) profilePreviewSection.style.display = 'block';
            if (profileDownloadBtn) {
                profileDownloadBtn.href = capturedImageData;
                profileDownloadBtn.style.display = 'inline-block';
            }
            if (profileDeleteBtn) profileDeleteBtn.style.display = 'inline-block';
            if (profileRemoveField) profileRemoveField.value = '0';
        } else {
            if (idHiddenField) idHiddenField.value = capturedImageData;
            if (idPreview) idPreview.src = capturedImageData;
            if (idPreviewSection) idPreviewSection.style.display = 'block';
            if (idDownloadBtn) {
                idDownloadBtn.href = capturedImageData;
                idDownloadBtn.style.display = 'inline-block';
            }
            if (idDeleteBtn) idDeleteBtn.style.display = 'inline-block';
            if (idRemoveField) idRemoveField.value = '0';
        }

        if (typeof window.saveCustomerDraft === 'function') {
            window.saveCustomerDraft();
        }

        closeCamera();
    }

    // Attach trigger event listeners
    if (captureProfileBtn) {
        captureProfileBtn.addEventListener('click', function(e) {
            e.preventDefault();
            openCamera('profile');
        });
    }

    if (captureIdBtn) {
        captureIdBtn.addEventListener('click', function(e) {
            e.preventDefault();
            openCamera('id');
        });
    }

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
            closeCamera();
        });
    }

    // Close on click outside modal inner
    cameraModal.addEventListener('click', function(e) {
        if (e.target === cameraModal) {
            closeCamera();
        }
    });

    // Close on ESC key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && cameraModal.style.display === 'block') {
            closeCamera();
        }
    });

    // Stop streams on page unload
    window.addEventListener('beforeunload', function() {
        if (currentStream) {
            currentStream.getTracks().forEach(track => track.stop());
        }
    });

    console.log('Unified camera capture initialized successfully.');
});
