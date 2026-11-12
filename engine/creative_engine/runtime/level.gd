extends Node3D
## Ein Jump'n'Run-Level (2,5D): Blöcke, Münzen, Gegner, Stacheln, Ziel, NPCs und 3D-Kulisse.
## Gebaut aus den Level-Daten des Editors; Kamera seitlich fest.

signal finished(points: int)
signal game_over
signal to_menu

const Assets = preload("res://assets.gd")
const PlayerScript = preload("res://player.gd")
const EnemyScript = preload("res://enemy.gd")
const BubbleScript = preload("res://bubble.gd")

const TILE_COLORS := {
	"gras": Color("#7a5a3a"), "erde": Color("#7a5a3a"), "stein": Color("#8a93a3"), "ziegel": Color("#b0603f"),
	"holz": Color("#a8794a"), "eis": Color("#bfe6ff"), "metall": Color("#6c7686"), "wolke": Color("#f4f7ff"),
}
const DEPTH := 3.0

var data := {}
var game := {}
var points := 0
var lives := 3
var autotest := false
var player: CharacterBody3D
var camera: Camera3D
var spawn := Vector3(2, 2, 0)
var hud: Label
var pause_panel: Control
var done := false
var width := 60
var height := 20
var materials := {}
var autotest_time := 0.0
var bubble_layer: CanvasLayer
var dialog := {}            # laufendes Gespräch (siehe start_dialog)
var bubble = null         # Sprechblase (bubble.gd)
var hud_coins: Label
var hud_lives: Label
var hearts: HBoxContainer
var life_bar: Range
var max_lives := 3
var lives_style := "herzen"
var heart_full := ""
var heart_empty := ""


func setup(level_data: Dictionary, game_data: Dictionary, start_points: int, test: bool) -> void:
	data = level_data
	game = game_data
	points = start_points
	autotest = test
	lives = int(game.get("player", {}).get("lives", 3))
	width = int(data.get("width", 60))
	height = int(data.get("height", 20))


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	build_environment()
	build_tiles()
	for e in data.get("entities", []):
		build_entity(e)
	for d in data.get("decor", []):
		build_decor(d)
	build_player()
	build_camera()
	build_hud()
	update_hud()


func mat(color: Color, rough := 0.85) -> StandardMaterial3D:
	var key := color.to_html() + str(rough)
	if materials.has(key):
		return materials[key]
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = rough
	materials[key] = m
	return m


# ---- Umgebung ------------------------------------------------------------------------------
func build_environment() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(String(data.get("sky", "#8ec5ff")))
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(1, 1, 1)
	env.ambient_light_energy = 0.35
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	if data.get("fog", false):
		env.fog_enabled = true
		env.fog_light_color = env.background_color
		env.fog_density = 0.01
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, -30, 0)
	sun.light_energy = 0.85
	sun.shadow_enabled = true
	add_child(sun)
	# Weiter Boden hinter dem Level (Horizont)
	var floor_color := String(data.get("ground", ""))
	if floor_color != "":
		var plane := MeshInstance3D.new()
		var pm := PlaneMesh.new()
		pm.size = Vector2(width + 200, 112)
		plane.mesh = pm
		plane.position = Vector3(width / 2.0, -0.5, -59)
		plane.material_override = mat(Color(floor_color), 1.0)
		add_child(plane)


# ---- Blöcke --------------------------------------------------------------------------------
func tile_at(x: int, y: int) -> String:
	return String(data.get("tiles", {}).get("%d,%d" % [x, y], ""))


func build_tiles() -> void:
	var tiles: Dictionary = data.get("tiles", {})
	var rows := {}
	for key in tiles:
		var p := String(key).split(",")
		var x := int(p[0])
		var y := int(p[1])
		if not rows.has(y):
			rows[y] = []
		rows[y].append(x)
	var body := StaticBody3D.new()
	add_child(body)
	for y in rows:
		var xs: Array = rows[y]
		xs.sort()
		var start: int = xs[0]
		var prev: int = xs[0]
		for i in range(1, xs.size() + 1):
			var x: int = xs[i] if i < xs.size() else -99999
			if x != prev + 1:
				add_collision_run(body, start, prev, y)
				start = x
			prev = x
		for x in xs:
			add_tile_mesh(x, y, tile_at(x, y))


