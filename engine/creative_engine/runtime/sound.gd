extends RefCounted
## Klänge der Creative Engine: eigene Dateien (OGG, MP3, WAV) laden und eingebaute Effekte erzeugen.
## Die eingebauten Effekte werden beim Start aus Formeln berechnet (keine Dateien, keine Lizenzfragen).

const Assets = preload("res://assets.gd")
const RATE := 22050

static var _cache := {}


# ---- Eigene Dateien ---------------------------------------------------------------------------
static func load_file(rel: String, loop := false) -> AudioStream:
	var path := Assets.path_of(rel)
	if path == "":
		return null
	var key := path + ("#loop" if loop else "")
	if _cache.has(key):
		return _cache[key]
	var bytes := FileAccess.get_file_as_bytes(path)
	if bytes.is_empty():
		push_warning("Klang fehlt: " + path)
		return null
	var ext := path.get_extension().to_lower()
	var stream: AudioStream = null
	if ext == "ogg":
		var ogg := AudioStreamOggVorbis.load_from_buffer(bytes)
		if ogg:
			ogg.loop = loop
			stream = ogg
	elif ext == "mp3":
		var mp3 := AudioStreamMP3.new()
		mp3.data = bytes
		mp3.loop = loop
		stream = mp3
	elif ext == "wav":
		stream = wav_from_bytes(bytes, loop)
	if stream == null:
		push_warning("Klang nicht lesbar: " + path)
		return null
	_cache[key] = stream
	return stream


static func wav_from_bytes(b: PackedByteArray, loop: bool) -> AudioStreamWAV:
	## Einfache PCM-WAV-Dateien (8/16 Bit, mono/stereo) – reicht für Musik und Effekte.
	if b.size() < 44 or b.slice(0, 4).get_string_from_ascii() != "RIFF" or b.slice(8, 12).get_string_from_ascii() != "WAVE":
		return null
	var pos := 12
	var channels := 1
	var rate := 44100
	var bits := 16
	var fmt := 1
	while pos + 8 <= b.size():
		var id := b.slice(pos, pos + 4).get_string_from_ascii()
		var size := b.decode_u32(pos + 4)
		if id == "fmt ":
			fmt = b.decode_u16(pos + 8)
			channels = b.decode_u16(pos + 10)
			rate = b.decode_u32(pos + 12)
			bits = b.decode_u16(pos + 22)
		elif id == "data":
			if fmt != 1 or not bits in [8, 16]:
				return null
			var w := AudioStreamWAV.new()
			w.format = AudioStreamWAV.FORMAT_16_BITS if bits == 16 else AudioStreamWAV.FORMAT_8_BITS
			var data := b.slice(pos + 8, mini(b.size(), pos + 8 + size))
			if bits == 8:
				# WAV speichert 8 Bit ohne Vorzeichen, Godot erwartet mit Vorzeichen
				for i in data.size():
					data[i] = (data[i] + 128) & 0xFF
			w.data = data
			w.mix_rate = rate
			w.stereo = channels == 2
			if loop:
				w.loop_mode = AudioStreamWAV.LOOP_FORWARD
				w.loop_end = data.size() / (channels * bits / 8)
			return w
		pos += 8 + size + (size & 1)
	return null


# ---- Eingebaute Effekte -----------------------------------------------------------------------
static func make(s: PackedFloat32Array, loop := false) -> AudioStreamWAV:
	var data := PackedByteArray()
	data.resize(s.size() * 2)
	for i in s.size():
		data.encode_s16(i * 2, int(clampf(s[i], -1.0, 1.0) * 32000.0))
	var w := AudioStreamWAV.new()
	w.format = AudioStreamWAV.FORMAT_16_BITS
	w.mix_rate = RATE
	w.data = data
	if loop:
		w.loop_mode = AudioStreamWAV.LOOP_FORWARD
		w.loop_begin = 0
		w.loop_end = s.size()
	return w


static func buffer(secs: float) -> PackedFloat32Array:
	var s := PackedFloat32Array()
	s.resize(int(secs * RATE))
	return s


