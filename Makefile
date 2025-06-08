.PHONY: hooks style

hooks:
	pre-commit install

style:
	pre-commit run --all-files
