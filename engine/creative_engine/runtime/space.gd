extends Node3D
## Weltraum-Level: Raumschiff aus der Verfolgerkamera (Third Person), Fadenkreuz, mehrere Waffen,
## Gegner (Jäger, Kreuzer, Geschütze), die zurückschießen, Planeten zum Landen, Raumbasen zum Reparieren
## und ein Horizont-Planet am Rand der Welt. Gebaut aus den Level-Daten des Editors (kind = "weltraum").

signal finished(points: int)
signal game_over
signal to_menu

const Assets = preload("res://assets.gd")

const ENEMY_TYPES := {
	"jaeger": {"name": "Jäger", "hp": 3, "speed": 46.0, "turn": 1.8, "weapon": "laser", "radius": 3.2,
		"color": "#d9534f", "points": 10, "range": 260.0, "cooldown": 0.9},
	"kreuzer": {"name": "Kreuzer", "hp": 14, "speed": 14.0, "turn": 0.5, "weapon": "plasma", "radius": 9.0,
		"color": "#8a4fd9", "points": 50, "range": 320.0, "cooldown": 1.6},
	"geschuetz": {"name": "Geschütz", "hp": 6, "speed": 0.0, "turn": 2.2, "weapon": "laser", "radius": 4.0,
		"color": "#e08a3c", "points": 15, "range": 300.0, "cooldown": 1.1},
}
## Schaden, den gegnerische Schüsse am eigenen Schiff anrichten (Hüllenpunkte)
const ENEMY_DAMAGE := {"laser": 6.0, "plasma": 16.0, "rakete": 20.0, "streu": 4.0}
const DEFAULT_WEAPONS := [
	{"name": "Laser", "type": "laser", "damage": 1, "cooldown": 0.14, "speed": 420, "color": "#ff5d6c"},
	{"name": "Plasma", "type": "plasma", "damage": 4, "cooldown": 0.6, "speed": 230, "color": "#7fe0ff"},
	{"name": "Raketen", "type": "rakete", "damage": 6, "cooldown": 1.1, "speed": 170, "color": "#ffb347", "ammo": 12},
	{"name": "Streuschuss", "type": "streu", "damage": 1, "cooldown": 0.5, "speed": 360, "color": "#c49bff"},
]

const PLANET_SHADER := """
shader_type spatial;
uniform vec4 color_a : source_color = vec4(0.2, 0.4, 0.8, 1.0);
uniform vec4 color_b : source_color = vec4(0.3, 0.6, 0.3, 1.0);
uniform float scale = 3.0;
uniform float bands = 0.0;
varying vec3 lp;
float hash(vec3 p) { p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
float noise(vec3 x) {
	vec3 i = floor(x); vec3 f = fract(x); f = f * f * (3.0 - 2.0 * f);
	return mix(mix(mix(hash(i), hash(i + vec3(1,0,0)), f.x), mix(hash(i + vec3(0,1,0)), hash(i + vec3(1,1,0)), f.x), f.y),
		mix(mix(hash(i + vec3(0,0,1)), hash(i + vec3(1,0,1)), f.x), mix(hash(i + vec3(0,1,1)), hash(i + vec3(1,1,1)), f.x), f.y), f.z);
}
float fbm(vec3 p) { float v = 0.0; float a = 0.5; for (int i = 0; i < 5; i++) { v += a * noise(p); p *= 2.03; a *= 0.5; } return v; }
void vertex() { lp = normalize(VERTEX); }
void fragment() {
	float f = fbm(lp * scale + vec3(lp.y * bands * 6.0));
	float b = mix(f, 0.5 + 0.5 * sin(lp.y * 18.0 + f * 4.0), bands);
	ALBEDO = mix(color_a.rgb, color_b.rgb, smoothstep(0.42, 0.62, b)) * (0.85 + 0.3 * f);
	ROUGHNESS = 0.95;
	SPECULAR = 0.1;
}
"""

const ATMO_SHADER := """
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_back;
uniform vec4 glow : source_color = vec4(0.5, 0.8, 1.0, 1.0);
uniform float power = 3.0;
void fragment() {
	float r = 1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0);
	float a = pow(r, power);
	ALBEDO = glow.rgb * a * 1.6;
	ALPHA = a;
}
"""

const SKY_SHADER := """
shader_type sky;
uniform vec4 base : source_color = vec4(0.02, 0.03, 0.06, 1.0);
uniform vec4 nebula : source_color = vec4(0.25, 0.18, 0.45, 1.0);
uniform float stars = 1.0;
float hash(vec3 p) { p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
float noise(vec3 x) {
	vec3 i = floor(x); vec3 f = fract(x); f = f * f * (3.0 - 2.0 * f);
	return mix(mix(mix(hash(i), hash(i + vec3(1,0,0)), f.x), mix(hash(i + vec3(0,1,0)), hash(i + vec3(1,1,0)), f.x), f.y),
		mix(mix(hash(i + vec3(0,0,1)), hash(i + vec3(1,0,1)), f.x), mix(hash(i + vec3(0,1,1)), hash(i + vec3(1,1,1)), f.x), f.y), f.z);
}
void sky() {
	vec3 d = EYEDIR;
	vec3 c = base.rgb;
	float n = noise(d * 2.5) * 0.6 + noise(d * 6.0 + 3.0) * 0.4;
	c += nebula.rgb * smoothstep(0.5, 0.95, n) * 0.7;
	vec3 g = d * 240.0;
	vec3 id = floor(g);
	float h = hash(id);
	float s = step(1.0 - 0.025 * stars, h) * smoothstep(0.32, 0.0, length(fract(g) - 0.5));
	c += vec3(s) * (0.5 + 0.5 * hash(id + 3.1));
	COLOR = c;
}
"""


class Overlay extends Control:
	## Zeichnet Fadenkreuz, Zielmarkierungen und Pfeile zu Gegnern außerhalb des Bildes.
	var level
	func _draw() -> void:
		if level:
			level.draw_overlay(self)


var data := {}
var game := {}
var points := 0
var autotest := false
var done := false
var ship_cfg := {}
var ship: Node3D
var ship_visual: Node3D
var smoke: CPUParticles3D
var camera: Camera3D
var world: Node3D                 # alles im All (wird beim Landen ausgeblendet)
var surface: Node3D               # Planetenoberfläche (nur gelandet)
var env: Environment
var space_env: Environment
var horizon: Node3D
var horizon_cfg := {}
var speed := 0.0
var throttle := 0.5
var boosting := false
var braking := false
var boost_energy := 1.0          # Boost hält ein paar Sekunden, lädt sich dann wieder auf
var boost_kick := 0.0            # kurzer Stoß beim Zünden (Sichtfeld, Kamera)
var boost_blocked := false
var maneuver := {}               # laufendes Manöver: Looping oder Fassrolle
var maneuver_wait := 0.0
var shake := 0.0
var streaks: Array = []          # Geschwindigkeitsstreifen um die Kamera
var streak_mat: StandardMaterial3D
var retro: Array = []            # Bremsdüsen vorne
var max_speed := 60.0
var boost := 1.8
var turn := 1.6
var hull := 100.0
var max_hull := 100.0
var shield := 60.0
var max_shield := 60.0
var shield_wait := 0.0
var lives := 3
var invulnerable := 0.0
var weapons: Array = []
var weapon_i := 0
var cooldown := 0.0
var ammo := {}
var mouse := Vector2.ZERO
var spawn_pos := Vector3.ZERO
var spawn_basis := Basis.IDENTITY
var enemies: Array = []
var shots: Array = []
var blasts: Array = []
var planets: Array = []
var bases: Array = []
var rocks: Array = []
var landed := {}
var land_option := {}
var docked := {}
var repair_done := false
var flash := 0.0
var materials := {}
var kills := 0
var total_enemies := 0
var message_time := 0.0
var aim_target := {}
var goal := "gegner"
var goal_target := ""
var goal_reached := false
var finish_wait := -1.0

# Anzeige
var overlay: Overlay
var prompt: Label
var message: Label
var flash_rect: ColorRect
var pause_panel: Control
var pause_shade: Control

# Autotest (Autopilot)
var test_time := 0.0
var test_phase := "kampf"
var test_said := {}
var phase_time := 0.0


func setup(level_data: Dictionary, game_data: Dictionary, start_points: int, test: bool) -> void:
	data = level_data
	game = game_data
	points = start_points
	autotest = test
	ship_cfg = game.get("ship", {})
	max_speed = float(ship_cfg.get("speed", 60.0))
	boost = float(ship_cfg.get("boost", 1.8))
	turn = float(ship_cfg.get("turn", 1.6))
	max_hull = float(ship_cfg.get("hull", 100.0))
	max_shield = float(ship_cfg.get("shield", 60.0))
	hull = max_hull
	shield = max_shield
	lives = int(ship_cfg.get("lives", game.get("player", {}).get("lives", 3)))
	weapons = ship_cfg.get("weapons", [])
	if weapons.is_empty():
		weapons = DEFAULT_WEAPONS.duplicate(true)
	for i in weapons.size():
		if weapons[i].has("ammo"):
			ammo[i] = int(weapons[i]["ammo"])
	goal = String(data.get("goal", "gegner"))
	goal_target = String(data.get("goalTarget", ""))
	horizon_cfg = data.get("horizon", {})


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	setup_input()
	world = Node3D.new()
	add_child(world)
	build_environment()
	build_horizon()
	for e in data.get("entities", []):
		build_entity(e)
	build_ship()
	build_camera()
	build_hud()
	total_enemies = enemies.size()
	if not autotest:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	var goals := {"gegner": "Zerstöre alle feindlichen Schiffe", "landen": "Lande auf %s" % (goal_target if goal_target != "" else "einem Planeten"),
		"basis": "Fliege zur Raumbasis %s" % goal_target, "frei": "Freier Flug"}
	show_message(String(goals.get(goal, "")), 4.0)
	update_hud()


func _exit_tree() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE


func setup_input() -> void:
	if game.has("controls"):
		return            # Belegung aus dem Editor – main.gd hat sie schon eingerichtet
	var keys := {
		"schub": [KEY_W], "bremse": [KEY_S], "gieren_links": [KEY_A], "gieren_rechts": [KEY_D],
		"nicken_hoch": [KEY_DOWN], "nicken_runter": [KEY_UP], "waffe_zurueck": [],
		"rollen_links": [KEY_Q], "rollen_rechts": [KEY_E], "boost": [KEY_SHIFT], "feuer": [KEY_SPACE, KEY_CTRL],
		"waffe_weiter": [KEY_TAB], "landen": [KEY_L], "waffe1": [KEY_1], "waffe2": [KEY_2], "waffe3": [KEY_3],
		"waffe4": [KEY_4], "waffe5": [KEY_5], "waffe6": [KEY_6],
		"looping": [KEY_R], "fassrolle_links": [KEY_X], "fassrolle_rechts": [KEY_C],
	}
	for action in keys:
		if InputMap.has_action(action):
			continue
		InputMap.add_action(action, 0.2)
		for key in keys[action]:
			var ev := InputEventKey.new()
			ev.physical_keycode = key
			InputMap.action_add_event(action, ev)
	var pad := {"feuer": JOY_BUTTON_RIGHT_SHOULDER, "boost": JOY_BUTTON_LEFT_SHOULDER, "landen": JOY_BUTTON_Y,
		"waffe_weiter": JOY_BUTTON_X}
	for action in pad:
		var jb := InputEventJoypadButton.new()
		jb.button_index = pad[action]
		InputMap.action_add_event(action, jb)
	var axes := [["gieren_links", JOY_AXIS_LEFT_X, -1.0], ["gieren_rechts", JOY_AXIS_LEFT_X, 1.0],
		["nicken_runter", JOY_AXIS_LEFT_Y, -1.0], ["nicken_hoch", JOY_AXIS_LEFT_Y, 1.0],
		["schub", JOY_AXIS_TRIGGER_RIGHT, 1.0], ["bremse", JOY_AXIS_TRIGGER_LEFT, 1.0],
		["rollen_links", JOY_AXIS_RIGHT_X, -1.0], ["rollen_rechts", JOY_AXIS_RIGHT_X, 1.0]]
	for a in axes:
		var jm := InputEventJoypadMotion.new()
		jm.axis = a[1]
		jm.axis_value = a[2]
		InputMap.action_add_event(a[0], jm)
	for pair in [["feuer", MOUSE_BUTTON_LEFT], ["waffe_weiter", MOUSE_BUTTON_RIGHT], ["waffe_weiter", MOUSE_BUTTON_WHEEL_DOWN],
			["waffe_zurueck", MOUSE_BUTTON_WHEEL_UP]]:
		var mb := InputEventMouseButton.new()
		mb.button_index = pair[1]
		InputMap.action_add_event(pair[0], mb)


