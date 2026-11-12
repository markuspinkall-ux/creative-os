extends Node
## Creative Engine – Spiel-Laufzeit (Godot 4).
## Liest res://game.json und spielt den Ablauf: Splash → Startbildschirm → Level … (Timeline aus dem Editor).

const Assets = preload("res://assets.gd")
const LevelScript = preload("res://level.gd")
const BubbleScript = preload("res://bubble.gd")

var game: Dictionary = {}
var flow: Array = []
var step := -1
var current: Node = null
var args := {}
var screenshot_path := ""
var score := 0


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--") and "=" in a:
			var kv := a.substr(2).split("=", true, 1)
			args[kv[0]] = kv[1]
		elif a.begins_with("--"):
			args[a.substr(2)] = "1"
	setup_input()
	var text := FileAccess.get_file_as_string("res://game.json")
	var parsed = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("game.json fehlt oder ist kaputt")
		get_tree().quit(1)
		return
	game = parsed
	flow = game.get("flow", [])
	var settings: Dictionary = game.get("settings", {})
	if settings.get("fullscreen", false) and not args.has("fenster"):
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
	DisplayServer.window_set_title(String(game.get("name", "Spiel")))
	if args.has("screenshot"):
		screenshot_path = args["screenshot"]
		get_tree().create_timer(float(args.get("nach", "2.5"))).timeout.connect(_take_screenshot)
	if args.has("level"):
		for i in flow.size():
			if flow[i].get("id", "") == args["level"]:
				show_step(i)
				return
	show_step(0)


func setup_input() -> void:
	var actions := {
		"links": [KEY_LEFT, KEY_A], "rechts": [KEY_RIGHT, KEY_D],
		"springen": [KEY_SPACE, KEY_UP, KEY_W], "pause": [KEY_ESCAPE, KEY_P],
		"weiter": [KEY_ENTER, KEY_KP_ENTER, KEY_SPACE],
	}
	for action in actions:
		if not InputMap.has_action(action):
			InputMap.add_action(action, 0.25)
		for key in actions[action]:
			var ev := InputEventKey.new()
			ev.physical_keycode = key
			InputMap.action_add_event(action, ev)
	var pad := {"links": JOY_BUTTON_DPAD_LEFT, "rechts": JOY_BUTTON_DPAD_RIGHT, "springen": JOY_BUTTON_A,
		"pause": JOY_BUTTON_START, "weiter": JOY_BUTTON_A}
	for action in pad:
		var jb := InputEventJoypadButton.new()
		jb.button_index = pad[action]
		InputMap.action_add_event(action, jb)
	for pair in [["links", -1.0], ["rechts", 1.0]]:
		var jm := InputEventJoypadMotion.new()
		jm.axis = JOY_AXIS_LEFT_X
		jm.axis_value = pair[1]
		InputMap.action_add_event(pair[0], jm)


func _take_screenshot() -> void:
	var img := get_viewport().get_texture().get_image()
	img.save_png(screenshot_path)
	print("Bildschirmfoto: ", screenshot_path)
	get_tree().quit()


func clear() -> void:
	if current:
		current.queue_free()
		current = null


func show_step(i: int) -> void:
	clear()
	if i < 0 or i >= flow.size():
		show_finish()
		return
	step = i
	var s: Dictionary = flow[i]
	match String(s.get("type", "")):
		"splash":
			current = make_splash(s)
		"menu":
			current = make_menu(s)
		"text":
			current = make_text(s)
		"seite":
			current = make_page(s)
		"level":
			current = make_level(s)
		_:
			call_deferred("next_step")
			return
	add_child(current)


func next_step() -> void:
	show_step(step + 1)


func goto_first_level() -> void:
	for i in range(step + 1, flow.size()):
		if flow[i].get("type", "") == "level":
			score = 0
			show_step(i)
			return
	next_step()


func goto_menu() -> void:
	for i in flow.size():
		if flow[i].get("type", "") == "menu":
			show_step(i)
			return
	show_step(0)


# ---- Bildschirme ---------------------------------------------------------------------------
func full_rect(node: Control) -> void:
	node.set_anchors_preset(Control.PRESET_FULL_RECT)


## Hintergrund: Farbe, Bild und/oder Video im Vollbild. Gibt den Video-Player zurück (oder null).
func background(layer: Control, s: Dictionary) -> VideoStreamPlayer:
	var bg := ColorRect.new()
	bg.color = Color(String(s.get("bg", "#000000")))
	full_rect(bg)
	layer.add_child(bg)
	var cover := String(s.get("bgFit", "cover")) == "cover"
	var image := String(s.get("bgImage", ""))
	if image != "":
		var m := Assets.media(image, cover)
		if m:
			full_rect(m)
			layer.add_child(m)
	var video := String(s.get("bgVideo", ""))
	if video != "":
		var v := Assets.media(video, cover, bool(s.get("videoLoop", false)), float(s.get("videoVolume", 0.0)),
			float(s.get("bgRatio", 16.0 / 9.0)))
		if v:
			full_rect(v)
			layer.add_child(v)
			return v.get_meta("video")
	return null