func add_collision_run(body: StaticBody3D, x0: int, x1: int, y: int) -> void:
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(x1 - x0 + 1, 1, DEPTH)
	shape.shape = box
	shape.position = Vector3((x0 + x1) / 2.0 + 0.5, y + 0.5, 0)
	body.add_child(shape)


func add_tile_mesh(x: int, y: int, kind: String) -> void:
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(1, 1, DEPTH)
	mi.mesh = bm
	mi.position = Vector3(x + 0.5, y + 0.5, 0)
	var rough := 0.2 if kind == "eis" or kind == "metall" else 0.85
	mi.material_override = mat(TILE_COLORS.get(kind, Color("#8a93a3")), rough)
	add_child(mi)
	# Gras: grüne Decke, wenn darüber frei ist
	if (kind == "gras") and tile_at(x, y + 1) == "":
		var top := MeshInstance3D.new()
		var tm := BoxMesh.new()
		tm.size = Vector3(1.02, 0.28, DEPTH + 0.04)
		top.mesh = tm
		top.position = Vector3(x + 0.5, y + 0.88, 0)
		top.material_override = mat(Color("#5fb04a"))
		add_child(top)
	if kind == "ziegel":
		for row in 2:
			var line := MeshInstance3D.new()
			var lm := BoxMesh.new()
			lm.size = Vector3(1.01, 0.05, DEPTH + 0.02)
			line.mesh = lm
			line.position = Vector3(x + 0.5, y + 0.33 + row * 0.33, 0)
			line.material_override = mat(Color("#7e4027"))
			add_child(line)


# ---- Objekte -------------------------------------------------------------------------------
func pos_of(e: Dictionary) -> Vector3:
	return Vector3(float(e.get("x", 0)) + 0.5, float(e.get("y", 0)), 0)


func build_entity(e: Dictionary) -> void:
	var kind := String(e.get("kind", ""))
	var p := pos_of(e)
	match kind:
		"start":
			spawn = p + Vector3(0, 0.1, 0)
		"coin":
			add_coin(p + Vector3(0, 0.5, 0))
		"enemy":
			add_enemy(e, p)
		"spike":
			add_spike(p)
		"goal":
			add_goal(p)
		"checkpoint":
			add_checkpoint(p)
		"npc":
			add_npc(e, p)
		"spring":
			add_spring(p)


func area_box(size: Vector3, position_: Vector3) -> Area3D:
	var a := Area3D.new()
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = size
	cs.shape = bs
	a.add_child(cs)
	a.position = position_
	add_child(a)
	return a


func add_coin(p: Vector3) -> void:
	var a := area_box(Vector3(0.7, 0.7, 2), p)
	var mi := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 0.32
	cm.bottom_radius = 0.32
	cm.height = 0.08
	mi.mesh = cm
	mi.rotation_degrees = Vector3(90, 0, 0)
	var m := StandardMaterial3D.new()
	m.albedo_color = Color("#ffd24a")
	m.metallic = 0.7
	m.roughness = 0.3
	m.emission_enabled = true
	m.emission = Color("#ffb300")
	m.emission_energy_multiplier = 0.25
	mi.material_override = m
	var spin := Node3D.new()
	spin.add_child(mi)
	a.add_child(spin)
	a.set_meta("spin", spin)
	a.body_entered.connect(_coin_hit.bind(a))
	a.add_to_group("coins")


func _coin_hit(body: Node, coin: Area3D) -> void:
	if body == player and is_instance_valid(coin) and not coin.has_meta("taken"):
		coin.set_meta("taken", true)
		points += 1
		update_hud()
		var tw := create_tween()
		tw.tween_property(coin, "position:y", coin.position.y + 1.2, 0.25)
		tw.parallel().tween_property(coin, "scale", Vector3.ONE * 0.1, 0.25)
		tw.tween_callback(coin.queue_free)