func mat(color: Color, emit := 0.0, rough := 0.6, metal := 0.3) -> StandardMaterial3D:
	var key := "%s/%s/%s/%s" % [color.to_html(), emit, rough, metal]
	if materials.has(key):
		return materials[key]
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = rough
	m.metallic = metal
	if emit > 0.0:
		m.emission_enabled = true
		m.emission = color
		m.emission_energy_multiplier = emit
	materials[key] = m
	return m


func glow_mat(color: Color) -> StandardMaterial3D:
	var key := "glow" + color.to_html()
	if materials.has(key):
		return materials[key]
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_color = color
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	materials[key] = m
	return m


func pos_of(e: Dictionary) -> Vector3:
	return Vector3(float(e.get("x", 0)), float(e.get("y", 0)), float(e.get("z", 0)))


# ---- Himmel und Horizont --------------------------------------------------------------------
func build_environment() -> void:
	env = Environment.new()
	var sky := Sky.new()
	var image := Assets.texture(String(data.get("skyImage", "")))
	if image:
		var pm := PanoramaSkyMaterial.new()
		pm.panorama = image
		sky.sky_material = pm
	else:
		var sm := ShaderMaterial.new()
		var sh := Shader.new()
		sh.code = SKY_SHADER
		sm.shader = sh
		sm.set_shader_parameter("base", Color(String(data.get("sky", "#04060c"))))
		sm.set_shader_parameter("nebula", Color(String(data.get("nebula", "#3a2d6b"))))
		sm.set_shader_parameter("stars", float(data.get("stars", 1.0)))
		sky.sky_material = sm
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.55, 0.6, 0.75)
	env.ambient_light_energy = 0.45
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.glow_enabled = true
	space_env = env
	var we := WorldEnvironment.new()
	we.name = "Umgebung"
	we.environment = env
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-35, float(data.get("sunAngle", -40)), 0)
	sun.light_energy = 1.2
	sun.light_color = Color(String(data.get("sunColor", "#fff3e0")))
	add_child(sun)


func planet_material(a: Color, b: Color, scale_: float, bands := 0.0) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	var sh := Shader.new()
	sh.code = PLANET_SHADER
	m.shader = sh
	m.set_shader_parameter("color_a", a)
	m.set_shader_parameter("color_b", b)
	m.set_shader_parameter("scale", scale_)
	m.set_shader_parameter("bands", bands)
	return m


func atmosphere(radius: float, color: Color, power := 3.0) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = radius
	sm.height = radius * 2.0
	sm.radial_segments = 64
	sm.rings = 32
	mi.mesh = sm
	var m := ShaderMaterial.new()
	var sh := Shader.new()
	sh.code = ATMO_SHADER
	m.shader = sh
	m.set_shader_parameter("glow", color)
	m.set_shader_parameter("power", power)
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi


## Riesiger Planet am Rand der Welt, der mit der Kamera mitwandert – man sieht seine Krümmung als Horizont.
func build_horizon() -> void:
	if not horizon_cfg.get("on", false):
		return
	var r := 6000.0
	horizon = Node3D.new()
	world.add_child(horizon)
	var body := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = r
	sm.height = r * 2.0
	sm.radial_segments = 128
	sm.rings = 64
	body.mesh = sm
	var c := Color(String(horizon_cfg.get("color", "#2f5fb3")))
	var c2 := Color(String(horizon_cfg.get("color2", "#3f8f4f")))
	body.material_override = planet_material(c, c2, 9.0, float(horizon_cfg.get("bands", 0.0)))
	body.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	horizon.add_child(body)
	horizon.add_child(atmosphere(r * 1.03, Color(String(horizon_cfg.get("atmosphere", "#7fc4ff"))), 2.2))
	horizon.set_meta("radius", r)


func update_horizon() -> void:
	if horizon == null or camera == null:
		return
	var r: float = horizon.get_meta("radius")
	var side := String(horizon_cfg.get("side", "unten"))
	var dirs := {"unten": Vector3.DOWN, "oben": Vector3.UP, "links": Vector3.LEFT, "rechts": Vector3.RIGHT,
		"vorne": Vector3.FORWARD, "hinten": Vector3.BACK}
	var d: Vector3 = dirs.get(side, Vector3.DOWN)
	var gap := float(horizon_cfg.get("distance", 900.0))
	horizon.global_position = camera.global_position + d * (r + gap)


# ---- Objekte --------------------------------------------------------------------------------
func build_entity(e: Dictionary) -> void:
	var kind := String(e.get("kind", ""))
	var p := pos_of(e)
	match kind:
		"start":
			spawn_pos = p
			spawn_basis = Basis(Vector3.UP, deg_to_rad(float(e.get("dir", 0.0))))
		"planet":
			add_planet(e, p)
		"base":
			add_base(e, p)
		"enemy":
			add_enemy(e, p)
		"asteroids":
			add_asteroids(e, p)
		"asteroid":
			add_rock(p, float(e.get("size", 18.0)), Color(String(e.get("color", "#6e6259"))), int(p.x * 31 + p.z))


func add_planet(e: Dictionary, p: Vector3) -> void:
	var r := float(e.get("radius", 120.0))
	var node := Node3D.new()
	node.position = p
	world.add_child(node)
	var mi := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = r
	sm.height = r * 2.0
	sm.radial_segments = 64
	sm.rings = 32
	mi.mesh = sm
	var a := Color(String(e.get("color", "#c8673a")))
	var b := Color(String(e.get("color2", "#7a3a22")))
	mi.material_override = planet_material(a, b, float(e.get("detail", 3.0)), float(e.get("bands", 0.0)))
	node.add_child(mi)
	if String(e.get("atmosphere", "")) != "":
		node.add_child(atmosphere(r * 1.06, Color(String(e["atmosphere"]))))
	if e.get("ring", false):
		var ring := MeshInstance3D.new()
		var tm := TorusMesh.new()
		tm.inner_radius = r * 1.4
		tm.outer_radius = r * 2.0
		tm.rings = 96
		ring.mesh = tm
		ring.scale = Vector3(1, 0.02, 1)
		ring.rotation_degrees = Vector3(18, 0, 8)
		var rm := StandardMaterial3D.new()
		rm.albedo_color = Color(String(e.get("ringColor", "#d9c7a0")), 0.6)
		rm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		rm.cull_mode = BaseMaterial3D.CULL_DISABLED
		ring.material_override = rm
		node.add_child(ring)
	planets.append({"node": node, "pos": p, "radius": r, "data": e, "name": String(e.get("name", "Planet")),
		"landable": bool(e.get("landable", true))})


func add_base(e: Dictionary, p: Vector3) -> void:
	var node := Node3D.new()
	node.position = p
	node.rotation_degrees = Vector3(0, float(e.get("dir", 0.0)), 0)
	world.add_child(node)
	var model := Assets.fitted(String(e.get("model", "")), 30.0)
	if model:
		node.add_child(model)
	else:
		var hub := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = 5
		cm.bottom_radius = 5
		cm.height = 26
		hub.mesh = cm
		hub.material_override = mat(Color("#9aa3b2"), 0.0, 0.4, 0.7)
		node.add_child(hub)
		var ring := MeshInstance3D.new()
		var tm := TorusMesh.new()
		tm.inner_radius = 16
		tm.outer_radius = 20
		tm.rings = 48
		ring.mesh = tm
		ring.material_override = mat(Color("#c3cad6"), 0.0, 0.35, 0.8)
		node.add_child(ring)
		for i in 4:
			var spoke := MeshInstance3D.new()
			var bm := BoxMesh.new()
			bm.size = Vector3(32, 1.2, 1.6)
			spoke.mesh = bm
			spoke.rotation_degrees = Vector3(0, i * 45.0, 0)
			spoke.material_override = mat(Color("#7d8696"), 0.0, 0.5, 0.6)
			node.add_child(spoke)
		for y in [-13.5, 13.5]:
			var lamp := MeshInstance3D.new()
			var sp := SphereMesh.new()
			sp.radius = 1.2
			sp.height = 2.4
			lamp.mesh = sp
			lamp.position = Vector3(0, y, 0)
			lamp.material_override = mat(Color("#6fdcc0"), 4.0)
			node.add_child(lamp)
	# Andockzone: leuchtender Ring
	var zone := MeshInstance3D.new()
	var zt := TorusMesh.new()
	zt.inner_radius = 44
	zt.outer_radius = 45
	zt.rings = 64
	zone.mesh = zt
	zone.material_override = glow_mat(Color(0.43, 0.86, 0.75, 0.35))
	node.add_child(zone)
	var light := OmniLight3D.new()
	light.light_color = Color("#6fdcc0")
	light.omni_range = 80
	light.light_energy = 1.5
	node.add_child(light)
	bases.append({"node": node, "pos": p, "radius": 45.0, "data": e, "name": String(e.get("name", "Raumbasis")),
		"rate": float(e.get("repair", 25.0))})


func enemy_mesh(type: String, color: Color) -> Node3D:
	var v := Node3D.new()
	var dark := mat(color.darkened(0.45), 0.0, 0.5, 0.6)
	var main := mat(color, 0.0, 0.45, 0.5)
	var engine := mat(Color("#ff7a4a"), 3.0)
	match type:
		"kreuzer":
			var hull_ := MeshInstance3D.new()
			var bm := BoxMesh.new()
			bm.size = Vector3(6, 3, 18)
			hull_.mesh = bm
			hull_.material_override = dark
			v.add_child(hull_)
			var bridge := MeshInstance3D.new()
			var b2 := BoxMesh.new()
			b2.size = Vector3(3, 3, 4)
			bridge.mesh = b2
			bridge.position = Vector3(0, 2.6, 4)
			bridge.material_override = main
			v.add_child(bridge)
			var nose := MeshInstance3D.new()
			var pm := PrismMesh.new()
			pm.size = Vector3(6, 6, 3)
			nose.mesh = pm
			nose.rotation_degrees = Vector3(-90, 0, 0)
			nose.position = Vector3(0, 0, -12)
			nose.material_override = main
			v.add_child(nose)
			for x in [-3.5, 3.5]:
				var pod := MeshInstance3D.new()
				var cm := CylinderMesh.new()
				cm.top_radius = 1.4
				cm.bottom_radius = 1.4
				cm.height = 10
				pod.mesh = cm
				pod.rotation_degrees = Vector3(90, 0, 0)
				pod.position = Vector3(x, -0.5, 3)
				pod.material_override = main
				v.add_child(pod)
				var glow := MeshInstance3D.new()
				var gs := SphereMesh.new()
				gs.radius = 1.2
				gs.height = 2.4
				glow.mesh = gs
				glow.position = Vector3(x, -0.5, 8.2)
				glow.material_override = engine
				v.add_child(glow)
		"geschuetz":
			var base_ := MeshInstance3D.new()
			var sm := SphereMesh.new()
			sm.radius = 3.0
			sm.height = 4.0
			base_.mesh = sm
			base_.material_override = dark
			v.add_child(base_)
			for x in [-0.8, 0.8]:
				var barrel := MeshInstance3D.new()
				var cm := CylinderMesh.new()
				cm.top_radius = 0.35
				cm.bottom_radius = 0.45
				cm.height = 5
				barrel.mesh = cm
				barrel.rotation_degrees = Vector3(90, 0, 0)
				barrel.position = Vector3(x, 0.6, -3.5)
				barrel.material_override = main
				v.add_child(barrel)
			var eye := MeshInstance3D.new()
			var es := SphereMesh.new()
			es.radius = 0.7
			es.height = 1.4
			eye.mesh = es
			eye.position = Vector3(0, 1.2, -2.4)
			eye.material_override = mat(Color("#ff3b3b"), 4.0)
			v.add_child(eye)
		_:
			var body := MeshInstance3D.new()
			var pm := PrismMesh.new()
			pm.size = Vector3(2.2, 5.0, 1.0)
			body.mesh = pm
			body.rotation_degrees = Vector3(-90, 0, 0)
			body.material_override = main
			v.add_child(body)
			for x in [-1, 1]:
				var wing := MeshInstance3D.new()
				var wb := BoxMesh.new()
				wb.size = Vector3(0.25, 3.2, 3.0)
				wing.mesh = wb
				wing.position = Vector3(x * 1.8, 0, 1.0)
				wing.rotation_degrees = Vector3(0, 0, x * 12.0)
				wing.material_override = dark
				v.add_child(wing)
			var glow := MeshInstance3D.new()
			var gs := SphereMesh.new()
			gs.radius = 0.5
			gs.height = 1.0
			glow.mesh = gs
			glow.position = Vector3(0, 0, 2.6)
			glow.material_override = engine
			v.add_child(glow)
	return v


