build/patch.n3: patch-source.n3 patch-rules.n3
	  cwm patch-source.n3 --filter=patch-rules.n3 --n3=/ > build/patch.n3

# this only to help the 2012 tools work
config.n3: dmxchannels.n3 networking.n3 build/patch.n3 playlist.n3
	cat dmxchannels.n3 networking.n3 build/patch.n3 playlist.n3 > config.n3
