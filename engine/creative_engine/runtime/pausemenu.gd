extends Control
## Pausenmenü für alle Spiele der Engine – im Editor einstellbar (settings.pause):
##   title, position (mitte/links/rechts), panel (Farbe), accent, text, shade (Abdunkeln 0–1),
##   size (Schriftgröße der Knöpfe), image (eigenes Hintergrundbild der Tafel),
##   buttons: {weiter, neustart, steuerung, menu} (an/aus), labels: eigene Beschriftungen.
## Sitzt immer richtig: füllt den Bildschirm, die Tafel wird per Container ausgerichtet.

signal chosen(action: String)

const Assets = preload("res://assets.gd")
const DEFAULTS := {"title": "Pause", "position": "mitte", "panel": "#161a22", "accent": "#8fb3ff",
	"text": "#e8ecf4", "shade": 0.55, "size": 24, "image": "", "width": 360,
	"buttons": {"weiter": true, "neustart": true, "steuerung": true, "menu": true},
	"labels": {"weiter": "Weiter", "neustart": "Level neu starten", "steuerung": "Steuerung", "menu": "Hauptmenü"}}
const ORDER := ["weiter", "neustart", "steuerung", "menu"]

var cfg := {}
var shade: ColorRect
var box: VBoxContainer
var help: Label
var buttons: Array = []


static func config(game: Dictionary) -> Dictionary:
	var own: Dictionary = game.get("settings", {}).get("pause", {})
	var c := DEFAULTS.duplicate(true)
	for k in own:
		if k in ["buttons", "labels"]:
			for b in own[k]:
				c[k][b] = own[k][b]
		else:
			c[k] = own[k]
	return c


func setup(game: Dictionary, controls_text: String) -> void:
	cfg = config(game)
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	process_mode = Node.PROCESS_MODE_ALWAYS
	visible = false
	shade = ColorRect.new()
	shade.color = Color(0, 0, 0, clampf(float(cfg["shade"]), 0.0, 1.0))
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(shade)
	# Ausrichtung: ganze Fläche mit Rand, darin links/mittig/rechts
	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 48)
	add_child(margin)
	var row := HBoxContainer.new()
	row.alignment = {"links": BoxContainer.ALIGNMENT_BEGIN, "rechts": BoxContainer.ALIGNMENT_END}.get(
		String(cfg["position"]), BoxContainer.ALIGNMENT_CENTER)
	margin.add_child(row)
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.size_flags_vertical = Control.SIZE_EXPAND_FILL
	var column := VBoxContainer.new()
	column.alignment = BoxContainer.ALIGNMENT_CENTER
	column.size_flags_vertical = Control.SIZE_EXPAND_FILL
	row.add_child(column)
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(float(cfg["width"]), 0)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(String(cfg["panel"]), 0.94)
	sb.border_color = Color(String(cfg["accent"]), 0.35)
	sb.set_border_width_all(1)
	sb.set_corner_radius_all(22)
	sb.set_content_margin_all(28)
	sb.shadow_color = Color(0, 0, 0, 0.35)
	sb.shadow_size = 18
	var tex := Assets.texture(String(cfg["image"]))
	if tex:
		var st := StyleBoxTexture.new()
		st.texture = tex
		var edge := minf(32.0, minf(tex.get_width(), tex.get_height()) / 3.0)
		st.set_texture_margin_all(edge)          # 9-teilig: Ecken bleiben scharf
		st.set_content_margin_all(28)
		panel.add_theme_stylebox_override("panel", st)
	else:
		panel.add_theme_stylebox_override("panel", sb)
	column.add_child(panel)
	box = VBoxContainer.new()
	box.add_theme_constant_override("separation", 12)
	panel.add_child(box)
	var title := Label.new()
	title.text = String(cfg["title"])
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", int(cfg["size"]) * 2)
	title.add_theme_color_override("font_color", Color(String(cfg["text"])))
	box.add_child(title)
	var accent := Color(String(cfg["accent"]))
	for key in ORDER:
		if not cfg["buttons"].get(key, true):
			continue
		var b := Button.new()
		b.text = String(cfg["labels"].get(key, ""))
		if b.text.strip_edges() == "":
			b.text = String(DEFAULTS["labels"][key])
		b.custom_minimum_size = Vector2(0, int(cfg["size"]) * 2.3)
		b.add_theme_font_size_override("font_size", int(cfg["size"]))
		b.add_theme_color_override("font_color", Color(String(cfg["text"])))
		b.add_theme_color_override("font_focus_color", Color("#12151b"))
		b.add_theme_color_override("font_hover_color", Color("#12151b"))
		var normal := StyleBoxFlat.new()
		normal.bg_color = Color(1, 1, 1, 0.06)
		normal.set_corner_radius_all(14)
		var hover := normal.duplicate() as StyleBoxFlat
		hover.bg_color = accent
		b.add_theme_stylebox_override("normal", normal)
		b.add_theme_stylebox_override("hover", hover)
		b.add_theme_stylebox_override("focus", hover)
		b.add_theme_stylebox_override("pressed", hover)
		b.pressed.connect(_press.bind(key))
		box.add_child(b)
		buttons.append(b)
	help = Label.new()
	help.text = controls_text
	help.visible = false
	help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	help.add_theme_font_size_override("font_size", maxi(14, int(cfg["size"]) - 8))
	help.add_theme_color_override("font_color", Color(String(cfg["text"]), 0.8))
	box.add_child(help)


func _press(key: String) -> void:
	if key == "steuerung":
		help.visible = not help.visible
		return
	chosen.emit({"weiter": "resume", "neustart": "restart", "menu": "menu"}.get(key, key))


func open() -> void:
	# immer die ganze Bildfläche abdecken, auch nach Fenstergrößen-Änderungen
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	size = get_viewport_rect().size
	visible = true
	help.visible = false
	if not buttons.is_empty():
		(buttons[0] as Button).grab_focus()


func close() -> void:
	visible = false


static func controls_summary(game: Dictionary) -> String:
	## Kurzübersicht der Tasten aus der Steuerung des Spiels
	var names := {"links": "Links", "rechts": "Rechts", "springen": "Springen", "schub": "Schneller",
		"bremse": "Bremsen", "boost": "Boost", "feuer": "Feuern", "waffe_weiter": "Waffe wechseln",
		"landen": "Landen/Starten", "looping": "Looping", "fassrolle_links": "Rolle links",
		"fassrolle_rechts": "Rolle rechts", "pause": "Pause"}
	var lines := PackedStringArray()
	var c: Dictionary = game.get("controls", {})
	for action in names:
		if c.has(action):
			var keys: Array = c[action].get("keys", [])
			var pads: Array = c[action].get("pad", [])
			var part := " / ".join(PackedStringArray(keys))
			if not pads.is_empty():
				part += "  ·  Controller " + " / ".join(PackedStringArray(pads))
			lines.append("%s: %s" % [names[action], part])
	return "\n".join(lines)
