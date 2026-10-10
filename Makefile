# `make install` builds the capture program, ships it inside the Python package and installs the CLI.

CAPTURE_BUILT := capture/.build/release/tldl-capture
CAPTURE_PACKAGED := src/tldl/bin/tldl-capture

.PHONY: install capture

install: capture
	uv tool install --force --reinstall .

capture:
	swift build --package-path capture --configuration release
	mkdir -p $(dir $(CAPTURE_PACKAGED))
	cp $(CAPTURE_BUILT) $(CAPTURE_PACKAGED)
