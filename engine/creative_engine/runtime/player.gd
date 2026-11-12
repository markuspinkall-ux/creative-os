extends CharacterBody3D
## Spielfigur: laufen, springen (mit „Coyote Time“ und Sprungpuffer), Gegner von oben besiegen.

signal stomped(enemy: Node)
signal hit
signal attacked(attack: Dictionary)

const Assets = preload("res://assets.gd")

var run_speed := 7.0
var jump_speed := 12.0
var gravity := 32.0
var frozen := false
var invulnerable := 0.0
var autotest := false
var visual: Node3D
var anim: AnimationPlayer
var anims := {}
var coyote := 0.0
var buffer := 0.0
var facing := 1.0
var auto_jump := 0.0
var one_shot := 0.0
var cheering := false
var attacks: Array = []        # [{name, key, range, damage, cooldown}] – Bewegung: Platz „attack1“, „attack2“ …
var attack_wait := 0.0
var auto_attack := 0.0
var slash: MeshInstance3D


func build(model_path: String, model_height: float) -> void:
	var shape := CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.32
	cap.height = 1.5
	shape.shape = cap
	shape.position = Vector3(0, 0.75, 0)
	add_child(shape)
	axis_lock_linear_z = true
	floor_snap_length = 0.2
	visual = Node3D.new()
	add_child(visual)
	var model := Assets.fitted(model_path, model_height)
	if model:
		visual.add_child(model)
		anim = Assets.find_animator(model)
		# Feste Plätze aus dem Charakter-Editor (idle, walk, run, jump, fall, cheer, hit) –
		# fremde Modelle werden über ähnliche Namen zugeordnet.
		anims = {
			"idle": Assets.pick_animation(anim, ["idle", "stand", "breath", "wait"]),
			"walk": Assets.pick_animation(anim, ["walk", "jog", "move", "run"]),
			"run": Assets.pick_animation(anim, ["run", "sprint", "jog", "walk", "move"]),
			"jump": Assets.pick_animation(anim, ["jump", "air", "fall"]),
			"fall": Assets.pick_animation(anim, ["fall", "air", "jump"]),
			"cheer": Assets.pick_animation(anim, ["cheer", "victory", "win", "dance", "wave"]),
			"hit": Assets.pick_animation(anim, ["hit", "hurt", "damage"]),
		}
		for key in ["idle", "walk", "run", "fall", "cheer"]:
			Assets.set_loop(anim, anims[key], true)
		for key in ["jump", "hit"]:
			Assets.set_loop(anim, anims[key], false)
		for i in range(1, 7):
			var a := Assets.pick_animation(anim, ["attack%d" % i])
			if a == "" and i == 1:
				a = Assets.pick_animation(anim, ["attack", "punch", "slash", "kick"])
			anims["attack%d" % i] = a
			Assets.set_loop(anim, a, false)
	else:
		var body := MeshInstance3D.new()
		var cm := CapsuleMesh.new()
		cm.radius = 0.32
		cm.height = 1.5
		body.mesh = cm
		body.position = Vector3(0, 0.75, 0)
		var m := StandardMaterial3D.new()
		m.albedo_color = Color("#8fb3ff")
		body.material_override = m
		visual.add_child(body)
		var eye := MeshInstance3D.new()
		var sm := SphereMesh.new()
		sm.radius = 0.09
		sm.height = 0.18
		eye.mesh = sm
		eye.position = Vector3(0.2, 1.15, 0.22)
		var em := StandardMaterial3D.new()
		em.albedo_color = Color("#12151b")
		eye.material_override = em
		visual.add_child(eye)


func play(kind: String, speed := 1.0) -> void:
	if anim == null:
		return
	var a: String = anims.get(kind, "")
	if a == "":
		a = anims.get("idle", "")
	if a != "" and anim.current_animation != a:
		anim.play(a, 0.15)
	if a != "":
		anim.speed_scale = speed


## Sichtbarer „Hieb“ vor der Figur (auch ohne eigene Angriffsbewegung)
func show_slash(reach: float) -> void:
	if slash == null:
		slash = MeshInstance3D.new()
		var q := QuadMesh.new()
		q.size = Vector2(1, 1)
		slash.mesh = q
		var m := StandardMaterial3D.new()
		m.albedo_color = Color(1, 1, 1, 0.55)
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		slash.material_override = m
		add_child(slash)
	slash.visible = true
	slash.position = Vector3(facing * (0.3 + reach * 0.5), 0.95, 0.4)
	slash.scale = Vector3(reach * 0.4, 0.25, 1)
	var tw := create_tween()
	tw.tween_property(slash, "scale", Vector3(reach, 0.7, 1), 0.12)
	tw.tween_callback(func(): slash.visible = false).set_delay(0.06)