func add_enemy(e: Dictionary, p: Vector3) -> void:
	var en := CharacterBody3D.new()
	en.set_script(EnemyScript)
	en.position = p + Vector3(0, 0.05, 0)
	en.patrol_range = float(e.get("range", 3))
	en.speed = float(e.get("speed", 2.0))
	en.max_hp = maxi(1, int(e.get("hp", 1)))
	en.hp = en.max_hp
	add_child(en)
	en.build(String(e.get("model", "")))
	en.build_bar()


func add_spike(p: Vector3) -> void:
	var a := area_box(Vector3(0.8, 0.5, 2), p + Vector3(0, 0.25, 0))
	for i in 3:
		var mi := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = 0.0
		cm.bottom_radius = 0.16
		cm.height = 0.55
		mi.mesh = cm
		mi.position = Vector3(-0.3 + i * 0.3, 0.03, 0)
		mi.material_override = mat(Color("#c9d1de"), 0.25)
		a.add_child(mi)
	a.body_entered.connect(_hurt_area)


func _hurt_area(body: Node) -> void:
	if body == player:
		hurt(true)


func add_goal(p: Vector3) -> void:
	var a := area_box(Vector3(1.2, 4, 2), p + Vector3(0, 2, 0))
	var pole := MeshInstance3D.new()
	var pm := CylinderMesh.new()
	pm.top_radius = 0.06
	pm.bottom_radius = 0.06
	pm.height = 4
	pole.mesh = pm
	pole.material_override = mat(Color("#dce6ff"), 0.4)
	a.add_child(pole)
	var flag := MeshInstance3D.new()
	var fm := BoxMesh.new()
	fm.size = Vector3(1.0, 0.65, 0.05)
	flag.mesh = fm
	flag.position = Vector3(0.52, 1.55, 0)
	flag.material_override = mat(Color("#6fdcc0"))
	a.add_child(flag)
	a.body_entered.connect(_goal_hit)


func _goal_hit(body: Node) -> void:
	if body == player and not done:
		done = true
		player.celebrate()
		var tw := create_tween()
		tw.tween_interval(1.6)
		tw.tween_callback(func_emit_finished)


func func_emit_finished() -> void:
	finished.emit(points)


func add_checkpoint(p: Vector3) -> void:
	var a := area_box(Vector3(1, 3, 2), p + Vector3(0, 1.5, 0))
	var post := MeshInstance3D.new()
	var pm := CylinderMesh.new()
	pm.top_radius = 0.05
	pm.bottom_radius = 0.05
	pm.height = 1.6
	post.mesh = pm
	post.position = Vector3(0, -0.7, 0)
	post.material_override = mat(Color("#c9d1de"))
	a.add_child(post)
	var lamp := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = 0.2
	sm.height = 0.4
	lamp.mesh = sm
	lamp.position = Vector3(0, 0.2, 0)
	lamp.material_override = mat(Color("#ff8a8e"))
	a.add_child(lamp)
	a.body_entered.connect(_checkpoint_hit.bind(p, lamp))


func _checkpoint_hit(body: Node, p: Vector3, lamp: MeshInstance3D) -> void:
	if body == player:
		spawn = p + Vector3(0, 0.1, 0)
		lamp.material_override = mat(Color("#6fdcc0"))


func add_spring(p: Vector3) -> void:
	var a := area_box(Vector3(0.9, 0.4, 2), p + Vector3(0, 0.2, 0))
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(0.9, 0.3, 1.2)
	mi.mesh = bm
	mi.material_override = mat(Color("#ff8a8e"), 0.4)
	a.add_child(mi)
	a.body_entered.connect(_spring_hit)


func _spring_hit(body: Node) -> void:
	if body == player:
		player.velocity.y = player.jump_speed * 1.6


