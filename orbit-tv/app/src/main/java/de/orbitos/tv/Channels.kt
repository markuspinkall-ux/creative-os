package de.orbitos.tv

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** Wie ein Sender läuft: direkt in Orbit TV oder über die offizielle App (mit deinem Konto). */
enum class Kind { STREAM, JOYN, RTL }

data class Channel(
    val id: String,
    val name: String,
    val group: String,
    val kind: Kind,
    var url: String,
    val color: Int,
)

/**
 * Senderliste mit eigener Reihenfolge, Favoriten und ausgeblendeten Sendern.
 * Die Stream-Adressen der öffentlich-rechtlichen Sender kommen aus der mitgelieferten Liste und
 * werden beim Start aus der freien Zapp-Schnittstelle (MediathekView) aktualisiert.
 */
class ChannelStore(private val context: Context) {
    private val prefs: SharedPreferences = context.getSharedPreferences("orbit_tv", Context.MODE_PRIVATE)
    private val all: List<Channel> = load()

    val favorites: MutableSet<String> = prefs.getStringSet("favoriten", emptySet())!!.toMutableSet()
    val hidden: MutableSet<String> = prefs.getStringSet("ausgeblendet", emptySet())!!.toMutableSet()
    private val order: MutableList<String> = run {
        val saved = prefs.getString("reihenfolge", null)?.split(",")?.filter { it.isNotBlank() } ?: emptyList()
        val known = all.map { it.id }
        (saved.filter { it in known } + known.filter { it !in saved }).toMutableList()
    }

    private fun load(): List<Channel> {
        val text = context.assets.open("channels.json").bufferedReader(Charsets.UTF_8).use { it.readText() }
        val arr = JSONArray(text)
        val cached = prefs.getString("stream_adressen", null)?.let { runCatching { JSONObject(it) }.getOrNull() }
        return (0 until arr.length()).map { i ->
            val o = arr.getJSONObject(i)
            val id = o.getString("id")
            Channel(
                id = id,
                name = o.getString("name"),
                group = o.getString("group"),
                kind = when (o.getString("kind")) { "joyn" -> Kind.JOYN; "rtl" -> Kind.RTL; else -> Kind.STREAM },
                url = cached?.optString(id)?.takeIf { it.isNotBlank() } ?: o.optString("url", ""),
                color = runCatching { android.graphics.Color.parseColor(o.optString("color", "#333333")) }
                    .getOrDefault(0xFF333333.toInt()),
            )
        }
    }

    fun byId(id: String?): Channel? = all.firstOrNull { it.id == id }

    /** Sender in deiner Reihenfolge; ausgeblendete nur in der Gruppe „Ausgeblendet“. */
    fun list(group: String): List<Channel> {
        val sorted = order.mapNotNull { byId(it) }
        return when (group) {
            GROUP_ALL -> sorted.filter { it.id !in hidden }
            GROUP_FAV -> sorted.filter { it.id in favorites && it.id !in hidden }
            GROUP_HIDDEN -> sorted.filter { it.id in hidden }
            else -> sorted.filter { it.group == group && it.id !in hidden }
        }
    }

    /** Senderplatz (1, 2, 3 …) wie auf der Fernbedienung – zählt in „Alle“. */
    fun number(ch: Channel): Int = list(GROUP_ALL).indexOfFirst { it.id == ch.id } + 1

    fun toggleFavorite(ch: Channel) {
        if (!favorites.remove(ch.id)) favorites.add(ch.id)
        prefs.edit().putStringSet("favoriten", favorites.toSet()).apply()
    }

    fun toggleHidden(ch: Channel) {
        if (!hidden.remove(ch.id)) hidden.add(ch.id)
        prefs.edit().putStringSet("ausgeblendet", hidden.toSet()).apply()
    }

    /** Einen Platz nach oben (-1) oder unten (+1) – bezogen auf die sichtbare Liste. */
    fun move(ch: Channel, delta: Int, group: String) {
        val visible = list(group)
        val pos = visible.indexOfFirst { it.id == ch.id }
        val target = visible.getOrNull(pos + delta) ?: return
        val a = order.indexOf(ch.id)
        val b = order.indexOf(target.id)
        order[a] = target.id
        order[b] = ch.id
        prefs.edit().putString("reihenfolge", order.joinToString(",")).apply()
    }

    fun resetOrder() {
        order.clear()
        order.addAll(all.map { it.id })
        prefs.edit().remove("reihenfolge").apply()
    }

    var lastChannel: String?
        get() = prefs.getString("letzter_sender", null)
        set(v) { prefs.edit().putString("letzter_sender", v).apply() }

    /** Aktuelle Stream-Adressen holen (läuft im Hintergrund, ohne Internet bleibt die alte Liste). */
    fun refreshStreams(): Boolean {
        val text = httpGet("$ZAPP_API/channelInfoList") ?: return false
        val obj = runCatching { JSONObject(text) }.getOrNull() ?: return false
        val urls = JSONObject()
        for (ch in all) {
            val url = obj.optJSONObject(ch.id)?.optString("streamUrl")
            if (!url.isNullOrBlank()) {
                ch.url = url
                urls.put(ch.id, url)
            }
        }
        prefs.edit().putString("stream_adressen", urls.toString()).apply()
        return true
    }

    /** „Jetzt läuft“ für öffentlich-rechtliche Sender (Zapp-Programmdaten). */
    fun nowPlaying(ch: Channel): String? {
        if (ch.kind != Kind.STREAM) return null
        val text = httpGet("$ZAPP_API/shows/${ch.id}") ?: return null
        val show = runCatching { JSONObject(text).getJSONArray("shows").getJSONObject(0) }.getOrNull() ?: return null
        val title = show.optString("title").takeIf { it.isNotBlank() } ?: return null
        val sub = show.optString("subtitle").takeIf { it.isNotBlank() && it != "null" }
        return if (sub != null) "$title – $sub" else title
    }

    companion object {
        const val GROUP_ALL = "Alle"
        const val GROUP_FAV = "Favoriten"
        const val GROUP_HIDDEN = "Ausgeblendet"
        val GROUPS = listOf(GROUP_ALL, GROUP_FAV, "ARD", "ZDF", "Dritte", "Joyn", "RTL+", GROUP_HIDDEN)
        private const val ZAPP_API = "https://api.zapp.mediathekview.de/v1"

        fun httpGet(url: String): String? = runCatching {
            val c = URL(url).openConnection() as HttpURLConnection
            c.connectTimeout = 6000
            c.readTimeout = 6000
            c.setRequestProperty("User-Agent", "OrbitTV/1.0 (Fire TV)")
            try {
                if (c.responseCode != 200) null else c.inputStream.bufferedReader().use { it.readText() }
            } finally {
                c.disconnect()
            }
        }.getOrNull()
    }
}
