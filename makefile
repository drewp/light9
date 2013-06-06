NOSEARGS="--no-path-adjustment light9.rdfdb.rdflibpatch light9.rdfdb.patch"

tests:
	eval env/bin/nosetests -x $(NOSEARGS)

tests_watch:
	eval env/bin/nosetests --with-watch $(NOSEARGS)


# needed packages: python-gtk2 python-imaging

install_python_deps: link_to_sys_packages
	env/bin/pip install -r pydeps

DP=/usr/lib/python2.7/dist-packages
SP=env/lib/python2.7/site-packages

link_to_sys_packages:
	# http://stackoverflow.com/questions/249283/virtualenv-on-ubuntu-with-no-site-packages
	ln -sf $(DP)/glib $(SP)/
	ln -sf $(DP)/gobject $(SP)/
	ln -sf $(DP)/cairo $(SP)/
	ln -sf $(DP)/gtk-2.0 $(SP)/
	ln -sf $(DP)/pygtk.py $(SP)/
	ln -sf $(DP)/pygtk.pth $(SP)/
	ln -sf $(DP)/pygst.pth $(SP)/
	ln -sf $(DP)/pygst.py $(SP)/
	ln -sf $(DP)/gst-0.10 $(SP)/
	ln -sf $(DP)/PIL $(SP)/
	ln -sf $(DP)/PIL.pth $(SP)/

PYTHON=/usr/bin/pypy
PYTHON=/usr/bin/python

create_virtualenv:
	mkdir -p env
	virtualenv -p $(PYTHON) env
	ln -sf ../env/bin/python bin/python

tkdnd_build:
	# get tkdnd r95 with subversion
	# then apply tkdnd-patch-on-r95 to that
	cd tkdnd/trunk
	./configure
	make
