tests:
	bin/python `which nosetests` --no-path-adjustment light9.rdfdb.rdflibpatch

install_python_deps:
	env/bin/pip install -r pydeps

PYTHON=/usr/bin/pypy
PYTHON=/usr/bin/python

create_virtualenv:
	mkdir -p env
	virtualenv -p $(PYTHON) env