func add_enemy(e: Dictionary, p: Vector3) -> void:
	var type := String(e.get("type", "jaeger"))
	var info: Dictionary = ENEMY_TYPES.get(type, ENEMY_TYPES["jaeger"])
	var node := Node3D.new()
	node.position = p
	node.rotation_degrees = Vector3(0, float(e.get("dir", 0.0)), 0)
	world.add_child(node)
	var size := float(info["radius"]) * 2.0
	var model := Assets.fitted(String(e.get("model", "")), size * 0.5)
	if model:
		var pivot := Node3D.new()
		pivot.rotation_degrees = Vector3(0, 180, 0)      # glTF schaut nach +Z, Godot nach -Z
		pivot.add_child(model)
		node.add_child(pivot)
	else:
		node.add_child(enemy_mesh(type, Color(String(e.get("color", info["color"])))))
	var hp := int(e.get("hp", info["hp"]))
	enemies.append({"node": node, "type": type, "hp": hp, "max": hp, "info": info, "home": p,
		"weapon": String(e.get("weapon", info["weapon"])), "cd": randf_range(0.5, 2.0), "evade": 0.0,
		"speed": float(e.get("speed", info["speed"])), "radius": float(info["radius"]), "hit": 0.0,
		"angle": randf() * TAU, "name": String(e.get("name", info["name"]))})


func add_asteroids(e: Dictionary, p: Vector3) -> void:
	var count := int(e.get("count", 30))
	var spread := float(e.get("spread", 160.0))
	var rng := RandomNumberGenerator.new()
	rng.seed = int(p.x * 13 + p.z * 7 + count)
	var rock_mat := mat(Color(String(e.get("color", "#6e6259"))), 0.0, 1.0, 0.0)
	for i in count:
		var mi := MeshInstance3D.new()
		var sm := SphereMesh.new()
		var r := rng.randf_range(2.0, float(e.get("size", 9.0)))
		sm.radius = r
		sm.height = r * 2.0
		sm.radial_segments = 10
		sm.rings = 6
		mi.mesh = sm
		mi.material_override = rock_mat
		mi.position = p + Vector3(rng.randf_range(-1, 1), rng.randf_range(-0.4, 0.4), rng.randf_range(-1, 1)) * spread
		mi.scale = Vector3(rng.randf_range(0.7, 1.3), rng.randf_range(0.6, 1.0), rng.randf_range(0.7, 1.4))
		mi.rotation = Vector3(rng.randf() * TAU, rng.randf() * TAU, 0)
		world.add_child(mi)
		rocks.append({"node": mi, "radius": r, "spin": Vector3(rng.randf_range(-0.4, 0.4), rng.randf_range(-0.4, 0.4), 0)})


func add_rock(p: Vector3, r: float, color: Color, seed_: int) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_
	var mi := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = r
	sm.height = r * 2.0
	sm.radial_segments = 14
	sm.rings = 8
	mi.mesh = sm
	mi.material_override = planet_material(color, color.darkened(0.35), 2.5)
	mi.position = p
	mi.scale = Vector3(rng.randf_range(0.8, 1.2), rng.randf_range(0.65, 0.95), rng.randf_range(0.8, 1.3))
	mi.rotation = Vector3(rng.randf() * TAU, rng.randf() * TAU, 0)
	world.add_child(mi)
	rocks.append({"node": mi, "radius": r * 0.9, "spin": Vector3.ZERO})


# ---- Eigenes Schiff ---------------------------------------------------------------------------
func build_ship() -> void:
	ship = Node3D.new()
	ship.position = spawn_pos
	ship.basis = spawn_basis
	add_child(ship)
	ship_visual = Node3D.new()
	ship.add_child(ship_visual)
	var model := Assets.fitted(String(ship_cfg.get("model", "")), float(ship_cfg.get("size", 2.2)))
	if model:
		var pivot := Node3D.new()
		pivot.rotation_degrees = Vector3(0, 180 + float(ship_cfg.get("modelTurn", 0.0)), 0)
		pivot.add_child(model)
		model.position.y -= float(ship_cfg.get("size", 2.2)) * 0.5
		ship_visual.add_child(pivot)
	else:
		var accent := Color(String(ship_cfg.get("color", "#8fb3ff")))
		var body := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = Vector3(1.3, 0.7, 4.2)
		body.mesh = bm
		body.material_override = mat(Color("#c9ced8"), 0.0, 0.35, 0.7)
		ship_visual.add_child(body)
		var nose := MeshInstance3D.new()
		var pm := PrismMesh.new()
		pm.size = Vector3(1.3, 1.8, 0.7)
		nose.mesh = pm
		nose.rotation_degrees = Vector3(-90, 0, 0)
		nose.position = Vector3(0, 0, -3.0)
		nose.material_override = mat(accent, 0.0, 0.4, 0.5)
		ship_visual.add_child(nose)
		var cockpit := MeshInstance3D.new()
		var cs := SphereMesh.new()
		cs.radius = 0.5
		cs.height = 0.7
		cockpit.mesh = cs
		cockpit.position = Vector3(0, 0.42, -0.9)
		cockpit.scale = Vector3(1, 1, 1.8)
		cockpit.material_override = mat(Color("#7fe0ff"), 0.6, 0.1, 0.2)
		ship_visual.add_child(cockpit)
		for x in [-1, 1]:
			var wing := MeshInstance3D.new()
			var wb := BoxMesh.new()
			wb.size = Vector3(3.2, 0.14, 1.8)
			wing.mesh = wb
			wing.position = Vector3(x * 2.1, -0.1, 0.9)
			wing.rotation_degrees = Vector3(0, x * -14.0, x * -6.0)
			wing.material_override = mat(Color("#8c93a1"), 0.0, 0.45, 0.6)
			ship_visual.add_child(wing)
			var tip := MeshInstance3D.new()
			var tb := BoxMesh.new()
			tb.size = Vector3(0.2, 0.6, 1.4)
			tip.mesh = tb
			tip.position = Vector3(x * 3.6, 0.05, 1.3)
			tip.material_override = mat(accent, 1.2)
			ship_visual.add_child(tip)
			var eng := MeshInstance3D.new()
			var cm := CylinderMesh.new()
			cm.top_radius = 0.32
			cm.bottom_radius = 0.4
			cm.height = 1.6
			eng.mesh = cm
			eng.rotation_degrees = Vector3(90, 0, 0)
			eng.position = Vector3(x * 0.55, 0, 2.4)
			eng.material_override = mat(Color("#5b6270"), 0.0, 0.4, 0.8)
			ship_visual.add_child(eng)
	# Triebwerksflammen hinten und Bremsdüsen vorne (auch bei eigenen Modellen)
	var k := float(ship_cfg.get("size", 2.2)) / 2.2 if model else 1.0
	var fs := SphereMesh.new()
	fs.radius = 0.3
	fs.height = 0.6
	for x in [-1, 1]:
		var flame := MeshInstance3D.new()
		flame.mesh = fs
		flame.position = Vector3(x * 0.55, 0, 3.25) * k
		var fm := StandardMaterial3D.new()
		fm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		fm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		fm.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
		fm.albedo_color = Color(0.5, 0.75, 1.0, 0.9)
		flame.material_override = fm
		flame.name = "Flamme"
		ship_visual.add_child(flame)
		var r := MeshInstance3D.new()
		var rs := SphereMesh.new()
		rs.radius = 0.16
		rs.height = 0.32
		r.mesh = rs
		r.position = Vector3(x * 0.5, -0.1, -3.2) * k
		r.material_override = glow_mat(Color(1.0, 0.6, 0.45, 0.85))
		r.visible = false
		ship_visual.add_child(r)
		retro.append(r)
	smoke = CPUParticles3D.new()
	smoke.amount = 40
	smoke.lifetime = 1.4
	smoke.emitting = false
	smoke.local_coords = false
	smoke.direction = Vector3(0, 0.3, 1)
	smoke.spread = 25
	smoke.initial_velocity_min = 2.0
	smoke.initial_velocity_max = 5.0
	smoke.gravity = Vector3.ZERO
	smoke.scale_amount_min = 0.6
	smoke.scale_amount_max = 1.6
	var sm := SphereMesh.new()
	sm.radius = 0.5
	sm.height = 1.0
	sm.radial_segments = 8
	sm.rings = 4
	smoke.mesh = sm
	var smat := StandardMaterial3D.new()
	smat.albedo_color = Color(0.25, 0.25, 0.28, 0.5)
	smat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	smat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	smoke.material_override = smat
	smoke.position = Vector3(0, 0.3, 1.5)
	ship.add_child(smoke)
	speed = max_speed * throttle


func build_camera() -> void:
	camera = Camera3D.new()
	camera.fov = 70
	camera.near = 0.3
	camera.far = 20000.0
	add_child(camera)
	camera.global_transform = chase_transform()
	camera.current = true


func chase_transform() -> Transform3D:
	var back := float(ship_cfg.get("cameraDistance", 12.0))
	var up := float(ship_cfg.get("cameraHeight", 3.2))
	var over := speed / maxf(1.0, max_speed) - 1.0          # > 0 beim Boost
	back += clampf(over, 0.0, 1.5) * 7.0 + boost_kick * 4.0 - (2.5 if braking else 0.0)
	up -= clampf(over, 0.0, 1.5) * 0.8
	var pos := ship.global_transform * Vector3(0, up, back)
	var look := ship.global_transform * Vector3(0, up * 0.55, -30)
	return Transform3D(Basis.looking_at(look - pos, ship.global_basis.y), pos)


## Spürbares Tempo: Sichtfeld weitet sich beim Boost (mit Stoß beim Zünden), zieht sich beim Bremsen
## zusammen, die Kamera wackelt, Streifen fliegen vorbei.
func speed_effects(delta: float) -> void:
	var k := speed / maxf(1.0, max_speed)
	var fov := 68.0 + clampf(k - 0.3, 0.0, 2.0) * 9.0 + boost_kick * 14.0 - (6.0 if braking else 0.0)
	camera.fov = lerpf(camera.fov, clampf(fov, 55.0, 105.0), clampf(delta * 4.0, 0, 1))
	shake = maxf(shake - delta, 0.0)
	var amp := shake * 0.5 + (0.07 if boosting else 0.0) + (0.04 if braking else 0.0)
	if amp > 0.0:
		camera.global_position += camera.global_basis * Vector3(randf_range(-1, 1), randf_range(-1, 1), 0) * amp
	update_streaks(k)


