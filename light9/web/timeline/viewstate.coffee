class window.ViewState
  constructor: () ->
    # caller updates all these observables
    @zoomSpec =
      duration: ko.observable(100) # current song duration
      t1: ko.observable(0)
      t2: ko.observable(100)
    @cursor =
      t: ko.observable(20) # songTime
    @mouse =
      pos: ko.observable($V([0,0]))
    @width = ko.observable(500)
    @coveredByDiagramTop = ko.observable(0) # page coords
    # all these are relative to #coveredByDiagram:
    @audioY = ko.observable(0)
    @audioH = ko.observable(0)
    @zoomedTimeY = ko.observable(0)
    @zoomedTimeH = ko.observable(0)
    @rowsY = ko.observable(0)
      
    @fullZoomX = d3.scaleLinear()
    @zoomInX = d3.scaleLinear()

    @zoomAnimSec = .1

    ko.computed(@maintainZoomLimitsAndScales.bind(@))
 
  setWidth: (w) ->
    @width(w)
    @maintainZoomLimitsAndScales() # before other handlers run
    
  maintainZoomLimitsAndScales: () ->
    log('maintainZoomLimitsAndScales')
    # not for cursor updates

    if @zoomSpec.t1() < 0
      @zoomSpec.t1(0)
    if @zoomSpec.duration() and @zoomSpec.t2() > @zoomSpec.duration()
      @zoomSpec.t2(@zoomSpec.duration())

    @fullZoomX.domain([0, @zoomSpec.duration()])
    @fullZoomX.range([0, @width()])

    @zoomInX.domain([@zoomSpec.t1(), @zoomSpec.t2()])
    @zoomInX.range([0, @width()])
    
  latestMouseTime: ->
    @zoomInX.invert(@mouse.pos().e(1))

  onMouseWheel: (deltaY) ->
    zs = @zoomSpec

    center = @latestMouseTime()
    left = center - zs.t1()
    right = zs.t2() - center
    scale = Math.pow(1.005, deltaY)

    zs.t1(center - left * scale)
    zs.t2(center + right * scale)
    log('view to', ko.toJSON(@))

  frameCursor: ->
    zs = @zoomSpec
    visSeconds = zs.t2() - zs.t1()
    margin = visSeconds * .4
    # buggy: really needs t1/t2 to limit their ranges
    if @cursor.t() < zs.t1() or @cursor.t() > zs.t2() - visSeconds * .6
      newCenter = @cursor.t() + margin
      @animatedZoom(newCenter - visSeconds / 2,
                    newCenter + visSeconds / 2, @zoomAnimSec)
  frameToEnd: ->
    @animatedZoom(@cursor.t() - 2, @zoomSpec.duration(), @zoomAnimSec)
  frameAll: ->
    @animatedZoom(0, @zoomSpec.duration(), @zoomAnimSec)
  animatedZoom: (newT1, newT2, secs) ->
    fps = 30
    oldT1 = @zoomSpec.t1()
    oldT2 = @zoomSpec.t2()
    lastTime = 0
    for step in [0..secs * fps]
      frac = step / (secs * fps)
      do (frac) =>
        gotoStep = =>
          @zoomSpec.t1((1 - frac) * oldT1 + frac * newT1)
          @zoomSpec.t2((1 - frac) * oldT2 + frac * newT2)
        delay = frac * secs * 1000
        setTimeout(gotoStep, delay)
        lastTime = delay
    setTimeout(=>
      @zoomSpec.t1(newT1)
      @zoomSpec.t2(newT2)
    , lastTime + 10)
