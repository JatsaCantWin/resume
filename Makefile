ifneq (,$(wildcard .env))
  include .env
  export
endif

ifndef DSPY_MODEL
  $(error DSPY_MODEL is not configured. Set it in .env or pass DSPY_MODEL=...)
endif

OUTPUT_DIRECTORY = output
OUTPUT_FILE = Piotr_Jurek_CV.pdf

MASTER_FILE = ./resume-data.yml
TEMPLATE_FILE = ./resume.tex.j2
RENDER_SCRIPT = ./render_template.py

SELECTION_FILE_NAME = selection.yml
GENERATE_SELECTION_SCRIPT = ./generate_selection.py

RENDERED_FILE_NAME = resume.tex

.PHONY: all render clean

all: select render

select:
	@echo "Selecting relevant experience..."
	@echo "Paste the job listing, then press Ctrl-D:"
	@python ./generate_selection.py --model $(DSPY_MODEL) $(MASTER_FILE) $(OUTPUT_DIRECTORY)/$(SELECTION_FILE_NAME)

render:
	@echo "Generating a resume file..."
	@python3 $(RENDER_SCRIPT) $(MASTER_FILE) $(OUTPUT_DIRECTORY)/$(SELECTION_FILE_NAME) $(TEMPLATE_FILE) $(OUTPUT_DIRECTORY)/$(RENDERED_FILE_NAME)
	@pdflatex -interaction=nonstopmode -halt-on-error -output-directory=$(OUTPUT_DIRECTORY) $(OUTPUT_DIRECTORY)/$(RENDERED_FILE_NAME) > /dev/null
	@mv "$(OUTPUT_DIRECTORY)/$$(basename $(RENDERED_FILE_NAME) .tex).pdf" "$(OUTPUT_DIRECTORY)/$(OUTPUT_FILE)"

clean:
	@rm -rf $(OUTPUT_DIRECTORY)