func build_streaks() -> void:
	streak_mat = StandardMaterial3D.new()
	streak_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	streak_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	streak_mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	streak_mat.albedo_color = Color(0.75, 0.85, 1.0, 0.0)
	var bm := BoxMesh.new()
	bm.size = Vector3(0.05, 0.05, 1.0)
	for i in 90:
		var mi := MeshInstance3D.new()
		mi.mesh = bm
		mi.material_override = streak_mat
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(mi)
		streaks.append(mi)
		place_streak(mi, true)


func place_streak(mi: MeshInstance3D, anywhere: bool) -> void:
	var a := randf() * TAU
	var r := randf_range(5.0, 28.0)
	var z := randf_range(-140.0, 10.0) if anywhere else randf_range(-150.0, -90.0)
	mi.global_position = ship.global_position + ship.global_basis * Vector3(cos(a) * r, sin(a) * r * 0.7, z)


func update_streaks(k: float) -> void:
	if streaks.is_empty():
		build_streaks()
	var strength := clampf((k - 0.75) * 1.2, 0.0, 1.0) + boost_kick * 0.5
	streak_mat.albedo_color.a = clampf(strength, 0.0, 0.9)
	var len := 2.0 + speed * 0.12
	for mi in streaks:
		var n := mi as MeshInstance3D
		n.visible = strength > 0.02
		var local := ship.global_basis.inverse() * (n.global_position - ship.global_position)
		if local.z > 14.0 or local.length() > 170.0:
			place_streak(n, false)
		n.global_basis = ship.global_basis
		n.scale = Vector3(1, 1, len)


func forward() -> Vector3:
	return -ship.global_basis.z


# ---- Anzeige (HUD) --------------------------------------------------------------------------
# Eigenes, gezeichnetes HUD im Stil heutiger Weltraum-Shooter: schräge Leisten mit Segmenten,
# Radar, Tacho-Bogen, Waffenleiste mit Symbolen, zweistufiges Fadenkreuz mit Zielerfassung.
const HUD_CYAN := Color("#6fe3ff")
const HUD_AMBER := Color("#ffb347")
const HUD_RED := Color("#ff5d6c")
const HUD_GREEN := Color("#6fdcc0")
const HUD_DIM := Color(0.62, 0.7, 0.82, 0.8)
const HUD_BG := Color(0.03, 0.05, 0.09, 0.55)


func label(size: int, color := Color("#e8ecf4")) -> Label:
	var l := Label.new()
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.add_theme_constant_override("outline_size", 6)
	l.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.55))
	return l


func build_hud() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	flash_rect = ColorRect.new()      # nur noch Platzhalter, der Treffer-Rand wird gezeichnet
	flash_rect.color = Color(0, 0, 0, 0)
	flash_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(flash_rect)
	overlay = Overlay.new()
	overlay.level = self
	overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(overlay)
	prompt = label(22, HUD_CYAN)
	prompt.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	prompt.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	prompt.grow_horizontal = Control.GROW_DIRECTION_BOTH
	prompt.position.y = -150
	layer.add_child(prompt)
	message = label(30)
	message.set_anchors_preset(Control.PRESET_CENTER_TOP)
	message.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	message.grow_horizontal = Control.GROW_DIRECTION_BOTH
	message.position.y = 110
	layer.add_child(message)
	pause_shade = ColorRect.new()
	(pause_shade as ColorRect).color = Color(0, 0, 0, 0.55)
	pause_shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	pause_shade.visible = false
	layer.add_child(pause_shade)
	pause_panel = VBoxContainer.new()
	pause_panel.set_anchors_preset(Control.PRESET_CENTER)
	pause_panel.add_theme_constant_override("separation", 14)
	pause_panel.visible = false
	layer.add_child(pause_panel)
	var title := label(56)
	title.text = "PAUSE"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	pause_panel.add_child(title)
	for pair in [["Weiter", "resume"], ["Hauptmenü", "menu"]]:
		var b := Button.new()
		b.text = pair[0]
		b.custom_minimum_size = Vector2(260, 56)
		b.add_theme_font_size_override("font_size", 26)
		var sb := StyleBoxFlat.new()
		sb.bg_color = Color(0.05, 0.08, 0.13, 0.85)
		sb.border_color = HUD_CYAN
		sb.border_width_left = 3
		sb.skew = Vector2(0.25, 0)
		var hov := sb.duplicate() as StyleBoxFlat
		hov.bg_color = Color(HUD_CYAN, 0.25)
		hov.set_border_width_all(2)
		b.add_theme_stylebox_override("normal", sb)
		b.add_theme_stylebox_override("hover", hov)
		b.add_theme_stylebox_override("focus", hov)
		b.add_theme_stylebox_override("pressed", hov)
		b.pressed.connect(_pause_button.bind(pair[1]))
		pause_panel.add_child(b)
	pause_panel.position = Vector2(-130, -120)


func _pause_button(what: String) -> void:
	set_paused(false)
	if what == "menu":
		to_menu.emit()


func set_paused(on: bool) -> void:
	get_tree().paused = on
	pause_panel.visible = on
	pause_shade.visible = on
	if not autotest:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE if on else Input.MOUSE_MODE_CAPTURED
	if on:
		(pause_panel.get_child(1) as Button).grab_focus()


func show_message(text: String, secs := 2.5) -> void:
	if message:
		message.text = text
		message_time = secs


func update_weapons() -> void:
	if overlay:
		overlay.queue_redraw()


func update_hud() -> void:
	if overlay:
		overlay.queue_redraw()


# -- Zeichenhelfer --
func hud_text(c: Control, pos: Vector2, text: String, size: int, color: Color, align := HORIZONTAL_ALIGNMENT_LEFT,
		italic := true, width := -1.0) -> void:
	var font := ThemeDB.fallback_font
	var w := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	var x := pos.x
	if align == HORIZONTAL_ALIGNMENT_RIGHT:
		x -= w
	elif align == HORIZONTAL_ALIGNMENT_CENTER:
		x -= w * 0.5
	c.draw_set_transform_matrix(Transform2D(0.0, Vector2.ONE, -0.18 if italic else 0.0, Vector2(x, pos.y)))
	c.draw_string_outline(font, Vector2.ZERO, text, HORIZONTAL_ALIGNMENT_LEFT, width, size, 5, Color(0, 0, 0, 0.5))
	c.draw_string(font, Vector2.ZERO, text, HORIZONTAL_ALIGNMENT_LEFT, width, size, color)
	c.draw_set_transform_matrix(Transform2D.IDENTITY)


func slant(r: Rect2, k: float) -> PackedVector2Array:
	## Parallelogramm (k = Versatz oben nach rechts)
	return PackedVector2Array([r.position + Vector2(k, 0), r.position + Vector2(r.size.x, 0),
		r.position + Vector2(r.size.x - k, r.size.y), r.position + Vector2(0, r.size.y)])


func cut_panel(c: Control, r: Rect2, cut: float, fill: Color, edge: Color) -> void:
	var p := r.position
	var s := r.size
	var pts := PackedVector2Array([p + Vector2(cut, 0), p + Vector2(s.x, 0), p + Vector2(s.x, s.y - cut),
		p + Vector2(s.x - cut, s.y), p + Vector2(0, s.y), p + Vector2(0, cut)])
	c.draw_colored_polygon(pts, fill)
	pts.append(pts[0])
	c.draw_polyline(pts, edge, 1.5, true)


func seg_bar(c: Control, pos: Vector2, w: float, h: float, frac: float, color: Color, segs := 16) -> void:
	var gap := 3.0
	var sw := (w - gap * (segs - 1)) / segs
	for i in segs:
		var r := Rect2(pos + Vector2(i * (sw + gap), 0), Vector2(sw, h))
		var on := float(i) < frac * segs - 0.001
		var part := clampf(frac * segs - i, 0.0, 1.0)
		c.draw_colored_polygon(slant(r, h * 0.45), Color(color, 0.16))
		if on:
			c.draw_colored_polygon(slant(r, h * 0.45), Color(color, 0.35 + 0.65 * part))


func ship_glyph(c: Control, center: Vector2, size: float, color: Color) -> void:
	var s := size
	var body := PackedVector2Array([center + Vector2(0, -s), center + Vector2(s * 0.28, s * 0.25), center + Vector2(s, s * 0.55),
		center + Vector2(s * 0.95, s * 0.75), center + Vector2(s * 0.25, s * 0.6), center + Vector2(s * 0.2, s * 0.9),
		center + Vector2(-s * 0.2, s * 0.9), center + Vector2(-s * 0.25, s * 0.6), center + Vector2(-s * 0.95, s * 0.75),
		center + Vector2(-s, s * 0.55), center + Vector2(-s * 0.28, s * 0.25)])
	c.draw_colored_polygon(body, Color(color, 0.25))
	body.append(body[0])
	c.draw_polyline(body, color, 2.0, true)


func weapon_glyph(c: Control, center: Vector2, type: String, color: Color, s: float) -> void:
	match type:
		"plasma":
			c.draw_circle(center, s * 0.42, Color(color, 0.35))
			c.draw_arc(center, s * 0.42, 0, TAU, 24, color, 2.0, true)
			c.draw_circle(center, s * 0.16, color)
		"rakete":
			var pts := PackedVector2Array([center + Vector2(s * 0.7, 0), center + Vector2(s * 0.3, -s * 0.18),
				center + Vector2(-s * 0.5, -s * 0.18), center + Vector2(-s * 0.7, -s * 0.38), center + Vector2(-s * 0.7, s * 0.38),
				center + Vector2(-s * 0.5, s * 0.18), center + Vector2(s * 0.3, s * 0.18)])
			c.draw_colored_polygon(pts, color)
		"streu":
			for a in [-0.45, -0.22, 0.0, 0.22, 0.45]:
				var d := Vector2(cos(a), sin(a))
				c.draw_line(center - Vector2(s * 0.55, 0), center - Vector2(s * 0.55, 0) + d * s * 1.15, color, 2.0, true)
		_:
			for y in [-0.18, 0.18]:
				c.draw_line(center + Vector2(-s * 0.7, y * s), center + Vector2(s * 0.7, y * s), color, 3.0, true)


func draw_overlay(c: Control) -> void:
	if camera == null or done:
		return
	var vp := c.get_viewport_rect().size
	var u := vp.y / 720.0
	var t := Time.get_ticks_msec() / 1000.0
	# Treffer: roter Bildrand
	if flash > 0.0:
		var a := clampf(flash * 1.8, 0, 0.7)
		var e := 140.0 * u
		var clear := Color(1, 0.1, 0.1, 0.0)
		var red := Color(1, 0.1, 0.1, a)
		for quad in [[Vector2.ZERO, Vector2(vp.x, 0), Vector2(vp.x - e, e), Vector2(e, e)],
				[Vector2(0, vp.y), Vector2(e, vp.y - e), Vector2(vp.x - e, vp.y - e), vp],
				[Vector2.ZERO, Vector2(e, e), Vector2(e, vp.y - e), Vector2(0, vp.y)],
				[Vector2(vp.x, 0), vp, Vector2(vp.x - e, vp.y - e), Vector2(vp.x - e, e)]]:
			c.draw_polygon(PackedVector2Array(quad), PackedColorArray([red, red, clear, clear]))
	if landed.is_empty():
		draw_targets(c, vp, u, t)
		draw_reticle(c, vp, u, t)
	draw_status(c, vp, u, t)
	draw_score(c, vp, u)
	draw_radar(c, vp, u, t)
	draw_weapons(c, vp, u)
	draw_speed(c, vp, u, t)


