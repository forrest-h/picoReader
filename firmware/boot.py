import storage
import board
import digitalio
# COM pins must be driven for the 5-way keypad matrix to work
for pin in (board.GP12, board.GP7):
  p = digitalio.DigitalInOut(pin)
  p.switch_to_output()
# Check CENTER button (GP11) — hold during boot for USB write access
btn = digitalio.DigitalInOut(board.GP11)
btn.direction = digitalio.Direction.INPUT
btn.pull = digitalio.Pull.UP

usb_writable = not btn.value  # pressed = low = False

btn.deinit()

if not usb_writable:
  # Normal mode: CircuitPython gets write access (USB is read-only)
  storage.remount("/", False)
# else: USB stays writable for file transfers (saves won't work)
