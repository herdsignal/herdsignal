import AppKit
import Foundation

let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
let source = root.appendingPathComponent("frontend/src/assets/brand/herdsignal-mark.svg")
let destination = root.appendingPathComponent("assets/herdsignal-avatar.png")
let size = 512

guard let image = NSImage(contentsOf: source) else {
    fatalError("HerdSignal 로고를 읽을 수 없습니다: \(source.path)")
}

guard let bitmap = NSBitmapImageRep(
    bitmapDataPlanes: nil,
    pixelsWide: size,
    pixelsHigh: size,
    bitsPerSample: 8,
    samplesPerPixel: 4,
    hasAlpha: true,
    isPlanar: false,
    colorSpaceName: .deviceRGB,
    bytesPerRow: 0,
    bitsPerPixel: 0
) else {
    fatalError("PNG 캔버스를 만들 수 없습니다.")
}

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
image.draw(
    in: NSRect(x: 0, y: 0, width: size, height: size),
    from: NSRect(origin: .zero, size: image.size),
    operation: .copy,
    fraction: 1
)
NSGraphicsContext.restoreGraphicsState()

guard let png = bitmap.representation(using: .png, properties: [:]) else {
    fatalError("PNG 인코딩에 실패했습니다.")
}

try png.write(to: destination)
print(destination.path)
