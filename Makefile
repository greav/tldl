# `make install` builds the capture program, ships it inside the Python package and installs the CLI.

CAPTURE_BUILT := capture/.build/release/tldl-capture
CAPTURE_PACKAGED := src/tldl/bin/tldl-capture

.PHONY: install capture

# `tldl record` works without ffmpeg; the other commands do not, so its absence is said, not fatal.
install: capture
	uv tool install --force --reinstall .
	@command -v ffmpeg > /dev/null || echo "Note: ffmpeg is not on the PATH. tldl transcribe and tldl stereo need it; install it, for example with: brew install ffmpeg"

capture:
	swift build --package-path capture --configuration release
	mkdir -p $(dir $(CAPTURE_PACKAGED))
	cp $(CAPTURE_BUILT) $(CAPTURE_PACKAGED)
