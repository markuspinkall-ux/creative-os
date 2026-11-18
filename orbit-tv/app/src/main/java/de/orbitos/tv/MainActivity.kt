package de.orbitos.tv

import android.app.Activity
import android.app.AlertDialog
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.HorizontalScrollView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import androidx.recyclerview.widget.GridLayoutManager
import androidx.recyclerview.widget.RecyclerView
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.Executors

@androidx.annotation.OptIn(androidx.media3.common.util.UnstableApi::class)
class MainActivity : Activity() {
    private lateinit var store: ChannelStore
    private lateinit var player: ExoPlayer
    private lateinit var playerView: PlayerView
    private lateinit var browse: View
    private lateinit var grid: RecyclerView
    private lateinit var tabs: LinearLayout
    private lateinit var tabScroll: HorizontalScrollView
    private lateinit var info: View
    private lateinit var message: TextView
    private lateinit var banner: TextView
    private lateinit var clock: TextView
    private val ui = Handler(Looper.getMainLooper())
    private val pool = Executors.newFixedThreadPool(4)
    private val loading = HashSet<String>()

    private var current: Channel? = null
    private var group = ChannelStore.GROUP_ALL
    private var playGroup = ChannelStore.GROUP_ALL
    private var shown: List<Channel> = emptyList()
    private var moving: Channel? = null
    private var digits = ""
    private var lastBack = 0L
    private var retried = false
    private val adapter = TileAdapter()

    private val hideInfo = Runnable { info.visibility = View.GONE }
    private val hideMessage = Runnable { message.visibility = View.GONE }
    private val tick = object : Runnable {
        override fun run() {
            clock.text = SimpleDateFormat("HH:mm", Locale.GERMANY).format(Date())
            ui.postDelayed(this, 20_000)
        }
    }
    private val applyDigits = Runnable {
        val n = digits.toIntOrNull()
        digits = ""
        val ch = n?.let { store.list(ChannelStore.GROUP_ALL).getOrNull(it - 1) }
        if (ch != null) watch(ch, ChannelStore.GROUP_ALL) else showMessage("Kein Sender auf Platz $n", 2000)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        store = ChannelStore(this)
        playerView = findViewById(R.id.player)
        browse = findViewById(R.id.browse)
        grid = findViewById(R.id.grid)
        tabs = findViewById(R.id.tabs)
        tabScroll = findViewById(R.id.tabScroll)
        info = findViewById(R.id.info)
        message = findViewById(R.id.message)
        banner = findViewById(R.id.banner)
        clock = findViewById(R.id.clock)

        // Weiterleitungen von http auf https erlauben (viele Senderadressen leiten um)
        val http = androidx.media3.datasource.DefaultHttpDataSource.Factory()
            .setAllowCrossProtocolRedirects(true)
            .setUserAgent("OrbitTV/2.0 (Fire TV)")
        val sources = androidx.media3.exoplayer.source.DefaultMediaSourceFactory(
            androidx.media3.datasource.DefaultDataSource.Factory(this, http))
        player = ExoPlayer.Builder(this).setMediaSourceFactory(sources).build()
        playerView.player = player
        player.addListener(object : Player.Listener {
            override fun onPlayerError(error: PlaybackException) {
                val ch = current ?: return
                if (!retried && !ch.custom) {
                    retried = true
                    ui.postDelayed({ current?.let { play(it) } }, 2500)
                } else if (ch.custom) {
                    showMessage("„${ch.name}“ lässt sich nicht abspielen.\nAdresse prüfen: Kachel wählen → ☰ → Bearbeiten", 7000)
                } else {
                    showMessage("${ch.name} ist gerade nicht erreichbar.\nBitte einen anderen Sender wählen.", 6000)
                }
            }

            override fun onPlaybackStateChanged(state: Int) {
                if (state == Player.STATE_READY) {
                    retried = false
                    if (message.visibility == View.VISIBLE) message.visibility = View.GONE
                }
            }
        })

        grid.layoutManager = GridLayoutManager(this, COLUMNS)
        grid.adapter = adapter
        grid.itemAnimator = null

        val start = store.byId(store.lastChannel) ?: store.list(ChannelStore.GROUP_ALL).firstOrNull()
        start?.let { play(it, quiet = true) }

        Thread {
            val before = current?.url
            if (store.refreshStreams()) ui.post { current?.let { if (it.url != before && !it.custom) play(it, quiet = true) } }
        }.start()

        showGroup(ChannelStore.GROUP_ALL, focusId = current?.id)
        ui.post(tick)
        if (savedInstanceState == null) ui.postDelayed({ handleIntent(intent) }, 800)
    }

