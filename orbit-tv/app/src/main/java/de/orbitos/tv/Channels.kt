package de.orbitos.tv

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

data class Channel(
    val id: String,
    var name: String,
    var group: String,
    var url: String,
    val color: Int,
    val custom: Boolean = false,
)

/**
 * Alle Sender: die öffentlich-rechtlichen aus der mitgelieferten Liste (Adressen werden aus der freien
 * Zapp-Schnittstelle aktualisiert) und deine eigenen Sender (Name + Adresse), gespeichert auf dem Gerät.
 * Reihenfolge, Favoriten, Ausblenden und Gruppenzuordnung gelten für alle Sender.
 */
class ChannelStore(private val context: Context) {
    private val prefs: SharedPreferences = context.getSharedPreferences("orbit_tv2", Context.MODE_PRIVATE)
    private val all: MutableList<Channel> = (loadBuiltin() + loadCustom()).toMutableList()

    val favorites: MutableSet<String> = prefs.getStringSet("favoriten", emptySet())!!.toMutableSet()
    val hidden: MutableSet<String> = prefs.getStringSet("ausgeblendet", emptySet())!!.toMutableSet()
    private val groupOf: JSONObject = runCatching { JSONObject(prefs.getString("gruppen", "{}")!!) }.getOrDefault(JSONObject())
    private val order: MutableList<String> = run {
        val saved = prefs.getString("reihenfolge", null)?.split(",")?.filter { it.isNotBlank() } ?: emptyList()
        val known = all.map { it.id }
        (saved.filter { it in known } + known.filter { it !in saved }).toMutableList()
    }

    init {
        for (ch in all) groupOf.optString(ch.id).takeIf { it.isNotBlank() }?.let { ch.group = it }
    }

    private fun loadBuiltin(): List<Channel> {
        val text = context.assets.open("channels.json").bufferedReader(Charsets.UTF_8).use { it.readText() }
        val arr = JSONArray(text)
        val cached = prefs.getString("stream_adressen", null)?.let { runCatching { JSONObject(it) }.getOrNull() }
        return (0 until arr.length()).map { i ->
            val o = arr.getJSONObject(i)
            val id = o.getString("id")
            Channel(id, o.getString("name"), o.getString("group"),
                cached?.optString(id)?.takeIf { it.isNotBlank() } ?: o.optString("url", ""),
                runCatching { android.graphics.Color.parseColor(o.optString("color", "#333333")) }.getOrDefault(0xFF333333.toInt()))
        }
    }

    private fun loadCustom(): List<Channel> {
        val arr = runCatching { JSONArray(prefs.getString("eigene_sender", "[]")) }.getOrDefault(JSONArray())
        return (0 until arr.length()).map { i ->
            val o = arr.getJSONObject(i)
            Channel(o.getString("id"), o.getString("name"), o.optString("group", GROUP_OWN), o.getString("url"),
                colorFor(o.getString("name")), custom = true)
        }
    }

    private fun saveCustom() {
        val arr = JSONArray()
        all.filter { it.custom }.forEach {
            arr.put(JSONObject().put("id", it.id).put("name", it.name).put("group", it.group).put("url", it.url))
        }
        prefs.edit().putString("eigene_sender", arr.toString()).apply()
    }

    private fun saveOrder() = prefs.edit().putString("reihenfolge", order.joinToString(",")).apply()

    fun byId(id: String?): Channel? = all.firstOrNull { it.id == id }

    // ---- Eigene Sender ------------------------------------------------------------------------

    fun addCustom(name: String, url: String, group: String): Channel {
        val ch = Channel("eigen:" + System.currentTimeMillis().toString(36), name.trim(), group, url.trim(),
            colorFor(name), custom = true)
        all += ch
        order += ch.id
        saveCustom()
        saveOrder()
        return ch
    }

    fun editCustom(ch: Channel, name: String, url: String) {
        ch.name = name.trim()
        ch.url = url.trim()
        saveCustom()
    }