func add_npc(e: Dictionary, p: Vector3) -> void:
	var holder := Node3D.new()
	holder.position = p
	add_child(holder)
	var model := Assets.fitted(String(e.get("model", "")), float(e.get("height", 1.7)))
	if model:
		holder.add_child(model)
		var anim := Assets.find_animator(model)
		var idle := Assets.pick_animation(anim, ["idle", "stand", "wait"])
		if idle != "":
			Assets.set_loop(anim, idle, true)
			anim.play(idle)
	else:
		var mi := MeshInstance3D.new()
		var cm := CapsuleMesh.new()
		cm.radius = 0.35
		cm.height = 1.6
		mi.mesh = cm
		mi.position = Vector3(0, 0.8, 0)
		mi.material_override = mat(Color("#c3a6ff"))
		holder.add_child(mi)
	var info := {
		"lines": npc_lines(e), "mode": String(e.get("mode", "gespraech")),
		"secs": float(e.get("seconds", 3.0)), "once": bool(e.get("once", true)), "done": false,
		"anchor": holder, "top": float(e.get("height", 1.7)) + 0.35, "name": String(e.get("name", "")),
	}
	if info["lines"].is_empty():
		return
	var a := area_box(Vector3(4, 3, 2), p + Vector3(0, 1.5, 0))
	a.body_entered.connect(_npc_near.bind(info, true))
	a.body_exited.connect(_npc_near.bind(info, false))


## Dialogzeilen eines NPCs: [{"who": "npc"|"spieler", "text": …}] (alte Projekte: nur "text")
func npc_lines(e: Dictionary) -> Array:
	var lines: Array = []
	for l in e.get("dialog", []):
		if String(l.get("text", "")).strip_edges() != "":
			lines.append(l)
	if lines.is_empty() and String(e.get("text", "")).strip_edges() != "":
		lines.append({"who": "npc", "text": String(e.get("text", ""))})
	return lines


func _npc_near(body: Node, info: Dictionary, entered: bool) -> void:
	if body != player or done:
		return
	if entered:
		if dialog.is_empty() and not (info["once"] and info["done"]):
			start_dialog(info)
	elif dialog == info and info["mode"] != "gespraech":
		end_dialog()


# ---- Sprechblasen-Dialoge --------------------------------------------------------------------
func start_dialog(info: Dictionary) -> void:
	dialog = info
	dialog["index"] = 0
	dialog["time"] = 0.0
	if info["mode"] == "gespraech":
		player.frozen = true
	show_line()


func show_line() -> void:
	if bubble:
		bubble.queue_free()
		bubble = null
	var line: Dictionary = dialog["lines"][dialog["index"]]
	var by_player := String(line.get("who", "npc")) == "spieler"
	var npc_x: float = (dialog["anchor"] as Node3D).global_position.x
	# Spitze zeigt zum Sprecher, Blase ragt zur Mitte zwischen beiden
	var speaker_left := (player.global_position.x < npc_x) == by_player
	var b = BubbleScript.new()
	var speaker := ""
	if not by_player:
		speaker = String(dialog["name"])
	var ui: Dictionary = game.get("settings", {}).get("ui", {})
	b.skin = Assets.texture(String(ui.get("bubble", "")))
	b.skin_margin = int(ui.get("bubbleMargin", 24))
	b.setup(String(line.get("text", "")), 24, Color("#ffffff"), Color(String(ui.get("bubbleText", "#1c2433"))),
		"unten-links" if speaker_left else "unten-rechts", speaker, dialog["mode"] == "gespraech")
	b.fit(440)
	bubble_layer.add_child(b)
	bubble = b
	bubble.set_meta("player", by_player)
	dialog["time"] = 0.0
	position_bubble()


func position_bubble() -> void:
	if bubble == null or dialog.is_empty():
		return
	var world: Vector3
	if bubble.get_meta("player"):
		world = player.global_position + Vector3(0, float(game.get("player", {}).get("height", 1.6)) + 0.35, 0)
	else:
		world = (dialog["anchor"] as Node3D).global_position + Vector3(0, float(dialog["top"]), 0)
	var screen := camera.unproject_position(world)
	var pos: Vector2 = screen - bubble.tip()
	var view := get_viewport().get_visible_rect().size
	pos.x = clampf(pos.x, 8, view.x - bubble.size.x - 8)
	pos.y = clampf(pos.y, 70, view.y - bubble.size.y - 8)
	bubble.position = pos


