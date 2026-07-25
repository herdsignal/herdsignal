import { useEffect, useRef } from 'react'

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

export default function ModalDialog({
  children,
  onClose,
  labelledBy,
  overlayClassName,
  dialogClassName,
  onDialogKeyDown,
}) {
  const dialogRef = useRef(null)
  const previousFocusRef = useRef(null)

  useEffect(() => {
    previousFocusRef.current = document.activeElement
    const dialog = dialogRef.current
    const initialTarget = dialog?.querySelector('[data-modal-autofocus]')
      ?? dialog?.querySelector(FOCUSABLE)
      ?? dialog
    initialTarget?.focus()

    return () => {
      const previous = previousFocusRef.current
      if (previous instanceof HTMLElement && document.contains(previous)) {
        previous.focus()
      }
    }
  }, [])

  function handleKeyDown(event) {
    if (event.key === 'Escape') {
      event.preventDefault()
      onClose()
      return
    }
    if (event.key !== 'Tab') {
      onDialogKeyDown?.(event)
      return
    }

    const focusable = [...dialogRef.current.querySelectorAll(FOCUSABLE)]
    if (focusable.length === 0) {
      event.preventDefault()
      dialogRef.current.focus()
      return
    }
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  return (
    <div
      className={overlayClassName}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        ref={dialogRef}
        className={dialogClassName}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        tabIndex="-1"
        onKeyDown={handleKeyDown}
      >
        {children}
      </div>
    </div>
  )
}