    fun delete(ch: Channel) {
        if (!ch.custom) return
        all.remove(ch)
        order.remove(ch.id)
        favorites.remove(ch.id)
        hidden.remove(ch.id)
        groupOf.remove(ch.id)
        saveCustom()
        saveOrder()
        prefs.edit().putStringSet("favoriten", favorites.toSet()).putStringSet("ausgeblendet", hidden.toSet())
            .putString("gruppen", groupOf.toString()).apply()
    }

    // ---- Gruppen ------------------------------------------------------------------------------

    /** Alle, Favoriten, ARD, ZDF, Dritte, Eigene, deine Gruppen – „Ausgeblendet“ nur wenn nötig. */
    fun groups(): List<String> {
        val used = all.map { it.group }.distinct()
        val user = used.filter { it !in FIXED }.sorted()
        val out = mutableListOf(GROUP_ALL, GROUP_FAV)
        out += FIXED.filter { it in used || it == GROUP_OWN }
        out += user
        if (hidden.isNotEmpty()) out += GROUP_HIDDEN
        return out
    }

    /** Gruppen, denen man einen Sender zuordnen kann. */
    fun assignableGroups(): List<String> = groups().filter { it !in listOf(GROUP_ALL, GROUP_FAV, GROUP_HIDDEN) }

    fun assign(ch: Channel, group: String) {
        ch.group = group.trim()
        groupOf.put(ch.id, ch.group)
        prefs.edit().putString("gruppen", groupOf.toString()).apply()
        if (ch.custom) saveCustom()
    }

    /** Sender in deiner Reihenfolge; ausgeblendete nur in „Ausgeblendet“. */
    fun list(group: String): List<Channel> {
        val sorted = order.mapNotNull { byId(it) }
        return when (group) {
            GROUP_ALL -> sorted.filter { it.id !in hidden }
            GROUP_FAV -> sorted.filter { it.id in favorites && it.id !in hidden }
            GROUP_HIDDEN -> sorted.filter { it.id in hidden }
            else -> sorted.filter { it.group == group && it.id !in hidden }
        }
    }

    /** Senderplatz wie auf der Fernbedienung (zählt in „Alle“). */
    fun number(ch: Channel): Int = list(GROUP_ALL).indexOfFirst { it.id == ch.id } + 1

    fun toggleFavorite(ch: Channel) {
        if (!favorites.remove(ch.id)) favorites.add(ch.id)
        prefs.edit().putStringSet("favoriten", favorites.toSet()).apply()
    }

    fun toggleHidden(ch: Channel) {
        if (!hidden.remove(ch.id)) hidden.add(ch.id)
        prefs.edit().putStringSet("ausgeblendet", hidden.toSet()).apply()
    }

    /** Sender innerhalb der sichtbaren Liste um [delta] Plätze verschieben. */
    fun move(ch: Channel, delta: Int, group: String): Boolean {
        val visible = list(group)
        val pos = visible.indexOfFirst { it.id == ch.id }
        val target = visible.getOrNull(pos + delta) ?: return false
        order.remove(ch.id)
        val t = order.indexOf(target.id)
        order.add(if (delta > 0) t + 1 else t, ch.id)
        saveOrder()
        return true
    }

    fun resetOrder() {
        order.clear()
        order.addAll(all.map { it.id })
        prefs.edit().remove("reihenfolge").apply()
    }

    var lastChannel: String?
        get() = prefs.getString("letzter_sender", null)
        set(v) { prefs.edit().putString("letzter_sender", v).apply() }

    // ---- Netz ---------------------------------------------------------------------------------

    /** Aktuelle Adressen der öffentlich-rechtlichen Sender holen (im Hintergrund aufrufen). */
    fun refreshStreams(): Boolean {
        val text = httpGet("$ZAPP_API/channelInfoList") ?: return false
        val obj = runCatching { JSONObject(text) }.getOrNull() ?: return false
        val urls = JSONObject()
        for (ch in all.filter { !it.custom }) {
            val url = obj.optJSONObject(ch.id)?.optString("streamUrl")
            if (!url.isNullOrBlank()) {
                ch.url = url
                urls.put(ch.id, url)
            }
        }
        prefs.edit().putString("stream_adressen", urls.toString()).apply()
        return true
    }

