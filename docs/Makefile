# Comma Tools Documentation Makefile

# You can set these variables from the command line.
SPHINXOPTS    ?=
SPHINXBUILD  ?= sphinx-build
SOURCEDIR    = .
BUILDDIR     = _build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

# Build HTML documentation
html:
	@$(SPHINXBUILD) -b html "$(SOURCEDIR)" "$(BUILDDIR)/html" $(SPHINXOPTS)
	@echo "Build finished. The HTML pages are in $(BUILDDIR)/html."

# Clean build directory
clean:
	rm -rf $(BUILDDIR)/*
	@echo "Cleaned build directory."

# Serve documentation locally
serve: html
	@echo "Serving documentation at http://localhost:8000"
	@cd $(BUILDDIR)/html && python3 -m http.server 8000

# Watch for changes and rebuild (requires entr)
watch:
	@echo "Watching for changes... Press Ctrl+C to stop"
	find . -name "*.rst" -o -name "*.md" -o -name "*.py" | entr -r make html

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)