    override fun onNewIntent(intent: android.content.Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    /** Direktwahl per Intent (Test): --es gruppe Dritte / --es sender zdf / --es neu_name … --es neu_url … */
    private fun handleIntent(intent: android.content.Intent?) {
        intent ?: return
        val name = intent.getStringExtra("neu_name")
        val url = intent.getStringExtra("neu_url")
        if (name != null && url != null) {
            val ch = store.addCustom(name, url, intent.getStringExtra("neu_gruppe") ?: ChannelStore.GROUP_OWN)
            showGroup(ch.group, ch.id)
        }
        intent.getStringExtra("gruppe")?.let { if (it in store.groups()) showGroup(it, null) }
        intent.getStringExtra("sender")?.let { id -> store.byId(id)?.let { watch(it, group) } }
        intent.getStringExtra("optionen")?.let { id -> store.byId(id)?.let { options(it) } }
        if (intent.getStringExtra("dialog") == "neu") editDialog(null)
        listOf("neu_name", "neu_url", "neu_gruppe", "gruppe", "sender", "optionen", "dialog").forEach { intent.removeExtra(it) }
    }

    override fun onStart() {
        super.onStart()
        if (::player.isInitialized && current != null) {
            if (player.playbackState == Player.STATE_IDLE) current?.let { play(it, quiet = true) } else player.play()
        }
    }

    override fun onStop() {
        super.onStop()
        player.pause()
    }

    override fun onDestroy() {
        player.release()
        pool.shutdownNow()
        super.onDestroy()
    }

    // ---- Abspielen ----------------------------------------------------------------------------

    private fun play(ch: Channel, quiet: Boolean = false) {
        current = ch
        store.lastChannel = ch.id
        if (!quiet) showInfo(ch)
        adapter.notifyDataSetChanged()
        Thread {
            val url = ChannelStore.resolvePlaylist(ch.url)
            ui.post {
                if (current?.id != ch.id) return@post
                val builder = MediaItem.Builder().setUri(url)
                if (url.contains(".m3u8", ignoreCase = true) || url.contains(".m3u", ignoreCase = true))
                    builder.setMimeType(MimeTypes.APPLICATION_M3U8)
                player.setMediaItem(builder.build())
                player.prepare()
                player.playWhenReady = true
            }
        }.start()
    }

    /** Sender bildschirmfüllend ansehen. */
    private fun watch(ch: Channel, fromGroup: String) {
        playGroup = fromGroup
        retried = false
        if (current?.id != ch.id || player.playbackState == Player.STATE_IDLE) play(ch) else showInfo(ch)
        hideBrowse()
    }

    private fun zap(delta: Int) {
        val list = store.list(playGroup).ifEmpty { store.list(ChannelStore.GROUP_ALL) }
        if (list.isEmpty()) return
        val pos = list.indexOfFirst { it.id == current?.id }
        val next = list[((if (pos < 0) 0 else pos + delta) % list.size + list.size) % list.size]
        retried = false
        play(next)
    }

    // ---- Übersicht ----------------------------------------------------------------------------

    private fun showBrowse() {
        browse.visibility = View.VISIBLE
        info.visibility = View.GONE
        showGroup(group, current?.id)
    }

    private fun hideBrowse() {
        endMove()
        browse.visibility = View.GONE
        playerView.requestFocus()
    }

    private fun showGroup(g: String, focusId: String?) {
        group = if (g in store.groups()) g else ChannelStore.GROUP_ALL
        shown = store.list(group)
        buildTabs()
        adapter.notifyDataSetChanged()
        val pos = shown.indexOfFirst { it.id == focusId }.takeIf { it >= 0 } ?: 0
        grid.scrollToPosition(pos)
        grid.post {
            val v = grid.findViewHolderForAdapterPosition(pos)?.itemView
            if (v != null && focusId != null) v.requestFocus() else selectedTab()?.requestFocus()
            if (v == null) updateHero(null)
        }
    }

    private fun buildTabs() {
        tabs.removeAllViews()
        val d = resources.displayMetrics.density
        for (g in store.groups()) {
            val count = store.list(g).size
            val t = TextView(this).apply {
                text = if (g == ChannelStore.GROUP_ALL || g == ChannelStore.GROUP_FAV || count == 0) g else "$g  $count"
                textSize = 16f
                setTextColor(getColorStateList(R.color.chip_text))
                setBackgroundResource(R.drawable.chip)
                setPadding((20 * d).toInt(), (9 * d).toInt(), (20 * d).toInt(), (9 * d).toInt())
                isFocusable = true
                isSelected = g == group
                tag = g
                setOnFocusChangeListener { v, has ->
                    if (has && group != g) {
                        group = g
                        shown = store.list(g)
                        adapter.notifyDataSetChanged()
                        grid.scrollToPosition(0)
                        for (i in 0 until tabs.childCount) tabs.getChildAt(i).isSelected = tabs.getChildAt(i).tag == g
                    }
                    if (has) {
                        tabScroll.smoothScrollTo((v.left - 120 * d).toInt().coerceAtLeast(0), 0)
                        updateHero(null)
                    }
                }
                setOnClickListener { focusGrid(0) }
            }
            tabs.addView(t, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT)
                .apply { marginEnd = (10 * d).toInt() })
        }
    }