func draw_reticle(c: Control, vp: Vector2, u: float, t: float) -> void:
	var col := HUD_RED if not aim_target.is_empty() else Color(HUD_CYAN, 0.95)
	var steps := [[160.0, 15.0], [55.0, 9.0]]
	for i in steps.size():
		var p := ship.global_position + forward() * float(steps[i][0])
		if camera.is_position_behind(p):
			continue
		var sp := camera.unproject_position(p)
		var r := float(steps[i][1]) * u
		if i == 0:
			for k in 4:
				var a := k * PI / 2 + PI / 4
				var d := Vector2(cos(a), sin(a))
				var n := d.orthogonal()
				c.draw_polyline(PackedVector2Array([sp + d * r * 1.6 + n * r * 0.6, sp + d * r, sp + d * r * 1.6 - n * r * 0.6]), col, 2.0 * u, true)
			c.draw_circle(sp, 2.2 * u, col)
			# Nachladen der Waffe als Bogen
			var w: Dictionary = weapons[weapon_i]
			var wait := clampf(cooldown / maxf(0.01, float(w.get("cooldown", 0.3))), 0, 1)
			if wait > 0.0:
				c.draw_arc(sp, r * 2.1, -PI / 2, -PI / 2 + TAU * (1.0 - wait), 32, Color(String(w.get("color", "#ffffff")), 0.9), 2.0 * u, true)
		else:
			c.draw_rect(Rect2(sp - Vector2(r, r), Vector2(r, r) * 2), Color(col, 0.55), false, 1.5 * u)
	# Zielerfassung: drehende Raute um das erfasste Ziel
	if not aim_target.is_empty():
		var tp: Vector3 = (aim_target["node"] as Node3D).global_position
		if not camera.is_position_behind(tp):
			var sp2 := camera.unproject_position(tp)
			var rr := 30.0 * u
			var pts := PackedVector2Array()
			for k in 5:
				var a := t * 2.0 + k * PI / 2
				pts.append(sp2 + Vector2(cos(a), sin(a)) * rr)
			c.draw_polyline(pts, HUD_RED, 2.0 * u, true)
			hud_text(c, sp2 + Vector2(rr + 8 * u, -rr), "ERFASST", int(13 * u), HUD_RED)


func draw_targets(c: Control, vp: Vector2, u: float, t: float) -> void:
	for e in enemies:
		var p: Vector3 = (e["node"] as Node3D).global_position
		var dist := p.distance_to(ship.global_position)
		var col := HUD_RED if e["hit"] <= 0.0 else Color.WHITE
		var on_screen := not camera.is_position_behind(p) and Rect2(Vector2.ZERO, vp).has_point(camera.unproject_position(p))
		if not on_screen:
			var local := camera.global_transform.affine_inverse() * p
			var dir := Vector2(local.x, -local.y).normalized()
			if dir == Vector2.ZERO:
				dir = Vector2.DOWN
			var edge := vp * 0.5 + dir * Vector2(vp.x * 0.45, vp.y * 0.4).length() * 0.75
			edge = edge.clamp(Vector2(40, 40) * u, vp - Vector2(40, 40) * u)
			var side := dir.orthogonal() * 8.0 * u
			c.draw_colored_polygon(PackedVector2Array([edge + dir * 16.0 * u, edge + side, edge - side]), Color(col, 0.85))
			continue
		var sp := camera.unproject_position(p)
		var s := clampf(1800.0 * float(e["radius"]) / maxf(dist, 1.0), 12.0, 110.0) * u
		var k := s * 0.45
		for corner in [Vector2(-1, -1), Vector2(1, -1), Vector2(1, 1), Vector2(-1, 1)]:
			var q: Vector2 = sp + corner * s
			c.draw_polyline(PackedVector2Array([q - Vector2(corner.x * k, 0), q, q - Vector2(0, corner.y * k)]), col, 1.8 * u)
		var frac := float(e["hp"]) / float(e["max"])
		var segs := mini(int(e["max"]), 10)
		seg_bar(c, sp + Vector2(-s, s + 6 * u), s * 2.0, 5 * u, frac, col, maxi(segs, 3))
		hud_text(c, sp + Vector2(s + 6 * u, -s + 12 * u), "%d" % roundi(dist), int(13 * u), Color(col, 0.9))
	if landed.is_empty():
		for b in bases:
			mark(c, vp, b["pos"], String(b["name"]), HUD_GREEN, u)
		for p in planets:
			if p["landable"]:
				mark(c, vp, p["pos"], String(p["name"]), HUD_AMBER, u)


func mark(c: Control, vp: Vector2, p: Vector3, text: String, color: Color, u: float) -> void:
	if camera.is_position_behind(p):
		return
	var sp := camera.unproject_position(p)
	if not Rect2(Vector2.ZERO, vp).has_point(sp):
		return
	var dist := p.distance_to(ship.global_position)
	var r := 7.0 * u
	c.draw_polyline(PackedVector2Array([sp + Vector2(0, -r), sp + Vector2(r, 0), sp + Vector2(0, r), sp + Vector2(-r, 0), sp + Vector2(0, -r)]), Color(color, 0.85), 1.5 * u, true)
	hud_text(c, sp + Vector2(12, 5) * u, "%s  %d m" % [text.to_upper(), roundi(dist)], int(13 * u), Color(color, 0.85))


func draw_status(c: Control, vp: Vector2, u: float, t: float) -> void:
	var r := Rect2(Vector2(22, 20) * u, Vector2(370, 96) * u)
	cut_panel(c, r, 14 * u, HUD_BG, Color(HUD_CYAN, 0.35))
	var hk := hull / maxf(1.0, max_hull)
	var hcol := HUD_RED.lerp(HUD_AMBER, clampf(hk * 2.0, 0, 1)).lerp(HUD_GREEN, clampf(hk * 2.0 - 1.0, 0, 1))
	var blink := hk < 0.25 and fmod(t, 0.6) < 0.3
	ship_glyph(c, r.position + Vector2(46, 46) * u, 26 * u, HUD_RED if blink else hcol)
	if shield > 0.0:
		c.draw_arc(r.position + Vector2(46, 50) * u, 38 * u, PI * 1.1, PI * 1.9, 24, Color("#6fa8ff", 0.35 + 0.5 * shield / maxf(1.0, max_shield)), 3 * u, true)
	var x := r.position.x + 96 * u
	hud_text(c, Vector2(x, r.position.y + 24 * u), "SCHILD", int(13 * u), HUD_DIM)
	hud_text(c, Vector2(r.end.x - 14 * u, r.position.y + 24 * u), "%d%%" % roundi(100.0 * shield / maxf(1.0, max_shield)), int(14 * u), Color("#9cc4ff"), HORIZONTAL_ALIGNMENT_RIGHT)
	seg_bar(c, Vector2(x, r.position.y + 30 * u), 255 * u, 10 * u, shield / maxf(1.0, max_shield), Color("#6fa8ff"), 20)
	hud_text(c, Vector2(x, r.position.y + 62 * u), "HÜLLE", int(13 * u), HUD_DIM)
	hud_text(c, Vector2(r.end.x - 14 * u, r.position.y + 62 * u), "%d%%" % roundi(100.0 * hk), int(14 * u), hcol, HORIZONTAL_ALIGNMENT_RIGHT)
	seg_bar(c, Vector2(x, r.position.y + 68 * u), 255 * u, 10 * u, hk, hcol, 20)
	for i in maxi(0, lives):
		ship_glyph(c, Vector2(r.position.x + (14 + i * 22) * u, r.end.y + 18 * u), 8 * u, Color(HUD_CYAN, 0.9))
	if hk < 0.25 and landed.is_empty():
		if blink:
			hud_text(c, Vector2(vp.x * 0.5, vp.y * 0.5 + 90 * u), "WARNUNG · HÜLLE KRITISCH", int(20 * u), HUD_RED, HORIZONTAL_ALIGNMENT_CENTER)
	elif hk < 0.5 and landed.is_empty():
		hud_text(c, Vector2(r.position.x + 96 * u, r.end.y + 22 * u), "SCHADEN · RAUMBASIS ANFLIEGEN", int(13 * u), HUD_AMBER)


func draw_score(c: Control, vp: Vector2, u: float) -> void:
	var right := vp.x - 26 * u
	hud_text(c, Vector2(right, 34 * u), "PUNKTE", int(13 * u), HUD_DIM, HORIZONTAL_ALIGNMENT_RIGHT)
	hud_text(c, Vector2(right, 72 * u), "%06d" % points, int(36 * u), Color("#ffd24a"), HORIZONTAL_ALIGNMENT_RIGHT)
	var y := 98.0 * u
	if total_enemies > 0:
		hud_text(c, Vector2(right, y), "FEINDE  %d / %d" % [total_enemies - enemies.size(), total_enemies], int(15 * u), HUD_RED, HORIZONTAL_ALIGNMENT_RIGHT)
		y += 22 * u
	hud_text(c, Vector2(right, y), String(data.get("name", "")).to_upper(), int(13 * u), HUD_DIM, HORIZONTAL_ALIGNMENT_RIGHT)
	var goals := {"gegner": "ZIEL: ALLE FEINDE ZERSTÖREN", "landen": "ZIEL: LANDEN AUF %s" % (goal_target.to_upper() if goal_target != "" else "EINEM PLANETEN"),
		"basis": "ZIEL: RAUMBASIS %s ERREICHEN" % goal_target.to_upper()}
	if goals.has(goal):
		hud_text(c, Vector2(right, y + 18 * u), ("✓ " if goal_reached else "") + String(goals[goal]), int(13 * u), HUD_GREEN if goal_reached else HUD_CYAN, HORIZONTAL_ALIGNMENT_RIGHT)


func draw_radar(c: Control, vp: Vector2, u: float, t: float) -> void:
	var r := 76.0 * u
	var center := Vector2(28 * u + r, vp.y - 26 * u - r)
	c.draw_circle(center, r, HUD_BG)
	c.draw_arc(center, r, 0, TAU, 64, Color(HUD_CYAN, 0.45), 1.5 * u, true)
	c.draw_arc(center, r * 0.5, 0, TAU, 48, Color(HUD_CYAN, 0.15), 1.0, true)
	c.draw_line(center - Vector2(r, 0), center + Vector2(r, 0), Color(HUD_CYAN, 0.12))
	c.draw_line(center - Vector2(0, r), center + Vector2(0, r), Color(HUD_CYAN, 0.12))
	var sweep := fmod(t * 1.6, TAU)
	for k in 10:
		c.draw_line(center, center + Vector2(cos(sweep - k * 0.05), sin(sweep - k * 0.05)) * r, Color(HUD_CYAN, 0.16 - k * 0.015), 2.0 * u)
	var range_ := 900.0
	var inv := ship.global_basis.inverse()
	var dots := []
	for e in enemies:
		dots.append([(e["node"] as Node3D).global_position, HUD_RED, 3.5])
	for b in bases:
		dots.append([b["pos"], HUD_GREEN, 4.5])
	for p in planets:
		dots.append([p["pos"], HUD_AMBER, 3.0 + float(p["radius"]) / 60.0])
	for d in dots:
		var l: Vector3 = inv * ((d[0] as Vector3) - ship.global_position)
		var v := Vector2(l.x, l.z) / range_ * r
		var col: Color = d[1]
		if v.length() > r - 4 * u:
			v = v.normalized() * (r - 4 * u)
			col.a = 0.5
		var size := float(d[2]) * u
		c.draw_circle(center + v, size, col)
		if l.y > 30.0:
			c.draw_line(center + v + Vector2(0, -size - 2), center + v + Vector2(0, -size - 6 * u), col, 1.5)
		elif l.y < -30.0:
			c.draw_line(center + v + Vector2(0, size + 2), center + v + Vector2(0, size + 6 * u), col, 1.5)
	c.draw_colored_polygon(PackedVector2Array([center + Vector2(0, -7) * u, center + Vector2(5, 5) * u, center + Vector2(-5, 5) * u]), HUD_CYAN)
	hud_text(c, center + Vector2(-r, -r - 6 * u), "RADAR", int(12 * u), HUD_DIM, HORIZONTAL_ALIGNMENT_LEFT)


