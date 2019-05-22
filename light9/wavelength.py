#!/usr/bin/python


import sys, wave

def wavelength(filename):
    filename = filename.replace('.ogg', '.wav')
    wavefile = wave.open(filename, 'rb')

    framerate = wavefile.getframerate() # frames / second
    nframes = wavefile.getnframes() # number of frames
    song_length = nframes / framerate

    return song_length

if __name__ == "__main__":
    for songfile in sys.argv[1:]:
        print(songfile, wavelength(songfile))
