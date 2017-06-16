# 2017 problems

* ssd error on laptop
* paint mode not complete enough
* many mistakes where unset sticky devattrs would just use last-set
  value and the effect would look different later
* putting in 8 flashes of the same lights and same note tint color
  takes a huge amount of work. Add-momentary might have helped but it
  did nothing
* rdfdb file watcher breaks a lot and drops files. emacs
  focus-autosave may have made this worse. No workaround less than
  restarting rdfdb then all its dependents
  * the dependents ought to resync without a restart
  * rdfdb should have a UI showing loaded files and any parse errors
* bug in timeline loading note tint colors
* given a multicolor static effect, I'd like a way to quickly animate
  it by rotating hues, chase, blink, etc
* output fps is not great, many fades are bumpy
* effectsequencer gets behind running graph patches at 100ms
  each. They should be coalesced by rdfdb so ES never gets behind
* can't edit an existing effect in /live because it's not reading and
  writing rdf data like KC and /timeline do. /live should edit an
  unnamed-or-named effect just like other tools. Rename /live to
  effectedit
* ballyhoo light moves look lumpy- lights seem to speed up and slow
  down
* chrome stalls on page loads sometimes with 'resolving host', but the
  host is in /etc/hosts and there's no route to another DNS
* would be nice to be able to preview audio in the booth, maybe on a
  different asco screen so I don't accidentally play the next stage
  song in the booth #nomodes
* computer times might be 100ms off, and i don't know how to sync them
  without internet
* show had 2-3 cases where it would be nice to have a follow spot do a
  programmed move
* get a keyboard/trackpad combo for the 2ary box- fitting a normal
  mouse on the table is hard
* asco doesn't autoreconnect (nor does much else), and this means i
  can't do wall-mounted tablets backstage
* rdfdb shows tons of http11clientfactory stopping, which probably
  isn't great. move to zmq or grpc or fix the http to keepalive
  better. maybe i'm sending more concurrent requests than i have
  connections in my pool? patch coalescing should help that.
* besides being low frame rate, manual fades on KC kind of crash into
  black. they could probably use a better transfer function somewhere
  in the pipeline, maybe in the effect
* near the end of 2nd show, enttec dmx seemed to just stop
  outputting. stats shows no more writes happening. dmesg says
  nothing. restarted collector and it's counting writes again. no idea
  how that got jammed.

New timeline layout:

A separate web page per song. 'Follow song' means go to the right page
when song changes (but you could press browser-back to go back).

When starting up, zoom the time to fit the song (current one doesn't do this).

Timeline includes vidref playback. Maybe it slides along with time
cursor so bystanders can obviously tell if we're going forward or
back. Or just put annotations on the video to show how it's moving.

Perhaps use a row of timeline to show thumbs of the dance, for finding
sections even faster.


# New elements:

## light9-effect-scale (for use in KC and timeline attrs)

*  effect name
*  big or normal colorvalue slider. Light up on non-zero
   values. Support KC mouse bindings.
*  value number
*  optional hue/sat widget
*  optional editable effect uri
 
## light9-device-settings (for effectedit)

*  device and class
*  each attr row has a 'set' checkbox. Editing anything sets
   everything, but you can unset them.
*  whole widget has a 'clear' which zeros and unsets all
*  rows are color-picker; slider; choice
*  it would be nice to be able to set rx, ry, zoom on a little stage
   widget
*  a settings element is selectable. on hover, all affected attrs
   light up as a hint. If they're offscreen, show a '5 more...'
   overlay on hover

## effect editor

*  one editor with an editable-resource choice. save null as new
   effect; edit existing; page has a session name, which could almost
   be automatic except it might be hard to rejoin your last anonymous
   session
*  easy to pick groups or classes of lights to edit, maybe with
   hotkeys ('show just quantums')
*  some lights should default to hidden or last
*  allow multiselect
*  copy from one dev to another(s). copy just one attr?
*  line up devices in spreadsheet rows or cols to more easily see
   which attrs are different
*  when editing a slider, show hints of what other devs are set to,
   and maybe even snap to those values
*  this is a 'settings' editor. how does it deal with effect code?
*  it would be nice to take 1 note in a song and quickly fork its
   effect for a custom edit, or even express overrides somehow
  
## light9-color-picker

*  try only waking on drag (not hover), but the big rainbow is offset
   so your drag starts at the current value
*  skew the gradient even more towards desaturated colors. Currently,
   the lower half is almost all the same effect

## timeline

*  need to see autostop
*  snap to autostop and to other curve points and to markers
*  hotkeys to add markers
*  note attrs box should let you swap the effect but not unlink/rename
   it
*  progressive reveal of UI as note grows: first, effect. then add
   note controls, then add l9-effect-scale
*  fade adjusters are very useful, but just grabbing the fade line
   should be enough. But don't let dragging the whole note move the
   origin, since that's way too easy to hit accidentally
*  pack the rows down to the fewest required; don't waste 6 rows of
   space all the time
*  more note operations:
  *    copy note, paste it repeatedly at multiple markers
  *    split note (to clear out a section for another effect, or to
       more easily say 'note ends here')
  *    adjust fade about its center
  *    animate scale at more points
  *    add more curves, like for rx,ry to do a follow spot
*  take a few note effects and combine them into a new effect, like
   you would in KC

## timeline internals

*  syncedgraph -> diagram values -> diagram screen layout
*  DV is just all the value() calls precomputed and maintained across
   patches, for performance
*  DSL is the positions of everything, after zooming, after adjuster
   creation and layout
*  inner-attrs probably don't need anything special, since we can
   always

## KC rewrite

*  drop qwerty controls
*  the row that is mapped to hardware sliders needs to stick over
   restarts (and work when no browser is open, too)
*  have effectsequencer run the effects; don't do it in the KC process
   (which wasn't reloading right anyway)


## effects

*  need more easy to use random primitives, or maybe i just always
   forget about noise()
*  given some settings, have easy canned effects to add: chase, blink,
   hue rotate, offset lights (maybe just during fade-in)

## effectsequencer

*  drop sticky attributes for lights that are on- they lead to errors
   with unset values. Ok to be sticky when the light is off, but if it
   turns on with a setting at 0, you have to go to 0. Also, ES needs
   to look aheead at coming notes and plan how values change before
   the light is turned on


## collector

*  drop the remap system and do it as a UI thing instead, where slider
   ranges are remapped on screen but you can see their ranges are
   adjusted. Then we don't need other translations later. I'm not sure
   if this will make trouble once we can copy rx,ry values between
   devices and they're not aligned. But if it does, do the remap at
   paste time.
  