static func builtin(key: String) -> AudioStreamWAV:
	if _cache.has("eingebaut:" + key):
		return _cache["eingebaut:" + key]
	var w: AudioStreamWAV
	match key:
		"laser": w = make(zap(0.17, 1500.0, 320.0, 0.55, 0.05))
		"streu": w = make(zap(0.13, 2100.0, 650.0, 0.45, 0.25))
		"plasma": w = make(plasma())
		"rakete": w = make(rocket())
		"triebwerk": w = make(engine_loop(), true)
		"boost": w = make(sweep_noise(1.1, 300.0, 4200.0, 0.9, 120.0, 420.0))
		"bremse": w = make(brake())
		"rolle": w = make(whoosh(0.6, 0.55, 600.0, 2600.0))
		"looping": w = make(whoosh(1.7, 0.6, 400.0, 2200.0))
		"explosion": w = make(explosion(1.5))
		"treffer": w = make(hit())
		"klick": w = make(zap(0.05, 900.0, 700.0, 0.25, 0.0))
		"reparatur": w = make(chime())
		_: return null
	_cache["eingebaut:" + key] = w
	return w


static func zap(secs: float, f0: float, f1: float, vol: float, noise: float) -> PackedFloat32Array:
	## „Piu“: Ton, der schnell nach unten rutscht – halb Rechteck, halb Sinus
	var s := buffer(secs)
	var phase := 0.0
	var rng := RandomNumberGenerator.new()
	rng.seed = int(f0)
	for i in s.size():
		var t := float(i) / s.size()
		var f := lerpf(f0, f1, pow(t, 0.6))
		phase += TAU * f / RATE
		var tone := 0.6 * sin(phase) + 0.4 * signf(sin(phase))
		var env := exp(-t * 5.0) * minf(1.0, t * 80.0)
		s[i] = vol * env * (tone * (1.0 - noise) + rng.randf_range(-1, 1) * noise)
	return s


static func plasma() -> PackedFloat32Array:
	var s := buffer(0.38)
	var phase := 0.0
	for i in s.size():
		var t := float(i) / s.size()
		var f := lerpf(260.0, 85.0, t) * (1.0 + 0.08 * sin(TAU * 32.0 * t * 0.38))
		phase += TAU * f / RATE
		var v := sin(phase) + 0.5 * sin(phase * 2.0 + 0.4)
		s[i] = 0.6 * tanh(v * 1.8) * exp(-t * 3.2) * minf(1.0, t * 40.0)
	return s


static func rocket() -> PackedFloat32Array:
	var s := buffer(0.7)
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	var lp := 0.0
	var phase := 0.0
	for i in s.size():
		var t := float(i) / s.size()
		var cut := lerpf(0.05, 0.4, minf(1.0, t * 3.0))
		lp += cut * (rng.randf_range(-1, 1) - lp)
		phase += TAU * lerpf(70.0, 140.0, t) / RATE
		s[i] = (0.7 * lp + 0.35 * sin(phase)) * minf(1.0, t * 14.0) * exp(-t * 2.4)
	return s


static func engine_loop() -> PackedFloat32Array:
	## 1 s, nahtlos wiederholbar: nur ganzzahlige Frequenzen, Rauschen an den Rändern überblendet
	var s := buffer(1.0)
	var n := s.size()
	var rng := RandomNumberGenerator.new()
	rng.seed = 3
	var noise := PackedFloat32Array()
	noise.resize(n)
	var lp := 0.0
	for i in n:
		lp += 0.08 * (rng.randf_range(-1, 1) - lp)
		noise[i] = lp
	for i in n:
		var t := float(i) / RATE
		var hum := 0.5 * sin(TAU * 55.0 * t) + 0.3 * sin(TAU * 110.0 * t + 0.6) + 0.15 * sin(TAU * 167.0 * t)
		hum *= 0.85 + 0.15 * sin(TAU * 6.0 * t)
		var k := float(i) / n
		var nz := noise[i] * (1.0 - k) + noise[(i + n / 2) % n] * k   # Rauschen nahtlos
		s[i] = 0.32 * hum + 0.9 * nz
	return s