    private fun selectedTab(): View? = (0 until tabs.childCount).map { tabs.getChildAt(it) }.firstOrNull { it.tag == group }

    private fun focusGrid(pos: Int) {
        grid.scrollToPosition(pos)
        grid.post { grid.findViewHolderForAdapterPosition(pos)?.itemView?.requestFocus() }
    }

    private fun canAdd() = group != ChannelStore.GROUP_FAV && group != ChannelStore.GROUP_HIDDEN

    /** Oben groß: der gewählte Sender – oder die Gruppe. */
    private fun updateHero(ch: Channel?) {
        val g = findViewById<TextView>(R.id.heroGroup)
        val n = findViewById<TextView>(R.id.heroName)
        val now = findViewById<TextView>(R.id.heroNow)
        if (ch == null) {
            g.text = "Gruppe"
            n.text = group
            now.text = when {
                group == ChannelStore.GROUP_FAV && shown.isEmpty() -> "Noch keine Favoriten – auf einer Kachel ☰ drücken → Favorit."
                shown.isEmpty() -> "Noch keine Sender in dieser Gruppe."
                else -> "${shown.size} Sender"
            }
            return
        }
        val nr = store.number(ch)
        g.text = listOfNotNull(if (nr > 0) "Platz $nr" else null, ch.group,
            if (ch.custom) "eigener Sender" else null, if (ch.id == current?.id) "läuft" else null).joinToString("  ·  ")
        n.text = ch.name
        now.text = if (ch.custom) ch.url else store.cachedNow(ch)?.let { "Jetzt: $it" } ?: ""
    }

    // ---- Anzeigen -----------------------------------------------------------------------------