func draw_weapons(c: Control, vp: Vector2, u: float) -> void:
	var n := weapons.size()
	var w := 138.0 * u
	var h := 46.0 * u
	var gap := 8.0 * u
	var total := n * w + (n - 1) * gap
	var x0 := vp.x * 0.5 - total * 0.5
	var y := vp.y - 26 * u - h
	for i in n:
		var wd: Dictionary = weapons[i]
		var col := Color(String(wd.get("color", "#ffffff")))
		var active := i == weapon_i
		var r := Rect2(Vector2(x0 + i * (w + gap), y - (8 * u if active else 0.0)), Vector2(w, h))
		c.draw_colored_polygon(slant(r, 12 * u), Color(col, 0.22) if active else HUD_BG)
		var pts := slant(r, 12 * u)
		pts.append(pts[0])
		c.draw_polyline(pts, col if active else Color(HUD_DIM, 0.4), (2.0 if active else 1.0) * u, true)
		if active:
			# Nachladebalken unten
			var wait := clampf(cooldown / maxf(0.01, float(wd.get("cooldown", 0.3))), 0, 1)
			c.draw_rect(Rect2(r.position + Vector2(6 * u, h - 5 * u), Vector2((w - 24 * u) * (1.0 - wait), 3 * u)), col)
		weapon_glyph(c, r.position + Vector2(32, h * 0.5 / u) * u, String(wd.get("type", "laser")), col if active else HUD_DIM, 20 * u)
		hud_text(c, r.position + Vector2(56, 20) * u, String(wd.get("name", "")).to_upper().left(11), int((13 if active else 12) * u), Color.WHITE if active else HUD_DIM)
		var sub := "∞"
		if ammo.has(i):
			sub = "× %d" % int(ammo[i])
		hud_text(c, r.position + Vector2(56, 38) * u, sub, int(13 * u), (HUD_RED if ammo.has(i) and int(ammo[i]) == 0 else col) if active else HUD_DIM)
		hud_text(c, r.position + Vector2(w - 6 * u, -4 * u), str(i + 1), int(12 * u), HUD_DIM, HORIZONTAL_ALIGNMENT_RIGHT, false)


func draw_speed(c: Control, vp: Vector2, u: float, t: float) -> void:
	var r := 70.0 * u
	var center := Vector2(vp.x - 30 * u - r, vp.y - 30 * u - r)
	c.draw_circle(center, r + 6 * u, HUD_BG)
	var a0 := PI * 0.75
	var span := PI * 1.5
	var k := clampf(speed / maxf(1.0, max_speed * boost), 0, 1)
	var col := HUD_AMBER if boosting else (HUD_RED if braking else HUD_CYAN)
	c.draw_arc(center, r, a0, a0 + span, 48, Color(HUD_DIM, 0.25), 7 * u, true)
	c.draw_arc(center, r, a0, a0 + span * k, 48, col, 7 * u, true)
	# Schubhebel als kleine Marke
	var ta := a0 + span * (0.12 + 0.88 * throttle) / boost
	c.draw_line(center + Vector2(cos(ta), sin(ta)) * (r - 10 * u), center + Vector2(cos(ta), sin(ta)) * (r + 8 * u), Color.WHITE, 2 * u)
	c.draw_arc(center, r - 13 * u, a0, a0 + span * boost_energy, 40, Color(HUD_AMBER, 0.45 if boost_blocked else 0.95), 4 * u, true)
	hud_text(c, center + Vector2(0, 8 * u), "%d" % roundi(speed), int(32 * u), col, HORIZONTAL_ALIGNMENT_CENTER)
	hud_text(c, center + Vector2(0, 28 * u), "M/S", int(12 * u), HUD_DIM, HORIZONTAL_ALIGNMENT_CENTER)
	var state := "BOOST" if boosting else ("BREMSE" if braking else ("BOOST LÄDT" if boost_blocked else ""))
	if state != "":
		hud_text(c, center + Vector2(0, r + 2 * u), state, int(15 * u), col if state != "BOOST LÄDT" else HUD_DIM, HORIZONTAL_ALIGNMENT_CENTER)


# ---- Schießen -------------------------------------------------------------------------------
func fire() -> void:
	if cooldown > 0.0 or not landed.is_empty():
		return
	var w: Dictionary = weapons[weapon_i]
	if ammo.has(weapon_i):
		if int(ammo[weapon_i]) <= 0:
			show_message("Keine %s mehr – an einer Basis auffüllen" % String(w.get("name", "Munition")), 1.5)
			cooldown = 0.4
			return
		ammo[weapon_i] = int(ammo[weapon_i]) - 1
		update_weapons()
	cooldown = float(w.get("cooldown", 0.3))
	var type := String(w.get("type", "laser"))
	var dir := forward()
	if not aim_target.is_empty():
		var tn: Node3D = aim_target["node"]
		var to := tn.global_position - ship.global_position
		dir = (to + aim_target.get("vel", Vector3.ZERO) * (to.length() / float(w.get("speed", 400)))).normalized()
	var base := ship.global_position + forward() * 3.5
	var color := Color(String(w.get("color", "#ff5d6c")))
	var spd := float(w.get("speed", 400)) + speed
	if type == "streu":
		for a in [-0.06, -0.03, 0.0, 0.03, 0.06]:
			var d := dir.rotated(ship.global_basis.y, a)
			spawn_shot(base, d * spd, float(w.get("damage", 1)), "spieler", "laser", color, {})
	elif type == "rakete":
		spawn_shot(base + ship.global_basis.y * -0.6, dir * spd, float(w.get("damage", 6)), "spieler", "rakete", color, aim_target)
	else:
		for x in [-0.6, 0.6] if type == "laser" else [0.0]:
			spawn_shot(base + ship.global_basis.x * x, dir * spd, float(w.get("damage", 1)), "spieler", type, color, {})


func spawn_shot(p: Vector3, vel: Vector3, dmg: float, team: String, type: String, color: Color, target: Dictionary) -> void:
	var mi := MeshInstance3D.new()
	if type == "plasma":
		var sm := SphereMesh.new()
		sm.radius = 0.9
		sm.height = 1.8
		mi.mesh = sm
	elif type == "rakete":
		var cm := CylinderMesh.new()
		cm.top_radius = 0.18
		cm.bottom_radius = 0.28
		cm.height = 1.6
		mi.mesh = cm
	else:
		var bm := BoxMesh.new()
		bm.size = Vector3(0.18, 0.18, 4.0)
		mi.mesh = bm
	mi.material_override = mat(color, 5.0, 0.2, 0.0)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)
	mi.global_position = p
	orient(mi, vel, type == "rakete")
	shots.append({"node": mi, "vel": vel, "life": 3.5 if type != "rakete" else 6.0, "dmg": dmg, "team": team,
		"type": type, "target": target, "color": color})


func orient(n: Node3D, vel: Vector3, cylinder := false) -> void:
	if vel.length() < 0.01:
		return
	var up := Vector3.UP if absf(vel.normalized().y) < 0.95 else Vector3.RIGHT
	n.global_basis = Basis.looking_at(vel, up)
	if cylinder:
		n.rotate_object_local(Vector3.RIGHT, PI / 2)


func blast(p: Vector3, size: float, color := Color("#ffb347")) -> void:
	var mi := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = 1.0
	sm.height = 2.0
	sm.radial_segments = 16
	sm.rings = 8
	mi.mesh = sm
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_color = color
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	mi.material_override = m
	add_child(mi)
	mi.global_position = p
	mi.scale = Vector3.ONE * size * 0.2
	blasts.append({"node": mi, "t": 0.0, "size": size, "mat": m})


func update_shots(delta: float) -> void:
	for i in range(shots.size() - 1, -1, -1):
		var s: Dictionary = shots[i]
		var n: Node3D = s["node"]
		s["life"] -= delta
		if s["type"] == "rakete" and not (s["target"] as Dictionary).is_empty() and enemies.has(s["target"]):
			var tn: Node3D = s["target"]["node"]
			var want: Vector3 = (tn.global_position - n.global_position).normalized() * (s["vel"] as Vector3).length()
			s["vel"] = (s["vel"] as Vector3).lerp(want, clampf(delta * 2.5, 0, 1))
			orient(n, s["vel"], true)
		n.global_position += s["vel"] * delta
		var hit := false
		var p := n.global_position
		if s["team"] == "spieler":
			for e in enemies:
				var en: Node3D = e["node"]
				if en.global_position.distance_to(p) < float(e["radius"]) + 0.8:
					damage_enemy(e, float(s["dmg"]))
					hit = true
					break
		elif s["team"] == "gegner" and ship.global_position.distance_to(p) < 2.6 and landed.is_empty():
			if not maneuver.is_empty() and maneuver["kind"] == "rolle":
				# Fassrolle: Schuss prallt ab
				s["vel"] = ((s["vel"] as Vector3).bounce(((p - ship.global_position).normalized())))
				s["team"] = "abgeprallt"
				if autotest and not test_said.has("abgeprallt"):
					test_said["abgeprallt"] = true
					print("AUTOTEST: Schuss abgeprallt")
			else:
				hurt(float(s["dmg"]))
				hit = true
		if not hit:
			for pl in planets:
				if (pl["pos"] as Vector3).distance_to(p) < float(pl["radius"]):
					hit = true
					break
		if not hit:
			for r in rocks:
				if (r["node"] as Node3D).global_position.distance_to(p) < float(r["radius"]):
					hit = true
					break
		if hit:
			blast(p, 2.5 if s["type"] != "rakete" else 7.0, s["color"])
		if hit or s["life"] <= 0.0:
			n.queue_free()
			shots.remove_at(i)


func update_blasts(delta: float) -> void:
	for i in range(blasts.size() - 1, -1, -1):
		var b: Dictionary = blasts[i]
		b["t"] += delta
		var k: float = b["t"] / 0.55
		var n: Node3D = b["node"]
		n.scale = Vector3.ONE * float(b["size"]) * (0.2 + k)
		var m: StandardMaterial3D = b["mat"]
		m.albedo_color.a = clampf(1.0 - k, 0, 1)
		if k >= 1.0:
			n.queue_free()
			blasts.remove_at(i)


# ---- Schaden --------------------------------------------------------------------------------
func damage_enemy(e: Dictionary, dmg: float) -> void:
	e["hp"] = int(e["hp"]) - int(maxf(1.0, dmg))
	e["hit"] = 0.12
	if autotest and not test_said.has("treffer"):
		test_said["treffer"] = true
		print("AUTOTEST: Treffer auf ", e["name"])
	if int(e["hp"]) <= 0:
		var n: Node3D = e["node"]
		blast(n.global_position, float(e["radius"]) * 2.5)
		blast(n.global_position, float(e["radius"]) * 1.4, Color("#fff3c4"))
		n.queue_free()
		enemies.erase(e)
		kills += 1
		points += int(e["info"]["points"])
		show_message("%s zerstört  +%d" % [e["name"], int(e["info"]["points"])], 1.6)
		if autotest:
			print("AUTOTEST: Gegner zerstört ", kills, "/", total_enemies)
		update_hud()
		check_goal()


func hurt(dmg: float) -> void:
	if done or invulnerable > 0.0:
		return
	var rest := dmg
	if shield > 0.0:
		var taken := minf(shield, rest)
		shield -= taken
		rest -= taken
	hull -= rest
	shield_wait = 3.0
	flash = 0.35 if rest > 0.0 else 0.15
	if autotest and not test_said.has("schaden"):
		test_said["schaden"] = true
		print("AUTOTEST: Schaden genommen, Schild %d Hülle %d" % [shield, hull])
	if hull <= 0.0:
		hull = 0.0
		lose_life()
	update_hud()


