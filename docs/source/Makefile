# Minimal makefile for Sphinx documentation

# You can set these variables from the command line.
SPHINXOPTS    = 
SPHINXBUILD   = sphinx-build 
SOURCEDIR     = .
BUILDDIR      = ../build

.PHONY: help build

# "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)"

clean: 
	rm -rf $(BUILDDIR)
	@echo "Deleted directory $(BUILDDIR)."

# $(O) is meant as a shortcut for $(SPHINXOPTS).
html:
#	./symlink_examples.sh
	@start=$$(date +%s); \
	$(SPHINXBUILD) -M html "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O) \
	--no-color 2> build_warnings.log; \
	end=$$(date +%s); \
	echo "Build time: $$((end - start)) seconds"


