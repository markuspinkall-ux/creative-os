extends RefCounted
## Bilder und GLB-Modelle zur Laufzeit laden (ohne Godot-Import, damit der Editor nur Dateien kopieren muss).

static var _textures := {}


static func path_of(rel: String) -> String:
	if rel == "":
		return ""
	if rel.begins_with("res://") or rel.begins_with("user://") or rel.begins_with("/"):
		return rel
	return "res://" + rel


static func texture(rel: String) -> Texture2D:
	var path := path_of(rel)
	if path == "":
		return null
	if _textures.has(path):
		return _textures[path]
	var bytes := FileAccess.get_file_as_bytes(path)
	if bytes.is_empty():
		push_warning("Bild fehlt: " + path)
		return null
	var img := Image.new()
	var ext := path.get_extension().to_lower()
	var err := ERR_FILE_UNRECOGNIZED
	if ext == "png":
		err = img.load_png_from_buffer(bytes)
	elif ext in ["jpg", "jpeg"]:
		err = img.load_jpg_from_buffer(bytes)
	elif ext == "webp":
		err = img.load_webp_from_buffer(bytes)
	if err != OK:
		push_warning("Bild nicht lesbar: " + path)
		return null
	var tex := ImageTexture.create_from_image(img)
	_textures[path] = tex
	return tex


static func model(rel: String) -> Node3D:
	## Lädt eine GLB-Datei als Szene; null, wenn es nicht klappt.
	var path := path_of(rel)
	if path == "":
		return null
	var bytes := FileAccess.get_file_as_bytes(path)
	if bytes.is_empty():
		push_warning("Modell fehlt: " + path)
		return null
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	if doc.append_from_buffer(bytes, path.get_base_dir(), state) != OK:
		push_warning("Modell nicht lesbar: " + path)
		return null
	var scene := doc.generate_scene(state)
	return scene as Node3D


static func bounds(node: Node3D) -> AABB:
	## Umriss aller Meshes (im Koordinatensystem von node).
	var result := AABB()
	var first := true
	var stack: Array = [node]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		if n is MeshInstance3D and n.mesh:
			var xf: Transform3D = _relative(node, n)
			var box: AABB = xf * n.mesh.get_aabb()
			if first:
				result = box
				first = false
			else:
				result = result.merge(box)
		for c in n.get_children():
			stack.append(c)
	return result


static func _relative(root: Node3D, n: Node) -> Transform3D:
	var xf := Transform3D.IDENTITY
	var cur: Node = n
	while cur and cur != root:
		if cur is Node3D:
			xf = (cur as Node3D).transform * xf
		cur = cur.get_parent()
	return xf


static func fitted(rel: String, height: float) -> Node3D:
	## Modell laden, auf die Höhe skalieren, Füße auf y=0, mittig.
	var m := model(rel)
	if m == null:
		return null
	var holder := Node3D.new()
	holder.add_child(m)
	var box := bounds(m)
	if box.size.y > 0.0001:
		var k := height / box.size.y
		m.scale = Vector3.ONE * k
		var c := box.get_center()
		m.position = Vector3(-c.x * k, -box.position.y * k, -c.z * k)
	return holder


static func find_animator(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node
	for c in node.get_children():
		var a := find_animator(c)
		if a:
			return a
	return null


static func pick_animation(player: AnimationPlayer, words: Array) -> String:
	if player == null:
		return ""
	for w in words:
		for name in player.get_animation_list():
			if String(name).to_lower().contains(w):
				return name
	return ""
