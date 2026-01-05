.PHONY: demo demo-raw docs install test clean

# Record and process demo video
demo: demo-raw
	./scripts/process-demo.sh

# Record raw demo (requires running instance capability)
demo-raw:
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
	rm -f docs/assets/demo-raw.mp4 docs/assets/demo-raw.gif