static func sweep_noise(secs: float, c0: float, c1: float, vol: float, f0: float, f1: float) -> PackedFloat32Array:
	## Boost: Rauschen, dessen Filter sich öffnet, dazu ein steigender Ton – „Wuuusch“
	var s := buffer(secs)
	var rng := RandomNumberGenerator.new()
	rng.seed = 11
	var lp := 0.0
	var phase := 0.0
	for i in s.size():
		var t := float(i) / s.size()
		var cut := clampf(lerpf(c0, c1, pow(t, 0.5)) / RATE * TAU, 0.0, 1.0)
		lp += cut * (rng.randf_range(-1, 1) - lp)
		phase += TAU * lerpf(f0, f1, t) / RATE
		var env := minf(1.0, t * 12.0) * (1.0 - smoothstep(0.55, 1.0, t))
		s[i] = vol * env * (0.75 * lp + 0.3 * sin(phase))
	return s


static func brake() -> PackedFloat32Array:
	## Bremsdüsen: zischendes Rauschen, Filter schließt sich, kurze Stöße
	var s := buffer(0.8)
	var rng := RandomNumberGenerator.new()
	rng.seed = 19
	var lp := 0.0
	var hp := 0.0
	for i in s.size():
		var t := float(i) / s.size()
		var cut := clampf(lerpf(5200.0, 900.0, t) / RATE * TAU, 0.0, 1.0)
		var x := rng.randf_range(-1, 1)
		lp += cut * (x - lp)
		hp = lp - hp * 0.0
		var puffs := 0.65 + 0.35 * sin(TAU * 11.0 * t * 0.8)
		s[i] = 0.75 * hp * puffs * minf(1.0, t * 25.0) * (1.0 - smoothstep(0.6, 1.0, t))
	return s


static func whoosh(secs: float, vol: float, c0: float, c1: float) -> PackedFloat32Array:
	## Rolle und Looping: Luftrauschen (Bandpass), das an- und abschwillt
	var s := buffer(secs)
	var rng := RandomNumberGenerator.new()
	rng.seed = int(secs * 100)
	var lp1 := 0.0
	var lp2 := 0.0
	for i in s.size():
		var t := float(i) / s.size()
		var bell := sin(PI * t)
		var cut := clampf(lerpf(c0, c1, bell) / RATE * TAU, 0.0, 1.0)
		var x := rng.randf_range(-1, 1)
		lp1 += cut * (x - lp1)
		lp2 += cut * 0.35 * (lp1 - lp2)
		s[i] = vol * 1.6 * (lp1 - lp2) * pow(bell, 1.3)
	return s


static func explosion(secs: float) -> PackedFloat32Array:
	## Abschuss: dumpfer Knall (fallender Ton) + Rauschen mit Knistern, klingt lange aus
	var s := buffer(secs)
	var rng := RandomNumberGenerator.new()
	rng.seed = 23
	var lp := 0.0
	var phase := 0.0
	for i in s.size():
		var t := float(i) / s.size()
		var cut := clampf(lerpf(0.5, 0.03, pow(t, 0.4)), 0.0, 1.0)
		lp += cut * (rng.randf_range(-1, 1) - lp)
		phase += TAU * lerpf(90.0, 28.0, pow(t, 0.5)) / RATE
		var crackle := (rng.randf_range(-1, 1) if rng.randf() < 0.02 * (1.0 - t) else 0.0)
		var env := minf(1.0, t * 200.0) * exp(-t * 4.0)
		s[i] = tanh(1.6 * (0.9 * lp + 0.7 * sin(phase) * exp(-t * 6.0) + 0.6 * crackle)) * env
	return s


static func hit() -> PackedFloat32Array:
	var s := buffer(0.28)
	var rng := RandomNumberGenerator.new()
	rng.seed = 31
	var phase := 0.0
	for i in s.size():
		var t := float(i) / s.size()
		phase += TAU * 330.0 / RATE
		var metal := sin(phase) * sin(phase * 2.76) * exp(-t * 9.0)
		s[i] = 0.7 * (0.6 * rng.randf_range(-1, 1) * exp(-t * 14.0) + 0.6 * metal)
	return s


static func chime() -> PackedFloat32Array:
	var s := buffer(0.6)
	for i in s.size():
		var t := float(i) / RATE
		var k := float(i) / s.size()
		var f := 660.0 if k < 0.5 else 880.0
		s[i] = 0.35 * sin(TAU * f * t) * exp(-fmod(k, 0.5) * 8.0)
	return s
