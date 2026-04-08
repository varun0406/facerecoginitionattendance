/**
 * Camera utility functions for cross-platform compatibility
 * Works on both desktop (laptop) and mobile devices
 *
 * Browsers only allow getUserMedia in a "secure context": HTTPS, or
 * http://localhost / http://127.0.0.1. Plain http://YOUR_PUBLIC_IP will NOT work.
 */

/** True only when the browser may allow camera (HTTPS or localhost). */
export function isCameraAllowedByBrowser() {
  if (typeof window === 'undefined') return true
  return window.isSecureContext === true
}

export function getInsecureCameraMessage() {
  return (
    'Camera is disabled on plain HTTP for this address. Browsers require HTTPS or localhost. ' +
    'Fix: (1) Add HTTPS (nginx + Let’s Encrypt), or (2) SSH tunnel from your PC: ' +
    'ssh -L 8002:127.0.0.1:8002 root@YOUR_SERVER — then open http://localhost:8002'
  )
}

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
    if (!isCameraAllowedByBrowser()) {
      return {
        success: false,
        stream: null,
        error: getInsecureCameraMessage(),
      }
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return {
        success: false,
        stream: null,
        error:
          'Camera API unavailable. Use a current Chrome/Firefox/Edge, or HTTPS / localhost.',
      }
    }

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

    if (error.name === 'SecurityError' || /secure context/i.test(String(error.message))) {
      errorMessage = getInsecureCameraMessage()
    } else if (error.name === 'NotAllowedError') {
      errorMessage =
        'Camera permission denied. Allow camera in the address bar, or use HTTPS / http://localhost (see banner above).'
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

/**
 * Attach a MediaStream to a <video> after React has mounted the element.
 * Call from useEffect when videoRef.current and stream are both available.
 */
export async function bindStreamToVideoElement(video, stream) {
  if (!video || !stream) return
  if (video.srcObject !== stream) {
    video.srcObject = stream
  }
  video.muted = true
  video.setAttribute('playsinline', '')
  video.playsInline = true
  try {
    await video.play()
  } catch (e) {
    console.warn('video.play():', e)
  }
}

/**
 * Wait until the video has non-zero dimensions (enough to drawImage).
 * More reliable than requiring HAVE_ENOUGH_DATA alone.
 */
export function waitForVideoDrawReady(video, timeoutMs = 20000) {
  return new Promise((resolve) => {
    if (!video) {
      resolve(false)
      return
    }
    let timer
    const cleanup = () => {
      clearTimeout(timer)
      video.removeEventListener('loadeddata', onTry)
      video.removeEventListener('loadedmetadata', onTry)
      video.removeEventListener('canplay', onTry)
      video.removeEventListener('playing', onTry)
    }
    const onTry = () => {
      if (video.videoWidth > 0 && video.videoHeight > 0) {
        cleanup()
        resolve(true)
      }
    }
    onTry()
    video.addEventListener('loadeddata', onTry)
    video.addEventListener('loadedmetadata', onTry)
    video.addEventListener('canplay', onTry)
    video.addEventListener('playing', onTry)
    timer = setTimeout(() => {
      cleanup()
      resolve(video.videoWidth > 0 && video.videoHeight > 0)
    }, timeoutMs)
  })
}
