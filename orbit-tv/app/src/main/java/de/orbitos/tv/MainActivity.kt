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
import android.widget.TextView
import android.widget.Toast
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView

class MainActivity : Activity() {
    private lateinit var store: ChannelStore
    private lateinit var player: ExoPlayer
    private lateinit var playerView: PlayerView
    private lateinit var panel: View
    private lateinit var list: RecyclerView
    private lateinit var groupLabel: TextView
    private lateinit var info: View
    private lateinit var message: TextView
    private val ui = Handler(Looper.getMainLooper())

    private var current: Channel? = null
    private var groupIndex = 0
    private var shown: List<Channel> = emptyList()
    private var digits = ""
    private var lastBack = 0L
    private var retried = false
    private val adapter = ChannelAdapter()

    private val hideInfo = Runnable { info.visibility = View.GONE }
    private val hideMessage = Runnable { message.visibility = View.GONE }
    private val applyDigits = Runnable {
        val n = digits.toIntOrNull()
        digits = ""
        val ch = n?.let { store.list(ChannelStore.GROUP_ALL).getOrNull(it - 1) }
        if (ch != null) select(ch) else showMessage("Kein Sender auf Platz $n", 2000)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        store = ChannelStore(this)
        playerView = findViewById(R.id.player)
        panel = findViewById(R.id.panel)
        list = findViewById(R.id.list)
        groupLabel = findViewById(R.id.group)
        info = findViewById(R.id.info)
        message = findViewById(R.id.message)

        player = ExoPlayer.Builder(this).build()
        playerView.player = player
        player.addListener(object : Player.Listener {
            override fun onPlayerError(error: PlaybackException) {
                if (!retried) {
                    retried = true
                    ui.postDelayed({ current?.let { play(it) } }, 2500)
                } else {
                    showMessage("${current?.name ?: "Sender"} ist gerade nicht erreichbar.\nBitte einen anderen Sender wählen.", 6000)
                }
            }

            override fun onPlaybackStateChanged(state: Int) {
                if (state == Player.STATE_READY) {
                    retried = false
                    if (message.visibility == View.VISIBLE) message.visibility = View.GONE
                }
            }
        })

        list.layoutManager = LinearLayoutManager(this)
        list.adapter = adapter
        list.itemAnimator = null

        val start = store.byId(store.lastChannel)?.takeIf { it.kind == Kind.STREAM }
            ?: store.list(ChannelStore.GROUP_ALL).firstOrNull { it.kind == Kind.STREAM }
        start?.let { play(it) }

        // Stream-Adressen aktualisieren; ändert sich die des laufenden Senders, neu starten
        Thread {
            val before = current?.url
            if (store.refreshStreams()) {
                ui.post { current?.let { if (it.url != before) play(it) } }
            }
        }.start()

        if (savedInstanceState == null) ui.postDelayed({ showPanel() }, 600)
    }

    override fun onStart() {
        super.onStart()
        if (::player.isInitialized && current != null) {
            if (player.playbackState == Player.STATE_IDLE) current?.let { play(it) } else player.play()
        }
    }

    override fun onStop() {
        super.onStop()
        player.pause()
    }

    override fun onDestroy() {
        player.release()
        super.onDestroy()
    }

    // ---- Abspielen und Umschalten -----------------------------------------------------------

    private fun play(ch: Channel) {
        current = ch
        store.lastChannel = ch.id
        val item = MediaItem.Builder().setUri(ch.url).setMimeType(MimeTypes.APPLICATION_M3U8).build()
        player.setMediaItem(item)
        player.prepare()
        player.playWhenReady = true
        showInfo(ch)
        adapter.notifyDataSetChanged()
    }

