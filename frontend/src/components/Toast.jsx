import { useState, useEffect, useCallback } from 'react'

/**
 * Toast notification state manager
 */
let toastListeners = []
let toastId = 0

export function showToast(message, type = 'success', duration = 3000) {
  const id = ++toastId
  toastListeners.forEach(listener => listener({ id, message, type, duration }))
  return id
}

export function useToast() {
  return { showToast }
}

/**
 * Toast component - renders at top of screen
 */
export function Toast() {
  const [toasts, setToasts] = useState([])

  useEffect(() => {
    const listener = (toast) => {
      setToasts(prev => [...prev, toast])
      
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== toast.id))
      }, toast.duration)
    }
    
    toastListeners.push(listener)
    return () => {
      toastListeners = toastListeners.filter(l => l !== listener)
    }
  }, [])

  if (toasts.length === 0) return null

  return (
    <div className="toast-container">
      {toasts.map(toast => (
        <div 
          key={toast.id} 
          className={`toast toast-${toast.type}`}
        >
          {toast.type === 'success' && (
            <svg className="icon" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
          )}
          {toast.type === 'error' && (
            <svg className="icon" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          )}
          <span>{toast.message}</span>
        </div>
      ))}
    </div>
  )
}

export default Toast