func lose_life() -> void:
	blast(ship.global_position, 10.0)
	lives -= 1
	if lives <= 0:
		done = true
		ship.visible = false
		update_hud()
		if autotest:
			print("AUTOTEST: Schiff zerstört – Game Over")
		get_tree().create_timer(1.5).timeout.connect(func(): game_over.emit())
		return
	show_message("Schiff zerstört – neues Schiff", 2.0)
	ship.global_position = spawn_pos
	ship.global_basis = spawn_basis
	hull = max_hull
	shield = max_shield
	invulnerable = 2.5
	throttle = 0.4


# ---- Gegner-KI ------------------------------------------------------------------------------
func update_enemies(delta: float) -> void:
	var me := ship.global_position
	var visible_ship := landed.is_empty() and not done
	for e in enemies:
		var n: Node3D = e["node"]
		var info: Dictionary = e["info"]
		e["hit"] = maxf(0.0, float(e["hit"]) - delta)
		e["cd"] = float(e["cd"]) - delta
		var to := me - n.global_position
		var dist := to.length()
		var alert := visible_ship and dist < float(info["range"]) * 1.6
		var want: Vector3
		var spd: float = e["speed"]
		var before := n.global_position
		if e["type"] == "geschuetz":
			want = to if alert else -n.global_basis.z
		elif not alert:
			# Streife: Kreis um den Startpunkt
			e["angle"] = float(e["angle"]) + delta * 0.25
			var home: Vector3 = e["home"]
			var target := home + Vector3(cos(e["angle"]), 0, sin(e["angle"])) * 60.0
			want = target - n.global_position
			spd *= 0.5
		elif float(e["evade"]) > 0.0:
			e["evade"] = float(e["evade"]) - delta
			want = -to + n.global_basis.x * 40.0 + Vector3.UP * 15.0
		else:
			want = to
			if dist < float(e["radius"]) * 6.0 + 18.0 and e["type"] == "jaeger":
				e["evade"] = 1.6
			if dist < 70.0 and e["type"] == "kreuzer":
				spd = 0.0
		if want.length() > 0.01:
			var up := Vector3.UP if absf(want.normalized().y) < 0.95 else Vector3.RIGHT
			var q := Quaternion(n.global_basis.orthonormalized()).slerp(Quaternion(Basis.looking_at(want, up)), clampf(float(info["turn"]) * delta, 0, 1))
			n.global_basis = Basis(q)
		n.global_position += -n.global_basis.z * spd * delta
		e["vel"] = (n.global_position - before) / maxf(delta, 0.0001)
		# eigenes Schiff zu nahe: Zusammenstoß
		if visible_ship and dist < float(e["radius"]) + 2.0:
			hurt(25.0)
			damage_enemy(e, 3)
			if not enemies.has(e):
				break
		if alert and float(e["cd"]) <= 0.0 and dist < float(info["range"]):
			var fwd := -n.global_basis.z
			var aligned := fwd.dot(to.normalized()) > (0.6 if e["type"] != "jaeger" else 0.93)
			if aligned:
				var wtype := String(e["weapon"])
				var bspeed := 260.0 if wtype != "plasma" else 150.0
				var lead := to + forward() * speed * (dist / bspeed)
				var spread := Vector3(randf_range(-1, 1), randf_range(-1, 1), randf_range(-1, 1)) * dist * 0.03
				var dir := (lead + spread).normalized()
				var col := Color("#ff6b4a") if wtype != "plasma" else Color("#c86bff")
				spawn_shot(n.global_position + fwd * (float(e["radius"]) + 1.0), dir * bspeed,
					float(ENEMY_DAMAGE.get(wtype, 6.0)), "gegner", wtype, col, {})
				e["cd"] = float(info["cooldown"]) * randf_range(0.8, 1.3)
		if e["hit"] > 0.0:
			n.scale = Vector3.ONE * 1.08
		else:
			n.scale = Vector3.ONE


# ---- Planeten, Basen, Landen ----------------------------------------------------------------
func update_places(delta: float) -> void:
	land_option = {}
	docked = {}
	var me := ship.global_position
	for p in planets:
		var d := me.distance_to(p["pos"]) - float(p["radius"])
		if d < 3.0:
			# Aufprall: zurückstoßen und Schaden
			var n: Vector3 = (me - (p["pos"] as Vector3)).normalized()
			ship.global_position = (p["pos"] as Vector3) + n * (float(p["radius"]) + 4.0)
			hurt(15.0)
			throttle = 0.15
			show_message("Zu schnell! L zum Landen drücken", 1.5)
		elif d < float(p["radius"]) * 0.6 + 40.0 and p["landable"]:
			land_option = p
	for b in bases:
		if me.distance_to(b["pos"]) < float(b["radius"]):
			docked = b
	for r in rocks:
		var rn: Node3D = r["node"]
		rn.rotate_object_local(Vector3(0.3, 1, 0.2).normalized(), delta * 0.2)
		if rn.global_position.distance_to(me) < float(r["radius"]) + 1.6:
			hurt(12.0)
			blast(me + forward() * 2.0, 3.0, Color("#c9b8a0"))
			var away: Vector3 = (me - rn.global_position).normalized()
			ship.global_position = rn.global_position + away * (float(r["radius"]) + 2.5)
	if not docked.is_empty():
		var slow := speed < max_speed * 0.4
		if slow:
			var rate: float = docked["rate"]
			var before := hull + shield
			hull = minf(max_hull, hull + rate * delta)
			shield = minf(max_shield, shield + rate * delta)
			for i in weapons.size():
				if weapons[i].has("ammo"):
					if int(ammo.get(i, 0)) < int(weapons[i]["ammo"]):
						ammo[i] = int(weapons[i]["ammo"])
						update_weapons()
			var full := hull >= max_hull and shield >= max_shield
			prompt.text = "%s · Reparatur %d %%" % [docked["name"], roundi(100.0 * hull / max_hull)] if not full else "%s · Schiff repariert ✓" % docked["name"]
			if before < max_hull + max_shield and full:
				show_message("Schiff vollständig repariert", 2.0)
				if autotest:
					print("AUTOTEST: Repariert an ", docked["name"], ", Hülle ", roundi(hull))
			if full and goal == "basis" and (goal_target == "" or goal_target == docked["name"]):
				reach_goal()
			update_hud()
		else:
			prompt.text = "%s · langsamer fliegen (S) zum Andocken" % docked["name"]
	elif not land_option.is_empty():
		prompt.text = "L – Landen auf %s" % land_option["name"]
	else:
		prompt.text = ""


func land(p: Dictionary) -> void:
	landed = p
	world.visible = false
	for s in shots:
		(s["node"] as Node3D).queue_free()
	shots.clear()
	surface = Node3D.new()
	add_child(surface)
	var e: Dictionary = p["data"]
	var ground_c := Color(String(e.get("ground", e.get("color", "#c8673a"))))
	var air := Color(String(e.get("atmosphere", "")) if String(e.get("atmosphere", "")) != "" else "#d9a07a")
	var senv := Environment.new()
	var sky := Sky.new()
	var ps := ProceduralSkyMaterial.new()
	ps.sky_top_color = air.darkened(0.35)
	ps.sky_horizon_color = air.lightened(0.25)
	ps.ground_horizon_color = ground_c.lightened(0.2)
	ps.ground_bottom_color = ground_c.darkened(0.4)
	sky.sky_material = ps
	senv.background_mode = Environment.BG_SKY
	senv.sky = sky
	senv.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	senv.ambient_light_energy = 0.8
	senv.fog_enabled = true
	senv.fog_light_color = air.lightened(0.2)
	senv.fog_density = 0.004
	senv.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	(get_node("Umgebung") as WorldEnvironment).environment = senv
	var gnd := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(3000, 3000)
	pm.subdivide_width = 1
	gnd.mesh = pm
	gnd.material_override = planet_material(ground_c, ground_c.darkened(0.3), 0.004, 0.0)
	surface.add_child(gnd)
	var rng := RandomNumberGenerator.new()
	rng.seed = String(p["name"]).hash()
	var rock_mat := mat(ground_c.darkened(0.25), 0.0, 1.0, 0.0)
	for i in 70:
		var r := MeshInstance3D.new()
		var sm := SphereMesh.new()
		var size := rng.randf_range(1.0, 9.0)
		sm.radius = size
		sm.height = size * 1.4
		sm.radial_segments = 8
		sm.rings = 5
		r.mesh = sm
		r.material_override = rock_mat
		var ang := rng.randf() * TAU
		var dd := rng.randf_range(25.0, 600.0)
		r.position = Vector3(cos(ang) * dd, size * 0.2, sin(ang) * dd)
		surface.add_child(r)
	# Landeplatz
	var pad := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 9
	cm.bottom_radius = 9.5
	cm.height = 0.4
	pad.mesh = cm
	pad.material_override = mat(Color("#5b6270"), 0.0, 0.6, 0.6)
	surface.add_child(pad)
	for i in 8:
		var l := MeshInstance3D.new()
		var ls := SphereMesh.new()
		ls.radius = 0.35
		ls.height = 0.7
		l.mesh = ls
		l.position = Vector3(cos(i * TAU / 8) * 8.6, 0.4, sin(i * TAU / 8) * 8.6)
		l.material_override = mat(Color("#ffd24a"), 4.0)
		surface.add_child(l)
	ship.global_position = Vector3(0, 1.6, 0)
	ship.global_basis = Basis.IDENTITY
	speed = 0.0
	throttle = 0.0
	prompt.text = "Gelandet auf %s · L zum Starten" % p["name"]
	show_message("Willkommen auf %s" % p["name"], 3.0)
	if autotest:
		print("AUTOTEST: Gelandet auf ", p["name"])
	if goal == "landen" and (goal_target == "" or goal_target == p["name"]):
		reach_goal()


func take_off() -> void:
	var p := landed
	landed = {}
	if surface:
		surface.queue_free()
		surface = null
	world.visible = true
	(get_node("Umgebung") as WorldEnvironment).environment = space_env
	var n := Vector3.UP
	if spawn_pos.distance_to(p["pos"]) > 1.0:
		n = (spawn_pos - (p["pos"] as Vector3)).normalized()
	ship.global_position = (p["pos"] as Vector3) + n * (float(p["radius"]) * 1.25 + 30.0)
	ship.global_basis = Basis.looking_at(n, Vector3.UP if absf(n.y) < 0.95 else Vector3.FORWARD)
	throttle = 0.5
	camera.global_transform = chase_transform()
	show_message("Gestartet von %s" % p["name"], 2.0)


func reach_goal() -> void:
	if goal_reached:
		return
	goal_reached = true
	show_message("Ziel erreicht!", 3.0)
	if autotest:
		print("AUTOTEST: Ziel erreicht (", goal, ")")
		return                  # der Autopilot testet erst alles fertig
	finish_wait = 2.5


func check_goal() -> void:
	if goal == "gegner" and enemies.is_empty() and total_enemies > 0:
		reach_goal()


# ---- Eingabe und Ablauf ---------------------------------------------------------------------
func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("pause") and not done:
		set_paused(not get_tree().paused)
		return
	if get_tree().paused or done:
		return
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		mouse += (event as InputEventMouseMotion).relative
	if event is InputEventMouseButton and event.pressed and Input.mouse_mode != Input.MOUSE_MODE_CAPTURED and not autotest:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		return
	if event.is_action_pressed("waffe_weiter"):
		select_weapon((weapon_i + 1) % weapons.size())
	elif event.is_action_pressed("waffe_zurueck"):
		select_weapon((weapon_i - 1 + weapons.size()) % weapons.size())
	for i in mini(6, weapons.size()):
		if event.is_action_pressed("waffe%d" % (i + 1)):
			select_weapon(i)
	if landed.is_empty():
		if event.is_action_pressed("looping"):
			start_maneuver("looping")
		elif event.is_action_pressed("fassrolle_links"):
			start_maneuver("rolle", 1.0)
		elif event.is_action_pressed("fassrolle_rechts"):
			start_maneuver("rolle", -1.0)
	if event.is_action_pressed("landen"):
		if not landed.is_empty():
			take_off()
		elif not land_option.is_empty():
			land(land_option)


