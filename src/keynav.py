"""Walking the lists with the keyboard. Pure: the window only forwards key codes and draws the highlight.

Up/Down move through the rows of the zone you are in (the sidebar or the page), Left/Right change zone,
Return opens the highlighted row."""

UP, DOWN, LEFT, RIGHT, RETURN, ENTER = 126, 125, 123, 124, 36, 76
ZONES = ("side", "main")


def move(ids, current, code):
    """The row id after pressing Up or Down. Nothing highlighted yet: Down takes the first, Up the last."""
    if not ids or code not in (UP, DOWN):
        return current if current in ids else None
    if current not in ids:
        return ids[0] if code == DOWN else ids[-1]
    i = ids.index(current) + (1 if code == DOWN else -1)
    return ids[max(0, min(len(ids) - 1, i))]


def zone_after(zone, code, rows):
    """Left goes to the sidebar, Right to the page; a zone with no rows is not entered."""
    want = {LEFT: "side", RIGHT: "main"}.get(code)
    return want if want and rows.get(want) else zone


def press(state, rows, code):
    """One key. `state` is {"zone", "id"}, `rows` is {zone: [(id, callback)]}. Returns (new state, callback or None)."""
    zone, cur = state["zone"], state["id"]
    if code in (LEFT, RIGHT):
        new = zone_after(zone, code, rows)
        return ({"zone": new, "id": None if new != zone else cur}, None)
    ids = [r[0] for r in rows.get(zone, [])]
    if code in (UP, DOWN):
        if not ids:
            other = "main" if zone == "side" else "side"
            if rows.get(other):
                zone, ids = other, [r[0] for r in rows[other]]
        return ({"zone": zone, "id": move(ids, cur, code)}, None)
    if code in (RETURN, ENTER) and cur in ids:
        return (state, dict(rows[zone])[cur])
    return (state, None)
