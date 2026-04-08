/**
 * Camera utility functions for cross-platform compatibility
 * Works on both desktop (laptop) and mobile devices
 */

/**
 * Get camera constraints optimized for both desktop and mobile
 */
export function getCameraConstraints() {
  // Check if we're on a mobile device
  const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
  
  if (isMobile) {
    // Mobile-optimized constraints
    return {
      video: {
        facingMode: 'user', // Front-facing camera
        width: { ideal: 640, max: 1280 },
        height: { ideal: 480, max: 720 },
        aspectRatio: { ideal: 1.7777777778 }, // 16:9
        // Mobile-specific optimizations
        frameRate: { ideal: 30, max: 30 }
      }
    }
  } else {
    // Desktop-optimized constraints
    return {
      video: {
        facingMode: 'user', // Webcam
        width: { ideal: 640, max: 1280 },
        height: { ideal: 480, max: 720 },
        aspectRatio: { ideal: 1.7777777778 }
      }
    }
  }
}

/**
 * Check if camera access is available
 */
export async function checkCameraAvailability() {
  try {
    // Check if getUserMedia is available
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return {
        available: false,
        error: 'Camera API not supported in this browser'
      }
    }
    
    // Try to enumerate devices to check camera availability
    const devices = await navigator.mediaDevices.enumerateDevices()
    const hasVideoInput = devices.some(device => device.kind === 'videoinput')
    
    if (!hasVideoInput) {
      return {
        available: false,
        error: 'No camera found on this device'
      }
    }
    
    return {
      available: true,
      error: null
    }
  } catch (error) {
    return {
      available: false,
      error: error.message
    }
  }
}

/**
 * Request camera access with fallback
 */
export async function requestCameraAccess(constraints = null) {
  try {
    if (!constraints) {
      constraints = getCameraConstraints()
    }
    
    const stream = await navigator.mediaDevices.getUserMedia(constraints)
    return {
      success: true,
      stream: stream,
      error: null
    }
  } catch (error) {
    let errorMessage = 'Camera access denied'
    
    if (error.name === 'NotAllowedError') {
      errorMessage = 'Camera permission denied. Please allow camera access in your browser settings.'
    } else if (error.name === 'NotFoundError') {
      errorMessage = 'No camera found on this device.'
    } else if (error.name === 'NotReadableError') {
      errorMessage = 'Camera is already in use by another application.'
    } else if (error.name === 'OverconstrainedError') {
      // Try with simpler constraints
      try {
        const fallbackConstraints = {
          video: {
            facingMode: 'user'
          }
        }
        const stream = await navigator.mediaDevices.getUserMedia(fallbackConstraints)
        return {
          success: true,
          stream: stream,
          error: null,
          fallback: true
        }
      } catch (fallbackError) {
        errorMessage = 'Camera constraints not supported. Please try a different device.'
      }
    } else {
      errorMessage = `Camera error: ${error.message}`
    }
    
    return {
      success: false,
      stream: null,
      error: errorMessage
    }
  }
}