    private fun showInfo(ch: Channel) {
        findViewById<TextView>(R.id.infoNumber).apply {
            text = store.number(ch).takeIf { it > 0 }?.toString() ?: "–"
            background = rounded(ch.color, 14f)
        }
        findViewById<TextView>(R.id.infoName).text = ch.name
        val now = findViewById<TextView>(R.id.infoNow)
        now.text = if (ch.custom) ch.group else store.cachedNow(ch)?.let { "Jetzt: $it" } ?: ch.group
        if (browse.visibility != View.VISIBLE) info.visibility = View.VISIBLE
        ui.removeCallbacks(hideInfo)
        ui.postDelayed(hideInfo, 5000)
        if (!ch.custom) pool.execute {
            val text = store.nowPlaying(ch)
            ui.post { if (current?.id == ch.id && text != null) now.text = "Jetzt: $text" }
        }
    }

    private fun showMessage(text: String, ms: Long) {
        message.text = text
        message.visibility = View.VISIBLE
        ui.removeCallbacks(hideMessage)
        ui.postDelayed(hideMessage, ms)
    }

    private fun rounded(color: Int, radiusDp: Float) = GradientDrawable().apply {
        cornerRadius = resources.displayMetrics.density * radiusDp
        setColor(color)
    }

    private fun artBackground(color: Int) = GradientDrawable(GradientDrawable.Orientation.TL_BR,
        intArrayOf(lighten(color), color)).apply {
        val r = resources.displayMetrics.density * 14
        cornerRadii = floatArrayOf(r, r, r, r, 0f, 0f, 0f, 0f)
    }

    private fun lighten(c: Int): Int {
        val f = 0.22f
        val r = (android.graphics.Color.red(c) + (255 - android.graphics.Color.red(c)) * f).toInt()
        val g = (android.graphics.Color.green(c) + (255 - android.graphics.Color.green(c)) * f).toInt()
        val b = (android.graphics.Color.blue(c) + (255 - android.graphics.Color.blue(c)) * f).toInt()
        return android.graphics.Color.rgb(r, g, b)
    }

    // ---- Optionen, Hinzufügen, Bearbeiten -----------------------------------------------------

    private fun options(ch: Channel) {
        val actions = mutableListOf<Pair<String, () -> Unit>>()
        actions += "Ansehen" to { watch(ch, group) }
        actions += (if (ch.id in store.favorites) "★  Favorit entfernen" else "☆  Als Favorit") to {
            store.toggleFavorite(ch); showGroup(group, ch.id)
        }
        actions += "Gruppe zuordnen …  (jetzt: ${ch.group})" to { assignDialog(ch) }
        actions += "Verschieben" to { startMove(ch) }
        actions += (if (ch.id in store.hidden) "Wieder einblenden" else "Ausblenden") to {
            store.toggleHidden(ch); showGroup(group, ch.id)
        }
        if (ch.custom) {
            actions += "Bearbeiten …" to { editDialog(ch) }
            actions += "Löschen" to { confirmDelete(ch) }
        }
        actions += "＋  Neuer Sender …" to { editDialog(null) }
        actions += "Reihenfolge zurücksetzen" to { store.resetOrder(); showGroup(group, ch.id) }
        AlertDialog.Builder(this, R.style.OrbitTV_Dialog)
            .setTitle(ch.name)
            .setItems(actions.map { it.first }.toTypedArray()) { _, i -> actions[i].second() }
            .show()
    }

    private fun assignDialog(ch: Channel) {
        val groups = store.assignableGroups()
        val items = groups.map { if (it == ch.group) "✓  $it" else it } + "＋  Neue Gruppe …"
        AlertDialog.Builder(this, R.style.OrbitTV_Dialog)
            .setTitle("„${ch.name}“ zuordnen")
            .setItems(items.toTypedArray()) { _, i ->
                if (i < groups.size) {
                    store.assign(ch, groups[i])
                    showGroup(group, ch.id)
                    showBanner("${ch.name} → ${groups[i]}")
                } else newGroupDialog(ch)
            }
            .show()
    }

