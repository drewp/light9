NOSEARGS="--no-path-adjustment light9.rdfdb.rdflibpatch light9.rdfdb.patch"

tests:
	eval env/bin/nosetests -x $(NOSEARGS)

tests_watch:
	eval env/bin/nosetests --with-watch $(NOSEARGS)


install_python_deps:
	env/bin/pip install -r pydeps

PYTHON=/usr/bin/pypy
PYTHON=/usr/bin/python

create_virtualenv:
	mkdir -p env
	virtualenv -p $(PYTHON) env
