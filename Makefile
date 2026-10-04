OUTPUT_DIRECTORY = output
OUTPUT_FILE = Piotr_Jurek_CV.pdf

.PHONY: all render clean

all: render 

render:
	mkdir $(OUTPUT_DIRECTORY)
	pdflatex -interaction=nonstopmode -halt-on-error \
	  -output-directory=$(OUTPUT_DIRECTORY) "resume-template.tex"
	pdflatex -interaction=nonstopmode -halt-on-error \
	  -output-directory=$(OUTPUT_DIRECTORY) "resume-template.tex"
	mv "$(OUTPUT_DIRECTORY)/resume-template.pdf" "$(OUTPUT_DIRECTORY)/$(OUTPUT_FILE)"

clean:
	@rm -rf $(OUTPUT_DIRECTORY)