func next_line() -> void:
	if dialog.is_empty():
		return
	dialog["index"] += 1
	if dialog["index"] >= dialog["lines"].size():
		end_dialog()
	else:
		show_line()


func end_dialog() -> void:
	if bubble:
		bubble.queue_free()
		bubble = null
	if dialog.is_empty():
		return
	dialog["done"] = true
	var talk: bool = dialog["mode"] == "gespraech"
	dialog = {}
	if talk:
		# kurz warten, damit der letzte Tastendruck nicht gleich springen lässt
		get_tree().create_timer(0.2).timeout.connect(_release_player)


func _release_player() -> void:
	if not done and dialog.is_empty():
		player.frozen = false


func build_decor(d: Dictionary) -> void:
	var holder := Assets.fitted(String(d.get("model", "")), float(d.get("height", 3.0)))
	if holder == null:
		return
	holder.position = Vector3(float(d.get("x", 0)) + 0.5, float(d.get("y", 0)), float(d.get("z", -4)))
	holder.rotation_degrees.y = float(d.get("rot", 0))
	add_child(holder)
	var anim := Assets.find_animator(holder)
	var anim_name := Assets.pick_animation(anim, ["idle", "loop", ""])
	if anim_name != "":
		anim.play(anim_name)


# ---- Spieler, Kamera, Anzeige ----------------------------------------------------------------
func build_player() -> void:
	player = CharacterBody3D.new()
	player.set_script(PlayerScript)
	var cfg: Dictionary = game.get("player", {})
	player.run_speed = float(cfg.get("speed", 7.0))
	player.jump_speed = float(cfg.get("jump", 12.0))
	player.position = spawn
	add_child(player)
	player.build(String(cfg.get("model", "")), float(cfg.get("height", 1.6)))
	player.attacks = cfg.get("attacks", [])
	player.attacked.connect(_player_attack)
	player.stomped.connect(_stomped)
	player.hit.connect(func_hit_enemy)
	player.autotest = autotest


## Angriff der Spielfigur: trifft Gegner vor ihr in Reichweite (kurz verzögert, passend zur Bewegung)
func _player_attack(attack: Dictionary) -> void:
	await get_tree().create_timer(float(attack.get("delay", 0.12))).timeout
	if done or not is_instance_valid(player):
		return
	var reach := float(attack.get("range", 1.5))
	var dmg := maxi(1, int(attack.get("damage", 1)))
	var hit_any := false
	for en in get_tree().get_nodes_in_group("enemies"):
		if en.dead:
			continue
		var dx: float = (en.global_position.x - player.global_position.x) * player.facing
		var dy: float = absf(en.global_position.y - player.global_position.y)
		if dx > -0.4 and dx < reach + 0.4 and dy < 1.4:
			en.take_hit(dmg, player.global_position.x)
			hit_any = true
	if hit_any:
		update_hud()


func _stomped(_enemy: Node) -> void:
	update_hud()


func func_hit_enemy() -> void:
	hurt(false)


func build_camera() -> void:
	camera = Camera3D.new()
	camera.fov = 40
	camera.current = true
	add_child(camera)
	camera.position = player.position + Vector3(0, 2.2, 17)
	camera.look_at(player.position + Vector3(0, 1.2, 0))


