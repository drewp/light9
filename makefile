NOSEARGS="--no-path-adjustment light9.rdfdb.rdflibpatch light9.rdfdb.patch light9.effecteval.test_effect light9.collector light9.rdfdb.graphfile_test"

tests:
	eval env/bin/nosetests -x $(NOSEARGS)

tests_watch:
	eval env/bin/nosetests --with-watcher $(NOSEARGS)


tests_coverage:
	eval env/bin/nosetests --with-coverage --cover-erase --cover-html --cover-html-dir=/tmp/light9-cov/  --cover-package=light9 --cover-branches $(NOSEARGS)

test_js_init:
	npm install

test_js:
	coffee -c light9/web/*.coffee
	node_modules/mocha/bin/mocha --compilers coffee:coffee-script/register --globals window,N3 light9/web/graph_test.coffee

test_js_watch:
	# have coffee continuously running
	watch -c node_modules/mocha/bin/mocha --compilers coffee:coffee-script/register --globals window,N3 light9/web/graph_test.coffee --colors

# needed packages: python-gtk2 python-imaging

binexec:
	chmod a+x bin/*

install_python_deps: link_to_sys_packages
	env/bin/pip install twisted
	env/bin/pip install -U -r requirements.txt

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
	ln -sf $(DP)/cv2.x86_64-linux-gnu.so $(SP)/
	ln -sf $(DP)/cv.py $(SP)/
	ln -sf $(DP)/numpy $(SP)/

PYTHON=/usr/bin/pypy
PYTHON=/usr/bin/python

create_virtualenv:
	mkdir -p env
	virtualenv -p $(PYTHON) env
	env/bin/pip install -U pip
	ln -sf ../env/bin/python bin/python

tkdnd_build:
	# get tkdnd r95 with subversion
	# then apply tkdnd-patch-on-r95 to that
	cd tkdnd/trunk
	./configure
	make

bin/ascoltami2: gst_packages link_to_sys_packages

gst_packages:
	sudo aptitude install python-gi gir1.2-gst-plugins-base-1.0 libgirepository-1.0-1 gir1.2-gstreamer-1.0 gstreamer1.0-tools gstreamer1.0-plugins-good gstreamer1.0-pulseaudio python-gst0.10 python-gst-1.0

packages:
	sudo aptitude install coffeescript freemind normalize-audio audacity python-pygoocanvas python-pygame gir1.2-goocanvas-2.0-9 libffi-dev tix libzmq3 python-dev libssl-dev python-opencv

bower:
	cd light9/web/lib; bower install
	cd light9/web/lib/N3.js; npm install; npm run browser
	cd light9/web/lib/d3; npm install

raspberry_pi_virtualenv:
	mkdir -p env_pi
	virtualenv --system-site-packages env_pi

raspberry_pi_packages:
	sudo apt-get install python-picamera python-dev python-twisted python-virtualenv
	env_pi/bin/pip install cyclone 'coloredlogs==1.0.1'

darcs_show_checkpoint:
	darcs add --quiet --recursive ${LIGHT9_SHOW} 
	darcs rec -a -m "checkpoint show data" ${LIGHT9_SHOW}

/usr/share/arduino/Arduino.mk:
	sudo aptitude install arduino-mk

arduino_upload: /usr/share/arduino/Arduino.mk
	cd rgbled
	make upload

effect_node_setup: create_virtualenv packages binexec install_python_deps

coffee:
	zsh -c 'coffee -cw light9/web/{.,live,timeline}/*.coffee'
