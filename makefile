### setup ###

packages:
	sudo aptitude install coffeescript normalize-audio audacity python3-pygame libffi-dev tix libzmq3-dev python3-dev libssl-dev python3-opencv python3-cairo npm git virtualenv python3-virtualenv nginx-full python3-tk zlib1g-dev libjpeg8-dev curl

# also pip3 install -U invoke (don't use ubuntu's version)

gst_packages:
	sudo aptitude install python3-gi gir1.2-gst-plugins-base-1.0 libgirepository-1.0-1 gir1.2-gstreamer-1.0 gstreamer1.0-tools gstreamer1.0-plugins-good gstreamer1.0-pulseaudio python3-gst-1.0 gir1.2-goocanvas-2.0

PYTHON=/usr/bin/python3

create_virtualenv:
	mkdir -p env
	virtualenv -p $(PYTHON) env
	env/bin/pip install -U pip
	ln -sf ../env/bin/python bin/python

install_python_deps:
	env/bin/pip install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -U -r requirements.txt

binexec:
	chmod a+x bin/*


node_modules/bower/bin/bower:
	npm install

bin/node:
	ln -sf `which nodejs` bin/node

bower: node_modules/bower/bin/bower bin/node
	cd light9/web/lib; nodejs ../../../node_modules/bower/bin/bower install

npm_install:
	npm install

node_modules/n3/n3-browser.js:
	(cd node_modules/n3; nodejs ../browserify/bin/cmd.js --standalone N3 --require n3 -o n3-browser.js)

light9/web/lib/debug/debug-build.js:
	node_modules/browserify/bin/cmd.js light9/web/lib/debug/src/browser.js -o light9/web/lib/debug/debug-build.js --standalone debug

light9/web/lib/debug/debug-build-es6.js:
	node_modules/browserify/bin/cmd.js light9/web/lib/debug/src/browser.js -o light9/web/lib/debug/debug-build-es6.js --standalone debug
	echo "\nexport default window.debug;" >> light9/web/lib/debug/debug-build-es6.js

lit_fix:
	perl -pi -e "s,'lit-html,'/node_modules/lit-html,; s,lit-html',lit-html/lit-html.js'," node_modules/lit-element/lit-element.js

round_fix:
	perl -pi -e 's/module.exports = rounding/export { rounding }/' node_modules/significant-rounding/index.js

light9/web/lib/underscore/underscore-min-es6.js:
	cp light9/web/lib/underscore/underscore-min.js light9/web/lib/underscore/underscore-min-es6.js
	perl -pi -e 's/call\(this\);/call(window); export default window._;/' light9/web/lib/underscore/underscore-min-es6.js

npm: npm_install node_modules/n3/n3-browser.js light9/web/lib/debug/debug-build.js light9/web/lib/debug/debug-build-es6.js lit_fix round_fix light9/web/lib/underscore/underscore-min-es6.js


bin/ascoltami2: gst_packages link_to_sys_packages

effect_node_setup: create_virtualenv packages binexec install_python_deps

tkdnd_build:
	# get tkdnd r95 with subversion
	# then apply tkdnd-patch-on-r95 to that
	cd tkdnd/trunk
	./configure
	make

### build ###

coffee:
	zsh -c 'cd light9/web; ../../node_modules/coffeescript/bin/coffee --map -cw {.,live,timeline,paint,effects}/*.coffee'

mypy:
	inv mypy

reformat:
	inv reformat

### show ###

darcs_show_checkpoint:
	darcs add --quiet --recursive ${LIGHT9_SHOW} 
	darcs rec -a -m "checkpoint show data" ${LIGHT9_SHOW}

### pi setup ###

raspberry_pi_packages:
	sudo apt-get install python3-picamera python3-dev python3-twisted python3-virtualenv

raspberry_pi_virtualenv:
	mkdir -p env_pi
	virtualenv -p /usr/bin/python3 --system-site-packages env_pi
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
	node_modules/coffeescript/bin/coffee -c light9/web/*.coffee
	node_modules/mocha/bin/mocha --compilers coffee:coffee-script/register --globals window,N3 light9/web/graph_test.coffee

test_js_watch:
	# have coffee continuously running
	watch -c node_modules/mocha/bin/mocha --compilers coffee:coffee-script/register --globals window,N3 light9/web/graph_test.coffee --colors

profile_seq:
	echo in lib, get https://github.com/uber/pyflame.git and https://github.com/brendangregg/FlameGraph.git
	sudo lib/pyflame/src/pyflame  -s 10 -p `pgrep -f effectsequencer` | perl -lpe 's,/home/drewp/projects-local/light9/,,g; s,env/local/lib/python2.7/site-packages/,,g;' | lib/FlameGraph/flamegraph.pl --width 2500 > /tmp/fl.svg