func start_attack(i: int) -> void:
	if i >= attacks.size() or attack_wait > 0.0 or frozen:
		return
	var a: Dictionary = attacks[i]
	attack_wait = float(a.get("cooldown", 0.4))
	var name_: String = anims.get("attack%d" % (i + 1), "")
	if anim and name_ != "":
		anim.play(name_, 0.08)
		anim.speed_scale = 1.0
		one_shot = minf(anim.current_animation_length, 1.2)
	show_slash(float(a.get("range", 1.5)))
	attacked.emit(a)


func celebrate() -> void:
	cheering = true
	frozen = true


func hurt_animation() -> void:
	if anim and anims.get("hit", "") != "":
		play("hit")
		one_shot = minf(0.6, anim.current_animation_length)


func respawn(at: Vector3) -> void:
	position = at
	velocity = Vector3.ZERO
	invulnerable = 1.5


func knockback() -> void:
	velocity = Vector3(-facing * 8.0, 8.0, 0)
	invulnerable = 1.5
	hurt_animation()


func _physics_process(delta: float) -> void:
	if frozen:
		velocity.x = move_toward(velocity.x, 0, 30 * delta)
		velocity.y -= gravity * delta
		move_and_slide()
		play("cheer" if cheering else "idle")
		return
	invulnerable = maxf(0.0, invulnerable - delta)
	attack_wait = maxf(0.0, attack_wait - delta)
	for i in attacks.size():
		if InputMap.has_action("angriff%d" % (i + 1)) and Input.is_action_just_pressed("angriff%d" % (i + 1)):
			start_attack(i)
	if autotest and not attacks.is_empty():
		auto_attack -= delta
		if auto_attack <= 0.0:
			auto_attack = 1.3
			start_attack(0)
	visual.visible = invulnerable <= 0.0 or int(invulnerable * 12) % 2 == 0
	var dir := Input.get_axis("links", "rechts")
	var want_jump := Input.is_action_just_pressed("springen")
	var hold_jump := Input.is_action_pressed("springen")
	if autotest:
		dir = 1.0
		auto_jump -= delta
		want_jump = auto_jump <= 0.0
		hold_jump = true
		if want_jump:
			auto_jump = 0.9
	if is_on_floor():
		coyote = 0.12
	else:
		coyote -= delta
	buffer = 0.12 if want_jump else buffer - delta
	var accel := 60.0 if is_on_floor() else 35.0
	velocity.x = move_toward(velocity.x, dir * run_speed, accel * delta)
	velocity.y -= gravity * delta
	if buffer > 0.0 and coyote > 0.0:
		velocity.y = jump_speed
		buffer = 0.0
		coyote = 0.0
	if not hold_jump and velocity.y > 0.0:
		velocity.y -= gravity * 1.2 * delta      # kurz drücken = kleiner Sprung
	velocity.y = maxf(velocity.y, -30.0)
	move_and_slide()
	for i in get_slide_collision_count():
		var c := get_slide_collision(i)
		var other := c.get_collider()
		if other and other.has_method("defeat"):
			if c.get_normal().y > 0.55:
				other.defeat()
				velocity.y = jump_speed * 0.7
				stomped.emit(other)
			elif invulnerable <= 0.0:
				hit.emit()
	if absf(dir) > 0.05:
		facing = signf(dir)
	visual.rotation.y = lerp_angle(visual.rotation.y, PI / 2.0 if facing > 0 else -PI / 2.0, minf(1.0, delta * 14.0))
	if one_shot > 0.0:
		one_shot -= delta
		return
	var speed := absf(velocity.x)
	if not is_on_floor():
		play("jump" if velocity.y > 0.0 else "fall")
	elif speed > run_speed * 0.6:
		play("run", clampf(speed / run_speed, 0.6, 1.6))
	elif speed > 0.5:
		play("walk", clampf(speed / (run_speed * 0.5), 0.6, 1.6))
	else:
		play("idle")
