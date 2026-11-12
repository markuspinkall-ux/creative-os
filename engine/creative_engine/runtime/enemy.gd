extends CharacterBody3D
## Gegner: läuft hin und her, dreht an Wänden und Kanten um. Von oben besiegbar.

const Assets = preload("res://assets.gd")

var patrol_range := 3.0
var speed := 2.0
var gravity := 30.0
var dir := -1.0
var origin_x := 0.0
var visual: Node3D
var dead := false
var anim: AnimationPlayer


func build(model_path: String) -> void:
	origin_x = position.x
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(0.8, 0.8, 1.0)
	shape.shape = box
	shape.position = Vector3(0, 0.4, 0)
	add_child(shape)
	axis_lock_linear_z = true
	visual = Node3D.new()
	add_child(visual)
	var model := Assets.fitted(model_path, 0.9)
	if model:
		visual.add_child(model)
		anim = Assets.find_animator(model)
		var walk := Assets.pick_animation(anim, ["walk", "run", "move", "idle"])
		if walk != "":
			anim.play(walk)
	else:
		var mi := MeshInstance3D.new()
		var sm := SphereMesh.new()
		sm.radius = 0.42
		sm.height = 0.7
		mi.mesh = sm
		mi.position = Vector3(0, 0.36, 0)
		var m := StandardMaterial3D.new()
		m.albedo_color = Color("#ff6b6b")
		mi.material_override = m
		visual.add_child(mi)
		for side in [-1, 1]:
			var eye := MeshInstance3D.new()
			var em := SphereMesh.new()
			em.radius = 0.08
			em.height = 0.16
			eye.mesh = em
			eye.position = Vector3(0.22, 0.5, side * 0.15 + 0.25)
			var wm := StandardMaterial3D.new()
			wm.albedo_color = Color.WHITE
			eye.material_override = wm
			visual.add_child(eye)


func defeat() -> void:
	if dead:
		return
	dead = true
	collision_layer = 0
	collision_mask = 0
	var tw := create_tween()
	tw.tween_property(visual, "scale", Vector3(1.3, 0.15, 1.3), 0.15)
	tw.tween_interval(0.3)
	tw.tween_callback(queue_free)


func _physics_process(delta: float) -> void:
	if dead:
		return
	velocity.y -= gravity * delta
	velocity.x = dir * speed
	move_and_slide()
	var turn := is_on_wall() or absf(position.x - origin_x) > patrol_range and signf(position.x - origin_x) == dir
	if is_on_floor() and not turn:
		# Kante voraus? Dann umdrehen.
		var space := get_world_3d().direct_space_state
		var from := global_position + Vector3(dir * 0.55, 0.3, 0)
		var q := PhysicsRayQueryParameters3D.create(from, from + Vector3(0, -1.0, 0))
		q.exclude = [get_rid()]
		if space.intersect_ray(q).is_empty():
			turn = true
	if turn:
		dir = -dir
	visual.rotation.y = 0.0 if dir > 0 else PI