    /** Sender wählen: öffentlich-rechtliche laufen hier, Joyn/RTL+ in der offiziellen App. */
    private fun select(ch: Channel) {
        val partner = Partners.of(ch.kind)
        if (partner == null) {
            retried = false
            play(ch)
            hidePanel()
            return
        }
        if (Partners.open(this, partner)) {
            Toast.makeText(this, "${partner.name}: Live-TV → ${ch.name}", Toast.LENGTH_LONG).show()
        } else {
            AlertDialog.Builder(this, R.style.OrbitTV_Dialog)
                .setTitle("${partner.name} fehlt")
                .setMessage("${ch.name} läuft über die offizielle ${partner.name}-App mit deinem Konto.\n\n" +
                    "Installiere „${partner.name}“ aus dem Amazon Appstore und melde dich dort einmal an. " +
                    "Danach öffnet Orbit TV den Sender direkt.")
                .setPositiveButton("Zum Appstore") { _, _ -> Partners.openStore(this, partner) }
                .setNegativeButton("Abbrechen", null)
                .show()
        }
    }

    /** Hoch/Runter: nächster öffentlich-rechtlicher Sender in deiner Reihenfolge. */
    private fun zap(delta: Int) {
        val streams = store.list(ChannelStore.GROUP_ALL).filter { it.kind == Kind.STREAM }
        if (streams.isEmpty()) return
        val pos = streams.indexOfFirst { it.id == current?.id }
        val next = streams[((if (pos < 0) 0 else pos + delta) % streams.size + streams.size) % streams.size]
        retried = false
        play(next)
    }

    // ---- Anzeige -------------------------------------------------------------------------------

    private fun showInfo(ch: Channel) {
        findViewById<TextView>(R.id.infoNumber).apply {
            text = store.number(ch).takeIf { it > 0 }?.toString() ?: "–"
            background = badge(ch.color)
        }
        findViewById<TextView>(R.id.infoName).text = ch.name
        val now = findViewById<TextView>(R.id.infoNow)
        now.text = ""
        info.visibility = View.VISIBLE
        ui.removeCallbacks(hideInfo)
        ui.postDelayed(hideInfo, 5000)
        Thread {
            val text = store.nowPlaying(ch)
            ui.post { if (current?.id == ch.id && text != null) now.text = "Jetzt: $text" }
        }.start()
    }

    private fun showMessage(text: String, ms: Long) {
        message.text = text
        message.visibility = View.VISIBLE
        ui.removeCallbacks(hideMessage)
        ui.postDelayed(hideMessage, ms)
    }

    private fun badge(color: Int) = GradientDrawable().apply {
        cornerRadius = resources.displayMetrics.density * 10
        setColor(color)
    }

    private fun group() = ChannelStore.GROUPS[groupIndex]

    private fun showPanel(focusId: String? = current?.id) {
        shown = store.list(group())
        groupLabel.text = "◀  ${group()}  ▶"
        adapter.notifyDataSetChanged()
        panel.visibility = View.VISIBLE
        if (shown.isEmpty()) {
            groupLabel.requestFocus()
            groupLabel.isFocusable = true
            return
        }
        val pos = shown.indexOfFirst { it.id == focusId }.coerceAtLeast(0)
        list.scrollToPosition(pos)
        list.post {
            (list.findViewHolderForAdapterPosition(pos)?.itemView ?: list.getChildAt(0))?.requestFocus()
        }
    }

    private fun hidePanel() {
        panel.visibility = View.GONE
        playerView.requestFocus()
    }

    private fun focusedChannel(): Channel? {
        val v = list.focusedChild ?: return null
        return shown.getOrNull(list.getChildAdapterPosition(v))
    }

    private fun changeGroup(delta: Int) {
        groupIndex = (groupIndex + delta + ChannelStore.GROUPS.size) % ChannelStore.GROUPS.size
        showPanel(focusId = null)
        if (shown.isEmpty()) {
            showMessage(if (group() == ChannelStore.GROUP_FAV) "Noch keine Favoriten.\nAuf einem Sender ☰ drücken → Favorit."
            else "Hier ist kein Sender.", 2500)
        }
    }

    private fun options(ch: Channel) {
        val fav = ch.id in store.favorites
        val hidden = ch.id in store.hidden
        val items = arrayOf(
            if (fav) "★ Aus Favoriten entfernen" else "☆ Zu Favoriten",
            "▲ Nach oben schieben",
            "▼ Nach unten schieben",
            if (hidden) "Wieder einblenden" else "Ausblenden",
            "Reihenfolge zurücksetzen",
        )
        AlertDialog.Builder(this, R.style.OrbitTV_Dialog)
            .setTitle(ch.name)
            .setItems(items) { _, which ->
                when (which) {
                    0 -> store.toggleFavorite(ch)
                    1 -> store.move(ch, -1, group())
                    2 -> store.move(ch, +1, group())
                    3 -> store.toggleHidden(ch)
                    4 -> store.resetOrder()
                }
                showPanel(focusId = ch.id)
            }
            .show()
    }