## Bild- oder Video-Element einer Seite/eines Menüs
func media_element(e: Dictionary) -> Control:
	var rel := String(e.get("video", e.get("image", "")))
	var m := Assets.media(rel, String(e.get("fit", "contain")) == "cover", bool(e.get("loop", false)),
		float(e.get("volume", 0.0)), float(e.get("ratio", 16.0 / 9.0)))
	if m == null:
		m = Control.new()
	return m


func make_label(text: String, size: int, color: String) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", Color(color))
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return l


class Skippable extends Control:
	signal skipped
	func _gui_input(event: InputEvent) -> void:
		if event is InputEventMouseButton and event.pressed:
			skipped.emit()
	func _unhandled_input(event: InputEvent) -> void:
		if event.is_action_pressed("weiter") or event.is_action_pressed("pause"):
			skipped.emit()


func make_splash(s: Dictionary) -> Node:
	var root := CanvasLayer.new()
	var box := Skippable.new()
	full_rect(box)
	root.add_child(box)
	var player := background(box, s)
	var center := VBoxContainer.new()
	center.alignment = BoxContainer.ALIGNMENT_CENTER
	full_rect(center)
	box.add_child(center)
	var logo := String(s.get("logo", ""))
	if logo != "":
		var tex := Assets.texture(logo)
		if tex:
			var tr := TextureRect.new()
			tr.texture = tex
			tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
			tr.custom_minimum_size = Vector2(0, 720 * float(s.get("logoSize", 0.35)))
			center.add_child(tr)
	var text := String(s.get("text", ""))
	if text != "":
		center.add_child(make_label(text, int(s.get("textSize", 28)), String(s.get("textColor", "#ffffff"))))
	box.modulate.a = 0.0
	var fade := float(s.get("fade", 0.6))
	var tw := box.create_tween()
	tw.tween_property(box, "modulate:a", 1.0, fade)
	if player and s.get("untilVideoEnd", false):
		player.finished.connect(_skip_splash.bind(box), CONNECT_ONE_SHOT)
		box.set_meta("tween", tw)
		box.skipped.connect(_skip_splash.bind(box))
		return root
	tw.tween_interval(max(0.2, float(s.get("duration", 2.5))))
	tw.tween_property(box, "modulate:a", 0.0, fade)
	tw.tween_callback(next_step)
	box.set_meta("tween", tw)
	box.skipped.connect(_skip_splash.bind(box))
	return root


func _skip_splash(box: Control) -> void:
	var tw: Tween = box.get_meta("tween")
	if tw and tw.is_valid():
		tw.kill()
	next_step()


func make_text(s: Dictionary, done: Callable = Callable()) -> Node:
	if not done.is_valid():
		done = next_step
	var root := CanvasLayer.new()
	var box := Skippable.new()
	full_rect(box)
	root.add_child(box)
	background(box, s)
	var l := make_label(String(s.get("text", "")), int(s.get("textSize", 34)), String(s.get("textColor", "#ffffff")))
	full_rect(l)
	l.offset_left = 120
	l.offset_right = -120
	box.add_child(l)
	var hint := make_label("Weiter mit Leertaste oder Klick", 16, String(s.get("textColor", "#ffffff")))
	hint.modulate.a = 0.6
	hint.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	hint.position.y -= 50
	box.add_child(hint)
	box.skipped.connect(done, CONNECT_ONE_SHOT)
	var dur := float(s.get("duration", 0))
	if dur > 0:
		get_tree().create_timer(dur).timeout.connect(_timed.bind(box, done))
	return root


## Freie Seite (Bild/Comic): Hintergrund, Texte, Bilder und Sprechblasen, die nacheinander erscheinen können.
## Weiter nach „duration“ Sekunden oder (bei 0) per Taste/Klick.
func make_page(s: Dictionary) -> Node:
	var root := CanvasLayer.new()
	var box := Skippable.new()
	full_rect(box)
	root.add_child(box)
	var player := background(box, s)
	var size := Vector2(1280, 720)
	var last := 0.0
	for e in s.get("elements", []):
		var kind := String(e.get("kind", ""))
		var rect := Rect2(float(e.get("x", 0.5)) * size.x, float(e.get("y", 0.5)) * size.y,
			float(e.get("w", 0.3)) * size.x, float(e.get("h", 0.1)) * size.y)
		rect.position -= rect.size / 2.0
		var node: Control
		if kind == "bubble":
			var b = BubbleScript.new()
			b.setup(String(e.get("text", "")), int(e.get("size", 30)), Color(String(e.get("color", "#ffffff"))),
				Color(String(e.get("textColor", "#1c2433"))), String(e.get("tail", "unten-links")),
				String(e.get("speaker", "")))
			node = b
		elif kind in ["image", "video"]:
			node = media_element(e)
			if kind == "video" and player == null and node.has_meta("video"):
				player = node.get_meta("video")
		else:
			var l := make_label(String(e.get("text", "")), int(e.get("size", 48)), String(e.get("color", "#ffffff")))
			if e.get("bold", false):
				l.add_theme_constant_override("outline_size", 2)
				l.add_theme_color_override("font_outline_color", Color(String(e.get("color", "#ffffff"))))
			node = l
		node.mouse_filter = Control.MOUSE_FILTER_IGNORE
		node.position = rect.position
		node.size = rect.size
		box.add_child(node)
		var delay := float(e.get("after", 0.0))
		last = maxf(last, delay)
		if delay > 0.0:
			node.modulate.a = 0.0
			var tw := node.create_tween()
			tw.tween_interval(delay)
			tw.tween_property(node, "modulate:a", 1.0, 0.25)
	var dur := float(s.get("duration", 0))
	if player and s.get("untilVideoEnd", false):
		player.finished.connect(_timed.bind(box, next_step), CONNECT_ONE_SHOT)
		dur = -1.0
	if dur == 0.0:
		var hint := make_label("Weiter mit Leertaste oder Klick", 16, "#ffffff")
		hint.modulate.a = 0.55
		hint.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
		hint.position.y -= 40
		box.add_child(hint)
	box.skipped.connect(next_step, CONNECT_ONE_SHOT)
	if dur > 0.0:
		get_tree().create_timer(maxf(dur, last + 0.3)).timeout.connect(_timed.bind(box, next_step))
	return root


