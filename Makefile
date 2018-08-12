# simple Makefile for some common tasks
.PHONY: dist release pypi tagv

tagv:
	git tag -s \
		-m `python -c 'import placeload; print(placeload.__version__)'` \
		`python -c 'import placeload; print(placeload.__version__)'`
	git push origin master --tags

dist:
	python setup.py sdist bdist_wheel

release: tagv pypi

pypi:
	python setup.py sdist bdist_wheel upload --sign