    // ---- Fernbedienung ------------------------------------------------------------------------

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (event.action != KeyEvent.ACTION_DOWN) return super.dispatchKeyEvent(event)
        val code = event.keyCode
        val panelOpen = panel.visibility == View.VISIBLE

        if (code in KeyEvent.KEYCODE_0..KeyEvent.KEYCODE_9) {
            digits += (code - KeyEvent.KEYCODE_0).toString()
            showMessage("Platz $digits", 1500)
            ui.removeCallbacks(applyDigits)
            ui.postDelayed(applyDigits, 1500)
            return true
        }
        if (panelOpen) {
            when (code) {
                KeyEvent.KEYCODE_DPAD_LEFT -> { changeGroup(-1); return true }
                KeyEvent.KEYCODE_DPAD_RIGHT -> { changeGroup(+1); return true }
                KeyEvent.KEYCODE_MENU -> { focusedChannel()?.let { options(it) }; return true }
                KeyEvent.KEYCODE_BACK -> { hidePanel(); return true }
            }
            return super.dispatchKeyEvent(event)
        }
        when (code) {
            KeyEvent.KEYCODE_DPAD_UP, KeyEvent.KEYCODE_CHANNEL_UP -> { zap(-1); return true }
            KeyEvent.KEYCODE_DPAD_DOWN, KeyEvent.KEYCODE_CHANNEL_DOWN -> { zap(+1); return true }
            KeyEvent.KEYCODE_DPAD_CENTER, KeyEvent.KEYCODE_ENTER, KeyEvent.KEYCODE_DPAD_LEFT,
            KeyEvent.KEYCODE_MENU, KeyEvent.KEYCODE_DPAD_RIGHT -> { showPanel(); return true }
            KeyEvent.KEYCODE_INFO -> { current?.let { showInfo(it) }; return true }
            KeyEvent.KEYCODE_BACK -> {
                val now = System.currentTimeMillis()
                if (now - lastBack < 2500) finish()
                else {
                    lastBack = now
                    Toast.makeText(this, "Nochmal Zurück zum Beenden", Toast.LENGTH_SHORT).show()
                }
                return true
            }
        }
        return super.dispatchKeyEvent(event)
    }

    // ---- Senderliste ---------------------------------------------------------------------------

    private inner class ChannelAdapter : RecyclerView.Adapter<ChannelAdapter.Holder>() {
        inner class Holder(v: View) : RecyclerView.ViewHolder(v) {
            val number: TextView = v.findViewById(R.id.number)
            val name: TextView = v.findViewById(R.id.name)
            val tag: TextView = v.findViewById(R.id.tag)
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): Holder {
            val v = LayoutInflater.from(parent.context).inflate(R.layout.item_channel, parent, false)
            val h = Holder(v)
            v.setOnClickListener { shown.getOrNull(h.bindingAdapterPosition)?.let { select(it) } }
            v.setOnLongClickListener { shown.getOrNull(h.bindingAdapterPosition)?.let { options(it) }; true }
            return h
        }

        override fun getItemCount() = shown.size

        override fun onBindViewHolder(h: Holder, position: Int) {
            val ch = shown[position]
            val nr = store.number(ch)
            h.number.text = if (nr > 0) nr.toString() else "–"
            h.number.background = badge(ch.color)
            h.name.text = ch.name
            val parts = mutableListOf<String>()
            if (ch.id in store.favorites) parts += "★"
            when (ch.kind) {
                Kind.JOYN -> parts += "Joyn"
                Kind.RTL -> parts += "RTL+"
                Kind.STREAM -> if (ch.id == current?.id) parts += "läuft"
            }
            h.tag.text = parts.joinToString("  ")
            h.tag.setTextColor(if (ch.id == current?.id) getColor(R.color.accent) else getColor(R.color.muted))
        }
    }
}