func _timed(box: Control, done: Callable) -> void:
	if is_instance_valid(box) and box.is_inside_tree():
		done.call()


func button_style(color: String, radius: int) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(color)
	sb.set_corner_radius_all(radius)
	sb.content_margin_left = 16
	sb.content_margin_right = 16
	return sb


func make_menu(s: Dictionary) -> Node:
	var root := CanvasLayer.new()
	var box := Control.new()
	full_rect(box)
	root.add_child(box)
	background(box, s)
	var size := Vector2(1280, 720)
	var first: Button = null
	for e in s.get("elements", []):
		var kind := String(e.get("kind", ""))
		var rect := Rect2(float(e.get("x", 0.5)) * size.x, float(e.get("y", 0.5)) * size.y,
			float(e.get("w", 0.3)) * size.x, float(e.get("h", 0.1)) * size.y)
		rect.position -= rect.size / 2.0
		var node: Control
		if kind == "button":
			var b := Button.new()
			b.text = String(e.get("text", "Knopf"))
			b.add_theme_font_size_override("font_size", int(e.get("size", 28)))
			var col := String(e.get("color", "#8fb3ff"))
			var tc := String(e.get("textColor", "#12151b"))
			var r := int(e.get("radius", 14))
			b.add_theme_stylebox_override("normal", button_style(col, r))
			b.add_theme_stylebox_override("hover", button_style(Color(col).lightened(0.15).to_html(), r))
			b.add_theme_stylebox_override("pressed", button_style(Color(col).darkened(0.15).to_html(), r))
			var focus := button_style(Color(col).lightened(0.15).to_html(), r)
			focus.border_color = Color(tc)
			focus.set_border_width_all(3)
			b.add_theme_stylebox_override("focus", focus)
			for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color"]:
				b.add_theme_color_override(state, Color(tc))
			var action := String(e.get("action", "start"))
			b.pressed.connect(menu_action.bind(action))
			node = b
			if first == null:
				first = b
		elif kind in ["image", "video"]:
			node = media_element(e)
		else:
			var l := make_label(String(e.get("text", "")), int(e.get("size", 48)), String(e.get("color", "#ffffff")))
			if e.get("bold", false):
				l.add_theme_constant_override("outline_size", 2)
				l.add_theme_color_override("font_outline_color", Color(String(e.get("color", "#ffffff"))))
			node = l
		node.position = rect.position
		node.size = rect.size
		box.add_child(node)
	if first:
		first.call_deferred("grab_focus")
	return root


func menu_action(action: String) -> void:
	match action:
		"start":
			goto_first_level()
		"quit":
			get_tree().quit()
		"next":
			next_step()
		_:
			if action.begins_with("goto:"):
				var target := action.substr(5)
				for i in flow.size():
					if flow[i].get("id", "") == target:
						show_step(i)
						return
			goto_first_level()


func make_level(s: Dictionary) -> Node:
	var levels: Dictionary = game.get("levels", {})
	var data: Dictionary = levels.get(String(s.get("id", "")), {})
	var lvl := Node3D.new()
	lvl.set_script(LevelScript)
	lvl.setup(data, game, score, args.has("autotest"))
	lvl.finished.connect(_level_done)
	lvl.game_over.connect(show_game_over)
	lvl.to_menu.connect(goto_menu)
	return lvl


func _level_done(points: int) -> void:
	score = points
	if args.has("autotest"):
		print("AUTOTEST: Level geschafft, Münzen ", points)
	call_deferred("next_step")


func show_game_over() -> void:
	clear()
	current = make_text({"text": "Game Over", "textSize": 72, "bg": "#12151b", "textColor": "#ff8a8e", "duration": 3},
		goto_menu)
	add_child(current)


func show_finish() -> void:
	clear()
	current = make_text({"text": "Geschafft!\n%d Münzen" % score, "textSize": 64, "bg": "#12151b",
		"textColor": "#6fdcc0"}, goto_menu)
	add_child(current)
