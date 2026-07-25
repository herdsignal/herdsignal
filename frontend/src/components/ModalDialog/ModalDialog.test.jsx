import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ModalDialog from './ModalDialog'

afterEach(cleanup)

describe('ModalDialog', () => {
  it('traps focus, closes on Escape, and restores the previous focus target', () => {
    const onClose = vi.fn()
    const { rerender } = render(
      <>
        <button type="button">열기</button>
      </>,
    )
    const opener = screen.getByRole('button', { name: '열기' })
    opener.focus()

    rerender(
      <>
        <button type="button">열기</button>
        <ModalDialog
          onClose={onClose}
          labelledBy="dialog-title"
          overlayClassName="overlay"
          dialogClassName="dialog"
        >
          <h2 id="dialog-title">테스트 모달</h2>
          <button type="button" data-modal-autofocus>첫 버튼</button>
          <button type="button">마지막 버튼</button>
        </ModalDialog>
      </>,
    )

    expect(screen.getByRole('dialog', { name: '테스트 모달' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '첫 버튼' })).toHaveFocus()

    const last = screen.getByRole('button', { name: '마지막 버튼' })
    last.focus()
    fireEvent.keyDown(last, { key: 'Tab' })
    expect(screen.getByRole('button', { name: '첫 버튼' })).toHaveFocus()

    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    expect(onClose).toHaveBeenCalledOnce()

    rerender(<button type="button">열기</button>)
    expect(screen.getByRole('button', { name: '열기' })).toHaveFocus()
  })
})