    private fun newGroupDialog(ch: Channel) {
        val field = textField("Name der Gruppe")
        AlertDialog.Builder(this, R.style.OrbitTV_Dialog)
            .setTitle("Neue Gruppe")
            .setView(wrap(field))
            .setPositiveButton("Anlegen") { _, _ ->
                val name = field.text.toString().trim()
                if (name.isNotEmpty() && name !in listOf(ChannelStore.GROUP_ALL, ChannelStore.GROUP_FAV, ChannelStore.GROUP_HIDDEN)) {
                    store.assign(ch, name)
                    showGroup(name, ch.id)
                    showBanner("Gruppe „$name“ angelegt")
                }
            }
            .setNegativeButton("Abbrechen", null)
            .show()
        field.requestFocus()
    }

    /** Eigenen Sender hinzufügen (ch == null) oder bearbeiten. */
    private fun editDialog(ch: Channel?) {
        val view = LayoutInflater.from(this).inflate(R.layout.dialog_channel, null)
        val name = view.findViewById<EditText>(R.id.fieldName)
        val url = view.findViewById<EditText>(R.id.fieldUrl)
        val target = ch?.group ?: if (canAdd() && group != ChannelStore.GROUP_ALL) group else ChannelStore.GROUP_OWN
        view.findViewById<TextView>(R.id.fieldGroup).text =
            if (ch == null) "Wird in der Gruppe „$target“ gespeichert. Zuordnen kannst du später über ☰."
            else "Gruppe: ${ch.group}"
        if (ch != null) {
            name.setText(ch.name)
            url.setText(ch.url)
        } else url.setText("https://")
        val dialog = AlertDialog.Builder(this, R.style.OrbitTV_Dialog)
            .setTitle(if (ch == null) "Neuer Sender" else "Sender bearbeiten")
            .setView(view)
            .setPositiveButton("Speichern", null)
            .setNegativeButton("Abbrechen", null)
            .create()
        dialog.setOnShowListener {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                val n = name.text.toString().trim()
                val u = url.text.toString().trim()
                when {
                    n.isEmpty() -> { name.error = "Bitte einen Namen eingeben"; name.requestFocus() }
                    !ChannelStore.validUrl(u) -> { url.error = "Adresse muss mit http:// oder https:// beginnen"; url.requestFocus() }
                    else -> {
                        dialog.dismiss()
                        val saved = if (ch == null) store.addCustom(n, u, target) else ch.also { store.editCustom(it, n, u) }
                        showGroup(saved.group, saved.id)
                        showBanner(if (ch == null) "„$n“ gespeichert – läuft zur Probe" else "„$n“ gespeichert")
                        retried = false
                        play(saved, quiet = true)
                    }
                }
            }
        }
        dialog.show()
        name.requestFocus()
    }

    private fun confirmDelete(ch: Channel) {
        AlertDialog.Builder(this, R.style.OrbitTV_Dialog)
            .setTitle("„${ch.name}“ löschen?")
            .setMessage("Der Sender wird aus Orbit TV entfernt.")
            .setPositiveButton("Löschen") { _, _ ->
                if (current?.id == ch.id) { player.stop(); current = null }
                store.delete(ch)
                showGroup(group, null)
                showBanner("„${ch.name}“ gelöscht")
            }
            .setNegativeButton("Abbrechen", null)
            .show()
    }

    private fun textField(hint: String) = EditText(this).apply {
        this.hint = hint
        isSingleLine = true
        textSize = 18f
        setTextColor(getColor(R.color.text))
        setHintTextColor(0xFF6A707C.toInt())
        setBackgroundResource(R.drawable.field)
        val p = (14 * resources.displayMetrics.density).toInt()
        setPadding(p, p, p, p)
    }

    private fun wrap(v: View) = LinearLayout(this).apply {
        val p = (28 * resources.displayMetrics.density).toInt()
        setPadding(p, p / 3, p, 0)
        addView(v, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
    }

    private fun showBanner(text: String, ms: Long = 3000) {
        banner.text = text
        banner.visibility = View.VISIBLE
        ui.removeCallbacksAndMessages(banner)
        ui.postAtTime({ if (moving == null) banner.visibility = View.GONE }, banner, android.os.SystemClock.uptimeMillis() + ms)
    }

    // ---- Verschieben --------------------------------------------------------------------------

    private fun startMove(ch: Channel) {
        moving = ch
        banner.text = "„${ch.name}“ verschieben:  ◀ ▶ ▲ ▼   ·   OK fertig"
        banner.visibility = View.VISIBLE
        adapter.notifyDataSetChanged()
        focusGrid(shown.indexOfFirst { it.id == ch.id }.coerceAtLeast(0))
    }

    private fun endMove() {
        if (moving == null) return
        val id = moving?.id
        moving = null
        banner.visibility = View.GONE
        if (browse.visibility == View.VISIBLE) showGroup(group, id)
    }

    private fun moveBy(delta: Int) {
        val ch = moving ?: return
        if (store.move(ch, delta, group)) {
            shown = store.list(group)
            adapter.notifyDataSetChanged()
            focusGrid(shown.indexOfFirst { it.id == ch.id })
        }
    }

    // ---- Fernbedienung ------------------------------------------------------------------------

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (event.action != KeyEvent.ACTION_DOWN) return super.dispatchKeyEvent(event)
        val code = event.keyCode
        val browsing = browse.visibility == View.VISIBLE

        if (moving != null) {
            when (code) {
                KeyEvent.KEYCODE_DPAD_LEFT -> moveBy(-1)
                KeyEvent.KEYCODE_DPAD_RIGHT -> moveBy(+1)
                KeyEvent.KEYCODE_DPAD_UP -> moveBy(-COLUMNS)
                KeyEvent.KEYCODE_DPAD_DOWN -> moveBy(+COLUMNS)
                KeyEvent.KEYCODE_DPAD_CENTER, KeyEvent.KEYCODE_ENTER, KeyEvent.KEYCODE_BACK, KeyEvent.KEYCODE_MENU -> endMove()
                else -> return super.dispatchKeyEvent(event)
            }
            return true
        }

        if (code in KeyEvent.KEYCODE_0..KeyEvent.KEYCODE_9 && currentFocus !is EditText) {
            digits += (code - KeyEvent.KEYCODE_0).toString()
            showMessage("Platz $digits", 1500)
            ui.removeCallbacks(applyDigits)
            ui.postDelayed(applyDigits, 1500)
            return true
        }

        if (browsing) {
            val focus = currentFocus
            val inGrid = focus != null && focus.parent === grid
            val pos = if (inGrid) grid.getChildAdapterPosition(focus!!) else -1
            when (code) {
                KeyEvent.KEYCODE_DPAD_UP -> if (inGrid && pos in 0 until COLUMNS) { selectedTab()?.requestFocus(); return true }
                KeyEvent.KEYCODE_DPAD_DOWN -> if (focus?.parent === tabs) { focusGrid(0); return true }
                KeyEvent.KEYCODE_MENU -> {
                    if (inGrid) shown.getOrNull(pos)?.let { options(it) } ?: editDialog(null)
                    else if (canAdd()) editDialog(null)
                    return true
                }
                KeyEvent.KEYCODE_BACK -> {
                    if (current != null && player.playbackState != Player.STATE_IDLE) { hideBrowse(); current?.let { showInfo(it) }; return true }
                    return backTwiceToExit()
                }
            }
            return super.dispatchKeyEvent(event)
        }

        when (code) {
            KeyEvent.KEYCODE_DPAD_UP, KeyEvent.KEYCODE_CHANNEL_UP -> { zap(-1); return true }
            KeyEvent.KEYCODE_DPAD_DOWN, KeyEvent.KEYCODE_CHANNEL_DOWN -> { zap(+1); return true }
            KeyEvent.KEYCODE_DPAD_LEFT, KeyEvent.KEYCODE_DPAD_RIGHT, KeyEvent.KEYCODE_INFO -> { current?.let { showInfo(it) }; return true }
            KeyEvent.KEYCODE_DPAD_CENTER, KeyEvent.KEYCODE_ENTER, KeyEvent.KEYCODE_MENU, KeyEvent.KEYCODE_BACK -> { showBrowse(); return true }
        }
        return super.dispatchKeyEvent(event)
    }

    private fun backTwiceToExit(): Boolean {
        val now = System.currentTimeMillis()
        if (now - lastBack < 2500) finish()
        else {
            lastBack = now
            Toast.makeText(this, "Nochmal Zurück zum Beenden", Toast.LENGTH_SHORT).show()
        }
        return true
    }

    // ---- Kacheln ------------------------------------------------------------------------------

    private inner class TileAdapter : RecyclerView.Adapter<TileAdapter.Holder>() {
        inner class Holder(v: View) : RecyclerView.ViewHolder(v) {
            val art: View = v.findViewById(R.id.art)
            val artName: TextView = v.findViewById(R.id.artName)
            val number: TextView = v.findViewById(R.id.number)
            val fav: View = v.findViewById(R.id.fav)
            val live: View = v.findViewById(R.id.live)
            val name: TextView = v.findViewById(R.id.name)
            val now: TextView = v.findViewById(R.id.now)
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): Holder {
            val v = LayoutInflater.from(parent.context).inflate(R.layout.item_tile, parent, false)
            v.clipToOutline = true
            val h = Holder(v)
            v.setOnClickListener {
                val ch = shown.getOrNull(h.bindingAdapterPosition)
                if (ch != null) watch(ch, group) else editDialog(null)
            }
            v.setOnLongClickListener { shown.getOrNull(h.bindingAdapterPosition)?.let { options(it) }; true }
            v.setOnFocusChangeListener { view, has ->
                view.animate().scaleX(if (has) 1.07f else 1f).scaleY(if (has) 1.07f else 1f)
                    .translationZ(if (has) 12f else 0f).setDuration(140).start()
                if (has) updateHero(shown.getOrNull(h.bindingAdapterPosition))
            }
            return h
        }

        override fun getItemCount() = shown.size + if (canAdd()) 1 else 0

        override fun onBindViewHolder(h: Holder, position: Int) {
            val ch = shown.getOrNull(position)
            if (ch == null) {                                    // Kachel „Sender hinzufügen“
                h.art.background = artBackground(getColor(R.color.raised2))
                h.artName.text = "＋"
                h.artName.textSize = 34f
                h.number.text = ""
                h.fav.visibility = View.GONE
                h.live.visibility = View.GONE
                h.name.text = "Sender hinzufügen"
                h.now.text = "Name + M3U-Adresse"
                h.itemView.alpha = 1f
                return
            }
            h.art.background = artBackground(ch.color)
            h.artName.text = ch.name
            val nr = store.number(ch)
            h.number.text = if (nr > 0) nr.toString() else ""
            h.fav.visibility = if (ch.id in store.favorites) View.VISIBLE else View.GONE
            val playing = ch.id == current?.id
            h.live.visibility = if (playing) View.VISIBLE else View.GONE
            h.live.background = if (playing) rounded(getColor(R.color.live), 8f) else null
            val dp = resources.displayMetrics.density
            h.live.setPadding((7 * dp).toInt(), (2 * dp).toInt(), (7 * dp).toInt(), (2 * dp).toInt())
            h.name.text = ch.name
            h.itemView.alpha = if (moving != null && moving?.id != ch.id) 0.45f else 1f
            if (ch.custom) h.now.text = "Eigener Sender" else {
                val now = store.cachedNow(ch)
                h.now.text = now ?: ch.group
                if (now == null && loading.add(ch.id)) pool.execute {
                    val t = store.nowPlaying(ch)
                    ui.post {
                        loading.remove(ch.id)
                        if (t != null) {
                            val i = shown.indexOfFirst { it.id == ch.id }
                            if (i >= 0) notifyItemChanged(i)
                            val f = currentFocus
                            if (f != null && f.parent === grid && shown.getOrNull(grid.getChildAdapterPosition(f))?.id == ch.id) updateHero(ch)
                        }
                    }
                }
            }
        }
    }

    companion object {
        const val COLUMNS = 5
    }
}