## Looping: das Schiff zieht in 1,6 s einen vollen Kreis nach oben. Fassrolle: schnelle Drehung um die
## Längsachse mit Ausweichen zur Seite – feindliche Schüsse prallen dabei ab.
func start_maneuver(kind: String, side := 1.0) -> void:
	if not maneuver.is_empty() or maneuver_wait > 0.0:
		return
	maneuver = {"kind": kind, "t": 0.0, "side": side, "dur": 1.7 if kind == "looping" else 0.55, "done": 0.0}
	if kind == "looping":
		shake = 0.25
	if autotest and not test_said.has(kind):
		test_said[kind] = true
		print("AUTOTEST: Manöver ", "Looping" if kind == "looping" else "Fassrolle")


func update_maneuver(delta: float) -> bool:
	## true, solange ein Manöver die Steuerung übernimmt
	maneuver_wait = maxf(0.0, maneuver_wait - delta)
	if maneuver.is_empty():
		return false
	var dur: float = maneuver["dur"]
	maneuver["t"] = minf(float(maneuver["t"]) + delta, dur)
	var k: float = maneuver["t"] / dur
	var eased := k * k * (3.0 - 2.0 * k)
	var step := eased - float(maneuver["done"])
	maneuver["done"] = eased
	if maneuver["kind"] == "looping":
		ship.rotate_object_local(Vector3.RIGHT, TAU * step)
		ship.global_basis = ship.global_basis.orthonormalized()
		speed = maxf(speed, max_speed * 0.9)
	else:
		ship_visual.rotation.z = float(maneuver["side"]) * TAU * eased
		ship.global_position += ship.global_basis.x * -float(maneuver["side"]) * 34.0 * step
	ship.global_position += forward() * speed * delta
	if k >= 1.0:
		if maneuver["kind"] == "rolle":
			ship_visual.rotation.z = 0.0
		maneuver = {}
		maneuver_wait = 0.25
	return true


func select_weapon(i: int) -> void:
	if i == weapon_i:
		return
	weapon_i = i
	cooldown = minf(cooldown, 0.15)
	update_weapons()
	show_message(String(weapons[i].get("name", "Waffe")), 0.9)


func fly(delta: float, input: Dictionary) -> void:
	var yaw: float = input["yaw"]
	var pitch: float = input["pitch"]
	var roll: float = input["roll"]
	throttle = clampf(throttle + float(input["throttle"]) * delta * 0.8, 0.0, 1.0)
	var target := max_speed * (0.12 + 0.88 * throttle)
	# Boost: kräftiger Schub, solange Energie da ist (danach erst wieder ab 30 %)
	var want_boost: bool = input["boost"] and not boost_blocked
	if want_boost and not boosting:
		boost_kick = 1.0
		shake = 0.5
	boosting = want_boost
	braking = float(input["throttle"]) < -0.1 and speed > target + 2.0
	if boosting:
		boost_energy -= delta / float(ship_cfg.get("boostTime", 4.0))
		if boost_energy <= 0.0:
			boost_energy = 0.0
			boost_blocked = true
			boosting = false
			show_message("Boost leer – lädt auf", 1.2)
		target = max_speed * boost
	else:
		boost_energy = minf(1.0, boost_energy + delta * 0.18)
		if boost_blocked and boost_energy >= 0.3:
			boost_blocked = false
	var rate := 3.2 if boosting else (3.5 if braking else 1.6)
	speed = lerpf(speed, target, clampf(delta * rate, 0, 1))
	boost_kick = maxf(0.0, boost_kick - delta * 2.2)
	ship.rotate_object_local(Vector3.UP, yaw * turn * delta)
	ship.rotate_object_local(Vector3.RIGHT, pitch * turn * delta)
	ship.rotate_object_local(Vector3.FORWARD, roll * turn * 1.4 * delta)
	ship.global_basis = ship.global_basis.orthonormalized()
	ship.global_position += forward() * speed * delta
	# Schiff neigt sich sichtbar in die Kurve, hebt beim Boost die Nase und nickt beim Bremsen nach vorn
	var lean := 0.12 if boosting else (-0.16 if braking else 0.0)
	ship_visual.rotation.z = lerpf(ship_visual.rotation.z, -yaw * 0.5 + roll * 0.25, clampf(delta * 5.0, 0, 1))
	ship_visual.rotation.x = lerpf(ship_visual.rotation.x, pitch * 0.15 + lean, clampf(delta * 5.0, 0, 1))
	var flame := speed / maxf(1.0, max_speed)
	for f in ship_visual.find_children("Flamme", "", true, false):
		var fn := f as Node3D
		fn.scale = Vector3.ONE * (1.6 if boosting else (0.6 if braking else 1.0)) + Vector3(0, 0, 1.0 + 3.0 * flame + boost_kick * 4.0)
		((fn as MeshInstance3D).material_override as StandardMaterial3D).albedo_color = \
			Color(1.0, 0.72, 0.38, 0.95) if boosting else Color(0.5, 0.75, 1.0, 0.9 if not braking else 0.4)
	for r in retro:
		(r as Node3D).visible = braking and speed > max_speed * 0.15
		(r as Node3D).scale = Vector3(1, 1, 1.5 + randf() * 1.2)


func player_input() -> Dictionary:
	var sens := float(ship_cfg.get("mouse", 1.0)) * 0.012
	var m := mouse * sens
	mouse = Vector2.ZERO
	var invert := -1.0 if ship_cfg.get("invertY", false) else 1.0
	return {
		"yaw": clampf(Input.get_axis("gieren_rechts", "gieren_links") - (m.x if ship_cfg.get("mouseSteer", true) else 0.0), -2.5, 2.5),
		"pitch": clampf(Input.get_axis("nicken_runter", "nicken_hoch") - (m.y * invert if ship_cfg.get("mouseSteer", true) else 0.0), -2.5, 2.5),
		"roll": Input.get_axis("rollen_rechts", "rollen_links"),
		"throttle": Input.get_axis("bremse", "schub"),
		"boost": Input.is_action_pressed("boost"),
		"fire": Input.is_action_pressed("feuer"),
	}


func find_aim_target() -> void:
	aim_target = {}
	var best := 0.985
	for e in enemies:
		var to: Vector3 = (e["node"] as Node3D).global_position - ship.global_position
		if to.length() > 700.0:
			continue
		var d := forward().dot(to.normalized())
		if d > best:
			best = d
			aim_target = e


func _process(delta: float) -> void:
	if get_tree().paused:
		return
	if message_time > 0.0:
		message_time -= delta
		message.modulate.a = clampf(message_time * 2.0, 0, 1)
	flash = maxf(0.0, flash - delta)
	if finish_wait > 0.0:
		finish_wait -= delta
		if finish_wait <= 0.0 and not done:
			done = true
			finished.emit(points)
			return
	if done:
		return
	cooldown = maxf(0.0, cooldown - delta)
	invulnerable = maxf(0.0, invulnerable - delta)
	ship_visual.visible = invulnerable <= 0.0 or fmod(invulnerable, 0.25) < 0.15
	var input := autopilot(delta) if autotest else player_input()
	if landed.is_empty():
		if not update_maneuver(delta):
			fly(delta, input)
		find_aim_target()
		if input["fire"]:
			fire()
		update_enemies(delta)
		update_places(delta)
		shield_wait -= delta
		if shield_wait <= 0.0 and shield < max_shield:
			shield = minf(max_shield, shield + 6.0 * delta)
			update_hud()
		camera.global_transform = camera.global_transform.interpolate_with(chase_transform(), clampf(delta * 7.0, 0, 1))
		speed_effects(delta)
	else:
		# gelandet: Kamera kreist langsam ums Schiff
		var t := Time.get_ticks_msec() / 1000.0
		var cp := ship.global_position + Vector3(cos(t * 0.15) * 16.0, 6.0, sin(t * 0.15) * 16.0)
		camera.global_transform = Transform3D(Basis.looking_at(ship.global_position - cp, Vector3.UP), cp)
	smoke.emitting = hull < max_hull * 0.5 and landed.is_empty()
	update_shots(delta)
	update_blasts(delta)
	update_horizon()
	overlay.queue_redraw()


# ---- Autotest: Autopilot fliegt Kampf → Basis → Landung -------------------------------------
func steer_to(target: Vector3, delta: float) -> float:
	var to := target - ship.global_position
	var local := ship.global_basis.inverse() * to.normalized()
	ship.global_basis = Basis(Quaternion(ship.global_basis.orthonormalized()).slerp(
		Quaternion(Basis.looking_at(to, Vector3.UP if absf(to.normalized().y) < 0.95 else Vector3.RIGHT)), clampf(delta * 2.0, 0, 1)))
	return local.z * -1.0


func autopilot(delta: float) -> Dictionary:
	test_time += delta
	phase_time += delta
	var input := {"yaw": 0.0, "pitch": 0.0, "roll": 0.0, "throttle": 0.0, "boost": false, "fire": false}
	if test_time > 75.0:
		print("AUTOTEST: Zeit um, Phase ", test_phase, " Hülle ", roundi(hull), " Punkte ", points)
		get_tree().quit(0)
		return input
	if test_phase == "kampf" and phase_time > 1.0 and not test_said.has("rolle"):
		start_maneuver("rolle", 1.0)
	if test_phase == "basis" and phase_time > 0.5 and not test_said.has("looping"):
		start_maneuver("looping")
	match test_phase:
		"kampf":
			if enemies.is_empty() or phase_time > 30.0:
				print("AUTOTEST: Kampf vorbei, zerstört ", kills, "/", total_enemies, ", Hülle ", roundi(hull))
				if weapon_i == 0 and weapons.size() > 2:
					pass
				next_phase("basis")
				return input
			# Waffen durchprobieren
			var want := int(phase_time / 4.0) % weapons.size()
			if want != weapon_i:
				select_weapon(want)
			var nearest: Dictionary = enemies[0]
			for e in enemies:
				if (e["node"] as Node3D).global_position.distance_to(ship.global_position) < (nearest["node"] as Node3D).global_position.distance_to(ship.global_position):
					nearest = e
			var tp: Vector3 = (nearest["node"] as Node3D).global_position
			var align := steer_to(tp, delta)
			var dist := tp.distance_to(ship.global_position)
			throttle = 0.6 if dist > 90.0 else 0.15
			input["fire"] = align > 0.97
		"basis":
			if bases.is_empty():
				next_phase("landen")
				return input
			if hull >= max_hull and not test_said.has("testschaden"):
				test_said["testschaden"] = true
				hurt(max_shield + 40.0)          # damit die Reparatur sicher etwas zu tun hat
			var b: Dictionary = bases[0]
			steer_to(b["pos"], delta)
			var dist := ship.global_position.distance_to(b["pos"])
			throttle = 0.9 if dist > 120.0 else 0.0
			if docked == b and hull >= max_hull and shield >= max_shield:
				next_phase("landen")
			elif phase_time > 30.0:
				print("AUTOTEST: Basis nicht erreicht, Abstand ", roundi(dist))
				next_phase("landen")
		"landen":
			var target: Dictionary = {}
			for p in planets:
				if p["landable"]:
					target = p
					break
			if target.is_empty():
				next_phase("ende")
				return input
			if not landed.is_empty():
				if phase_time > 3.0:
					take_off()
					next_phase("ende")
				return input
			steer_to(target["pos"], delta)
			throttle = 1.0
			input["boost"] = ship.global_position.distance_to(target["pos"]) > float(target["radius"]) + 300.0
			if land_option == target:
				land(target)
				phase_time = 0.0
		"ende":
			if phase_time > 1.0:
				print("AUTOTEST: Fertig, Punkte ", points, ", Hülle ", roundi(hull), ", Leben ", lives)
				done = true
				finished.emit(points)
	return input


func next_phase(p: String) -> void:
	test_phase = p
	phase_time = 0.0
	print("AUTOTEST: Phase ", p)
