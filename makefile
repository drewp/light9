NOSEARGS="--no-path-adjustment light9.rdfdb.rdflibpatch light9.rdfdb.patch light9.effecteval.test_effect"

tests:
	eval env/bin/nosetests -x $(NOSEARGS)

tests_watch:
	eval env/bin/nosetests --with-watcher $(NOSEARGS)


# needed packages: python-gtk2 python-imaging

install_python_deps: link_to_sys_packages
	env/bin/pip install -r pydeps

DP=/usr/lib/python2.7/dist-packages
SP=env/lib/python2.7/site-packages

link_to_sys_packages:
	# http://stackoverflow.com/questions/249283/virtualenv-on-ubuntu-with-no-site-packages
	ln -sf $(DP)/glib $(SP)/
	ln -sf $(DP)/gi $(SP)/
	ln -sf $(DP)/gobject $(SP)/
	ln -sf $(DP)/cairo $(SP)/
	ln -sf $(DP)/gtk-2.0 $(SP)/
	ln -sf $(DP)/pygtk.py $(SP)/
	ln -sf $(DP)/pygtk.pth $(SP)/
	ln -sf $(DP)/pygst.pth $(SP)/
	ln -sf $(DP)/pygst.py $(SP)/
	ln -sf $(DP)/gst-0.10 $(SP)/
	ln -sf $(DP)/goocanvasmodule.so $(SP)/

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

bin/ascoltami2: gst_packages link_to_sys_packages

gst_packages:
	sudo aptitude install python-gi gir1.2-gst-plugins-base-1.0 libgirepository-1.0-1 gir1.2-gstreamer-1.0 gstreamer1.0-tools gstreamer1.0-plugins-good gstreamer1.0-pulseaudio gir1.2-goocanvas-2.0-9

packages:
	sudo aptitude install coffeescript freemind normalize-audio audacity python-pygoocanvas python-pygame

raspberry_pi_virtualenv:
	mkdir -p env_pi
	virtualenv --system-site-packages env_pi

raspberry_pi_packages:
	sudo apt-get install python-picamera python-twisted 
	env_pi/bin/pip install cyclone coloredlogs
