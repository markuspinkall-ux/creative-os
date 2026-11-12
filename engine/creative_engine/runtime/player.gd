extends CharacterBody3D
## Spielfigur: laufen, springen (mit „Coyote Time“ und Sprungpuffer), Gegner von oben besiegen.

signal stomped(enemy: Node)
signal hit

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
		anims = {
			"idle": Assets.pick_animation(anim, ["idle", "stand", "breath", "wait"]),
			"run": Assets.pick_animation(anim, ["run", "walk", "jog", "move"]),
			"jump": Assets.pick_animation(anim, ["jump", "fall", "air"]),
		}
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


func play(kind: String) -> void:
	if anim == null:
		return
	var a: String = anims.get(kind, "")
	if a == "" and kind == "jump":
		a = anims.get("idle", "")
	if a != "" and anim.current_animation != a:
		anim.play(a, 0.15)


func respawn(at: Vector3) -> void:
	position = at
	velocity = Vector3.ZERO
	invulnerable = 1.5


func knockback() -> void:
	velocity = Vector3(-facing * 8.0, 8.0, 0)
	invulnerable = 1.5


func _physics_process(delta: float) -> void:
	if frozen:
		velocity.x = move_toward(velocity.x, 0, 30 * delta)
		velocity.y -= gravity * delta
		move_and_slide()
		play("idle")
		return
	invulnerable = maxf(0.0, invulnerable - delta)
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
	if not is_on_floor():
		play("jump")
	elif absf(velocity.x) > 0.5:
		play("run")
	else:
		play("idle")
