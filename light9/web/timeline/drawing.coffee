
window.Drawing = {}
  
window.Drawing.svgPathFromPoints = (pts) ->
  out = ''
  pts.forEach (p) ->
    p = p.elements if p.elements # for vec2
    if out.length == 0
      out = 'M '
    else
      out += 'L '
    out += '' + p[0] + ',' + p[1] + ' '
    return
  out

window.Drawing.line = (ctx, p1, p2) ->
  ctx.moveTo(p1.e(1), p1.e(2))
  ctx.lineTo(p2.e(1), p2.e(2))

# http://stackoverflow.com/a/4959890
window.Drawing.roundRect = (ctx, sx,sy,ex,ey,r) ->
    d2r = Math.PI/180
    r = ( ( ex - sx ) / 2 ) if ( ex - sx ) - ( 2 * r ) < 0 # ensure that the radius isn't too large for x
    r = ( ( ey - sy ) / 2 ) if ( ey - sy ) - ( 2 * r ) < 0 # ensure that the radius isn't too large for y
    ctx.beginPath();
    ctx.moveTo(sx+r,sy);
    ctx.lineTo(ex-r,sy);
    ctx.arc(ex-r,sy+r,r,d2r*270,d2r*360,false);
    ctx.lineTo(ex,ey-r);
    ctx.arc(ex-r,ey-r,r,d2r*0,d2r*90,false);
    ctx.lineTo(sx+r,ey);
    ctx.arc(sx+r,ey-r,r,d2r*90,d2r*180,false);
    ctx.lineTo(sx,sy+r);
    ctx.arc(sx+r,sy+r,r,d2r*180,d2r*270,false);
    ctx.closePath();
