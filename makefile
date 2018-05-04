### setup ###

packages:
	sudo aptitude install coffeescript normalize-audio audacity python-pygame libffi-dev tix libzmq3-dev python-dev libssl-dev python-opencv python-cairo npm git python-virtualenv nginx-full python-tk

gst_packages:
	sudo aptitude install python-gi gir1.2-gst-plugins-base-1.0 libgirepository-1.0-1 gir1.2-gstreamer-1.0 gstreamer1.0-tools gstreamer1.0-plugins-good gstreamer1.0-pulseaudio python-gst-1.0 python-pygoocanvas gir1.2-goocanvas-2.0

PYTHON=/usr/bin/pypy
PYTHON=/usr/bin/python

create_virtualenv:
	mkdir -p env
	virtualenv -p $(PYTHON) env
	env/bin/pip install -U pip
	ln -sf ../env/bin/python bin/python


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

binexec:
	chmod a+x bin/*


node_modules/bower/bin/bower:
	npm install

bin/node:
	ln -sf `which nodejs` bin/node

bower: node_modules/bower/bin/bower bin/node
	cd light9/web/lib; nodejs ../../../node_modules/bower/bin/bower install

npm:
	npm install
	cd node_modules/n3; nodejs ../browserify/bin/cmd.js --standalone N3 --require n3 -o n3-browser.js

bin/ascoltami2: gst_packages link_to_sys_packages

effect_node_setup: create_virtualenv packages binexec install_python_deps

tkdnd_build:
	# get tkdnd r95 with subversion
	# then apply tkdnd-patch-on-r95 to that
	cd tkdnd/trunk
	./configure
	make

env-mypy/bin/mypy:
	mkdir -p env-mypy
	virtualenv -p /usr/bin/python3  env-mypy/
	env-mypy/bin/pip install mypy==0.590 lxml==4.2.1

### build ###

coffee:
	zsh -c 'coffee --map -cw light9/web/{.,live,timeline,paint,effects}/*.coffee'

mypy-collector: env-mypy/bin/mypy
	env-mypy/bin/mypy --py2 --ignore-missing-imports --strict-optional --custom-typeshed-dir stubs --html-report /tmp/rep bin/collector light9/collector/*.py

mypy-paint: env-mypy/bin/mypy
	env-mypy/bin/mypy --py2 --ignore-missing-imports --strict-optional --custom-typeshed-dir stubs --html-report /tmp/rep light9/paint/*.py

### show ###

darcs_show_checkpoint:
	darcs add --quiet --recursive ${LIGHT9_SHOW} 
	darcs rec -a -m "checkpoint show data" ${LIGHT9_SHOW}

### pi setup ###

raspberry_pi_packages:
	sudo apt-get install python-picamera python-dev python-twisted python-virtualenv

raspberry_pi_virtualenv:
	mkdir -p env_pi
	virtualenv --system-site-packages env_pi
	env_pi/bin/pip install cyclone 'coloredlogs==6.0'

### arduino build ###

/usr/share/arduino/Arduino.mk:
	sudo aptitude install arduino-mk

arduino_upload: /usr/share/arduino/Arduino.mk
	cd rgbled
	make upload

### testing ###

NOSEARGS="--no-path-adjustment light9.rdfdb.rdflibpatch light9.rdfdb.patch light9.effecteval.test_effect light9.collector light9.rdfdb.graphfile_test light9.paint light9.effect"

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