func build_hud() -> void:
	var ui: Dictionary = game.get("settings", {}).get("ui", {})
	var layer := CanvasLayer.new()
	add_child(layer)
	var panel := PanelContainer.new()
	var skin := Assets.texture(String(ui.get("panel", "")))
	if skin:
		var st := StyleBoxTexture.new()
		st.texture = skin
		var m := float(ui.get("panelMargin", 16))
		st.texture_margin_left = m
		st.texture_margin_right = m
		st.texture_margin_top = m
		st.texture_margin_bottom = m
		st.content_margin_left = m + 4
		st.content_margin_right = m + 4
		st.content_margin_top = m * 0.6
		st.content_margin_bottom = m * 0.6
		panel.add_theme_stylebox_override("panel", st)
	else:
		var sb := StyleBoxFlat.new()
		sb.bg_color = Color(0.07, 0.08, 0.1, 0.55)
		sb.set_corner_radius_all(14)
		sb.content_margin_left = 16
		sb.content_margin_right = 16
		sb.content_margin_top = 8
		sb.content_margin_bottom = 8
		panel.add_theme_stylebox_override("panel", sb)
	panel.position = Vector2(20, 18)
	layer.add_child(panel)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	panel.add_child(row)
	hud = Label.new()
	hud.add_theme_font_size_override("font_size", 24)
	row.add_child(hud)
	row.add_child(hud_icon(String(ui.get("coin", "")), "●", Color("#ffd24a")))
	hud_coins = Label.new()
	hud_coins.add_theme_font_size_override("font_size", 24)
	row.add_child(hud_coins)
	max_lives = maxi(1, lives)
	lives_style = String(ui.get("lives", "herzen"))
	if lives_style == "herzen" and max_lives > 12:
		lives_style = "zahl"
	if lives_style == "balken":
		var fill := Assets.texture(String(ui.get("barFill", "")))
		if fill:
			var tp := TextureProgressBar.new()
			tp.texture_progress = fill
			var under := Assets.texture(String(ui.get("barBack", "")))
			if under:
				tp.texture_under = under
			tp.nine_patch_stretch = true
			var m2 := int(ui.get("barMargin", 6))
			tp.stretch_margin_left = m2
			tp.stretch_margin_right = m2
			tp.stretch_margin_top = m2
			tp.stretch_margin_bottom = m2
			tp.custom_minimum_size = Vector2(200, 26)
			life_bar = tp
		else:
			var pb := ProgressBar.new()
			pb.show_percentage = false
			pb.custom_minimum_size = Vector2(200, 18)
			var bg := StyleBoxFlat.new()
			bg.bg_color = Color(0, 0, 0, 0.45)
			bg.set_corner_radius_all(9)
			var fg := StyleBoxFlat.new()
			fg.bg_color = Color("#ff5d6c")
			fg.set_corner_radius_all(9)
			pb.add_theme_stylebox_override("background", bg)
			pb.add_theme_stylebox_override("fill", fg)
			life_bar = pb
		life_bar.max_value = max_lives
		life_bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		row.add_child(life_bar)
	elif lives_style == "herzen":
		hearts = HBoxContainer.new()
		hearts.add_theme_constant_override("separation", 4)
		row.add_child(hearts)
		for i in max_lives:
			hearts.add_child(Control.new())
		heart_full = String(ui.get("heart", ""))
		heart_empty = String(ui.get("heartEmpty", ""))
	else:
		row.add_child(hud_icon(String(ui.get("heart", "")), "♥", Color("#ff5d6c")))
		hud_lives = Label.new()
		hud_lives.add_theme_font_size_override("font_size", 24)
		row.add_child(hud_lives)
	bubble_layer = CanvasLayer.new()
	bubble_layer.layer = 0
	add_child(bubble_layer)
	pause_panel = VBoxContainer.new()
	pause_panel.set_anchors_preset(Control.PRESET_CENTER)
	pause_panel.alignment = BoxContainer.ALIGNMENT_CENTER
	pause_panel.add_theme_constant_override("separation", 14)
	pause_panel.visible = false
	layer.add_child(pause_panel)
	var shade := ColorRect.new()
	shade.color = Color(0, 0, 0, 0.5)
	shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	shade.visible = false
	layer.add_child(shade)
	layer.move_child(shade, 1)
	pause_panel.set_meta("shade", shade)
	var title := Label.new()
	title.text = "Pause"
	title.add_theme_font_size_override("font_size", 56)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	pause_panel.add_child(title)
	for pair in [["Weiter", "resume"], ["Hauptmenü", "menu"]]:
		var b := Button.new()
		b.text = pair[0]
		b.custom_minimum_size = Vector2(260, 56)
		b.add_theme_font_size_override("font_size", 26)
		b.pressed.connect(_pause_button.bind(pair[1]))
		pause_panel.add_child(b)
	pause_panel.position = Vector2(640 - 130, 230)


