
class window.BrickLayout
  constructor: (@viewState, @numRows) ->
    @noteRow = {} # uristr: row, t0, t1, onRowChange
    
  addNote: (n, onRowChange) ->
    @noteRow[n.uri.value] = {row: 0, t0: 0, t1: 0, onRowChange: onRowChange}
    
  setNoteSpan: (n, t0, t1) ->
    @noteRow[n.uri.value].t0 = t0
    @noteRow[n.uri.value].t1 = t1
    @_recompute()
    
  delNote: (n) ->
    delete @noteRow[n.uri.value]
    @_recompute()
    
  _recompute: ->
    for u, row of @noteRow
      row.prev = row.row
      row.row = null
    overlap = (a, b) -> a.t0 < b.t1 and a.t1 > b.t0

    notesByWidth = _.sortBy(
      ({dur: row.t1 - row.t0 + row.t0 * .0001, uri: u} for u, row of @noteRow),
      'dur')
    notesByWidth.reverse()

    for n in notesByWidth
      blockedRows = new Set()
      for u, other of @noteRow
        if other.row != null
          if overlap(other, @noteRow[n.uri])
            blockedRows.add(other.row)

      for r in [0 ... @numRows]
        if not blockedRows.has(r)
          @noteRow[n.uri].row = r
          break
      if @noteRow[n.uri].row == null
        log("warning: couldn't place #{n.uri}")
        @noteRow[n.uri].row = 0
      if @noteRow[n.uri].row != @noteRow[n.uri].prev
        @noteRow[n.uri].onRowChange()
          
  rowBottom: (row) -> @viewState.rowsY() + 20 + 150 * row + 140
  
  yForVFor: (n) ->
    row = @noteRow[n.uri.value].row
    rowBottom = @rowBottom(row)
    rowTop = rowBottom - 140
    (v) => rowBottom + (rowTop - rowBottom) * v      
