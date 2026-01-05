.PHONY: demo docs install test clean

# Record demo video (requires Lambda API credentials)
demo:
	vhs scripts/demo.tape

# Serve docs locally
docs:
	cd docs && mkdocs serve

# Install CLI in development mode
install:
	cd cli && pip install -e ".[test]"

# Run tests
test:
	cd cli && pytest -v

# Clean generated files
clean:
	rm -f docs/assets/demo.mp4 docs/assets/demo.gif
