extends Control
## Sprechblase: abgerundete Fläche mit Spitze, optional Name des Sprechers, Text darin.
## Spitze: unten-links, unten-mitte, unten-rechts, oben-links, oben-rechts, keine.

const TAIL := 22.0
const PAD := 14.0

var tail := "unten-links"
var fill := Color.WHITE
var line_color := Color(0.07, 0.08, 0.1)
var text_color := Color(0.07, 0.08, 0.1)
var label: Label
var name_label: Label
var hint: Label
var font_size := 26


func setup(text: String, size_px: int, fill_c: Color, text_c: Color, tail_kind: String, speaker := "",
		show_hint := false) -> void:
	fill = fill_c
	text_color = text_c
	line_color = text_c.darkened(0.2) if text_c.get_luminance() < 0.5 else fill_c.darkened(0.55)
	tail = tail_kind
	font_size = size_px
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	if speaker != "":
		name_label = Label.new()
		name_label.text = speaker
		name_label.add_theme_font_size_override("font_size", maxi(12, int(size_px * 0.62)))
		name_label.add_theme_color_override("font_color", text_c.lerp(fill_c, 0.35))
		add_child(name_label)
	label = Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", size_px)
	label.add_theme_color_override("font_color", text_c)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(label)
	if show_hint:
		hint = Label.new()
		hint.text = "▶"
		hint.add_theme_font_size_override("font_size", maxi(12, int(size_px * 0.6)))
		hint.add_theme_color_override("font_color", text_c.lerp(fill_c, 0.3))
		add_child(hint)
	resized.connect(_layout)
	_layout()


func _notification(what: int) -> void:
	# Größe wird oft gesetzt, bevor die Blase im Baum hängt – dann hier nachziehen
	if what == NOTIFICATION_RESIZED or what == NOTIFICATION_READY:
		_layout()


## Größe passend zum Text (für Blasen im Level)
func fit(max_width: float) -> void:
	var font := label.get_theme_font("font")
	var inner := max_width - PAD * 2
	var s := font.get_multiline_string_size(label.text, HORIZONTAL_ALIGNMENT_CENTER, inner, font_size)
	var extra := font_size * 0.9 if hint else 0.0
	var w := minf(max_width, maxf(s.x + PAD * 2 + 8 + extra, 120.0))
	var h := s.y + PAD * 2 + (TAIL if tail != "keine" else 0.0)
	if name_label:
		h += name_label.get_theme_font_size("font_size") + 4
	size = Vector2(w, h)
	_layout()


func body_rect() -> Rect2:
	var r := Rect2(Vector2.ZERO, size)
	if tail.begins_with("unten"):
		r.size.y -= TAIL
	elif tail.begins_with("oben"):
		r.position.y += TAIL
		r.size.y -= TAIL
	return r


## Wo die Spitze hinzeigt (relativ zur Blase) – damit sie über dem Sprecher sitzt
func tip() -> Vector2:
	var r := body_rect()
	var x := r.position.x + r.size.x * _tail_x()
	if tail.begins_with("oben"):
		return Vector2(x - 6, 0)
	return Vector2(x - 6, size.y)


func _tail_x() -> float:
	if tail.ends_with("links"):
		return 0.22
	if tail.ends_with("rechts"):
		return 0.78
	return 0.5


func _layout() -> void:
	if label == null:
		return
	var r := body_rect().grow(-PAD)
	if name_label:
		var nh := float(name_label.get_theme_font_size("font_size")) + 4
		name_label.position = r.position + Vector2(0, -6)
		name_label.size = Vector2(r.size.x, nh)
		r.position.y += nh - 4
		r.size.y -= nh - 4
	if hint:
		r.size.x -= font_size * 0.9
		hint.position = Vector2(body_rect().end.x - PAD - font_size * 0.6, body_rect().end.y - PAD - font_size * 0.85)
	label.position = r.position
	label.size = r.size
	queue_redraw()


func _draw() -> void:
	var r := body_rect()
	var sb := StyleBoxFlat.new()
	sb.bg_color = fill
	sb.border_color = line_color
	sb.set_border_width_all(3)
	sb.set_corner_radius_all(int(minf(26.0, r.size.y * 0.45)))
	sb.anti_aliasing = true
	sb.shadow_color = Color(0, 0, 0, 0.18)
	sb.shadow_size = 6
	sb.shadow_offset = Vector2(0, 3)
	draw_style_box(sb, r)
	if tail == "keine":
		return
	var x := r.position.x + r.size.x * _tail_x()
	var a: Vector2
	var b: Vector2
	var t: Vector2
	if tail.begins_with("oben"):
		a = Vector2(x - 14, r.position.y + 2)
		b = Vector2(x + 14, r.position.y + 2)
		t = Vector2(x - 6, 0)
	else:
		a = Vector2(x - 14, r.end.y - 2)
		b = Vector2(x + 14, r.end.y - 2)
		t = Vector2(x - 6, size.y)
	draw_colored_polygon(PackedVector2Array([a, b, t]), fill)
	draw_line(a, t, line_color, 3.0, true)
	draw_line(b, t, line_color, 3.0, true)