func _pause_button(what: String) -> void:
	set_paused(false)
	if what == "menu":
		to_menu.emit()


func set_paused(on: bool) -> void:
	get_tree().paused = on
	pause_panel.visible = on
	(pause_panel.get_meta("shade") as Control).visible = on
	if on:
		(pause_panel.get_child(1) as Button).grab_focus()


## Symbol in der Anzeige: eigene Grafik oder ein Zeichen
func hud_icon(rel: String, fallback: String, color: Color, faded := false) -> Control:
	var tex := Assets.texture(rel)
	if tex:
		var tr := TextureRect.new()
		tr.texture = tex
		tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		tr.custom_minimum_size = Vector2(30, 30)
		if faded:
			tr.modulate = Color(1, 1, 1, 0.3)
		return tr
	var l := Label.new()
	l.text = fallback
	l.add_theme_font_size_override("font_size", 26)
	l.add_theme_color_override("font_color", Color(0.6, 0.62, 0.7, 0.55) if faded else color)
	return l


func update_hud() -> void:
	if hud == null:
		return
	hud.text = String(data.get("name", ""))
	hud_coins.text = str(points)
	var shown := maxi(0, lives)
	if life_bar:
		life_bar.value = shown
	elif hearts:
		for c in hearts.get_children():
			c.queue_free()
		for i in max_lives:
			if i < shown:
				hearts.add_child(hud_icon(heart_full, "♥", Color("#ff5d6c")))
			elif heart_empty != "":
				hearts.add_child(hud_icon(heart_empty, "♡", Color("#ff5d6c")))
			else:
				hearts.add_child(hud_icon(heart_full, "♥", Color("#ff5d6c"), true))
	elif hud_lives:
		hud_lives.text = str(shown)


func hurt(fell: bool) -> void:
	if done or player.invulnerable > 0.0:
		return
	lives -= 1
	update_hud()
	if lives <= 0:
		done = true
		game_over.emit()
		return
	if fell:
		player.respawn(spawn)
	else:
		player.knockback()


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("pause") and not done:
		set_paused(not get_tree().paused)
		return
	if not dialog.is_empty() and dialog["mode"] == "gespraech" and not get_tree().paused:
		var click: bool = event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT
		if event.is_action_pressed("weiter") or click:
			get_viewport().set_input_as_handled()
			next_line()


func _process(delta: float) -> void:
	if get_tree().paused or player == null:
		return
	for c in get_tree().get_nodes_in_group("coins"):
		if c.has_meta("spin"):
			(c.get_meta("spin") as Node3D).rotate_y(delta * 3.0)
	# Kamera folgt seitlich, bleibt im Level
	var half := 7.5
	var tx := clampf(player.position.x, half, max(half, width - half))
	var ty := maxf(player.position.y + 1.6, 4.0)
	var target := Vector3(tx, ty + 0.6, 17)
	camera.position = camera.position.lerp(target, clampf(delta * 5.0, 0, 1))
	camera.look_at(Vector3(camera.position.x, ty - 0.4, 0))
	if player.position.y < -8 and not done:
		hurt(true)
	if not dialog.is_empty():
		position_bubble()
		dialog["time"] += delta
		var wait: float = dialog["secs"]
		if autotest and dialog["mode"] == "gespraech":
			wait = 1.0
		if (dialog["mode"] != "gespraech" or autotest) and dialog["time"] >= wait:
			next_line()
	if autotest:
		autotest_time += delta
		if autotest_time > 25.0:
			print("AUTOTEST: Zeit um, Position ", player.position, " Münzen ", points)
			get_tree().quit(0)
