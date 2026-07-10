import '@testing-library/jest-dom/vitest'
import { beforeEach } from 'vitest'

const values = new Map()
const memoryStorage = {
  getItem: (key) => values.has(String(key)) ? values.get(String(key)) : null,
  setItem: (key, value) => { values.set(String(key), String(value)) },
  removeItem: (key) => { values.delete(String(key)) },
  clear: () => { values.clear() },
  key: (index) => [...values.keys()][index] ?? null,
  get length() { return values.size },
}

Object.defineProperty(window, 'localStorage', { value: memoryStorage, configurable: true })
Object.defineProperty(globalThis, 'localStorage', { value: memoryStorage, configurable: true })

Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
  configurable: true,
  value: () => ({
    arc() {}, beginPath() {}, clearRect() {}, fill() {}, lineTo() {}, moveTo() {}, stroke() {},
    fillStyle: '', strokeStyle: '', globalAlpha: 1, lineWidth: 1,
  }),
})

globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  localStorage.clear()
})