    private val nowCache = HashMap<String, Pair<Long, String?>>()

    /** „Jetzt läuft“ für öffentlich-rechtliche Sender (5 Minuten zwischengespeichert). */
    fun nowPlaying(ch: Channel): String? {
        if (ch.custom) return null
        synchronized(nowCache) {
            nowCache[ch.id]?.let { (t, v) -> if (System.currentTimeMillis() - t < 300_000) return v }
        }
        val text = httpGet("$ZAPP_API/shows/${ch.id}")
        val show = text?.let { runCatching { JSONObject(it).getJSONArray("shows").getJSONObject(0) }.getOrNull() }
        val title = show?.optString("title")?.takeIf { it.isNotBlank() }
        val sub = show?.optString("subtitle")?.takeIf { it.isNotBlank() && it != "null" }
        val v = title?.let { if (sub != null) "$it – $sub" else it }
        synchronized(nowCache) { nowCache[ch.id] = System.currentTimeMillis() to v }
        return v
    }

    fun cachedNow(ch: Channel): String? = synchronized(nowCache) { nowCache[ch.id]?.second }

    companion object {
        const val GROUP_ALL = "Alle"
        const val GROUP_FAV = "Favoriten"
        const val GROUP_OWN = "Eigene"
        const val GROUP_HIDDEN = "Ausgeblendet"
        val FIXED = listOf("ARD", "ZDF", "Dritte", GROUP_OWN)
        private const val ZAPP_API = "https://api.zapp.mediathekview.de/v1"

        private val PALETTE = intArrayOf(0xFF3E5C8A.toInt(), 0xFF7A4E8C.toInt(), 0xFF2F7A6B.toInt(),
            0xFF9A5B3C.toInt(), 0xFF5A6B2F.toInt(), 0xFF8C3E52.toInt(), 0xFF3C6F9A.toInt(), 0xFF6B5A43.toInt())

        fun colorFor(name: String) = PALETTE[Math.floorMod(name.trim().lowercase().hashCode(), PALETTE.size)]

        fun validUrl(url: String) = Regex("^https?://\\S+$", RegexOption.IGNORE_CASE).matches(url.trim())

        fun httpGet(url: String): String? = runCatching {
            var target = url
            var result: String? = null
            for (hop in 0 until 5) {                     // Weiterleitungen auch von http nach https folgen
                val c = URL(target).openConnection() as HttpURLConnection
                c.connectTimeout = 6000
                c.readTimeout = 6000
                c.instanceFollowRedirects = false
                c.setRequestProperty("User-Agent", "OrbitTV/2.0 (Fire TV)")
                try {
                    val code = c.responseCode
                    if (code in 300..399) {
                        target = URL(URL(target), c.getHeaderField("Location") ?: break).toString()
                        continue
                    }
                    if (code == 200) result = c.inputStream.bufferedReader().use { r ->
                        val buf = CharArray(512 * 1024)
                        val n = r.read(buf)
                        if (n > 0) String(buf, 0, n) else ""
                    }
                } finally {
                    c.disconnect()
                }
                break
            }
            result
        }.getOrNull()

        private val PLAYLIST = Regex("\\.(m3u|pls|asx)(\\?|$)", RegexOption.IGNORE_CASE)

        /**
         * Eine .m3u-Adresse kann eine HLS-Wiedergabeliste sein (dann direkt abspielen) oder eine einfache
         * Liste mit einer Stream-Adresse darin (dann den ersten Eintrag nehmen).
         */
        fun resolvePlaylist(url: String): String {
            if (!PLAYLIST.containsMatchIn(url)) return url
            val text = httpGet(url) ?: return url
            if (text.contains("#EXT-X-")) return url
            val first = text.lines().map { it.trim() }.firstOrNull { it.isNotEmpty() && !it.startsWith("#") } ?: return url
            return runCatching { URL(URL(url), first).toString() }.getOrDefault(url)
        }
    }
}
