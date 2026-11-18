package de.orbitos.tv

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri

/**
 * Joyn und RTL+ zeigen ihre Sender nur in ihren eigenen Apps (Kopierschutz). Orbit TV startet die
 * offizielle App – angemeldet bist du dort mit deinem eigenen Konto.
 */
object Partners {
    data class Partner(val name: String, val packages: List<String>, val labels: List<Regex>, val liveUrl: String, val store: String, val webUrl: String)

    val JOYN = Partner(
        name = "Joyn",
        packages = listOf("de.prosiebensat1digital.seventv", "de.prosiebensat1digital.joyn"),
        labels = listOf(Regex("^joyn", RegexOption.IGNORE_CASE)),
        liveUrl = "https://www.joyn.de/play/live-tv",
        store = "Joyn",
        webUrl = "https://www.joyn.de/play/live-tv",
    )
    val RTL = Partner(
        name = "RTL+",
        packages = listOf("de.cbc.vp2gen.rtlplus", "de.rtli.tvnow", "de.cbc.vp2gen"),
        labels = listOf(Regex("^rtl\\s*\\+", RegexOption.IGNORE_CASE), Regex("^rtl\\s*plus", RegexOption.IGNORE_CASE)),
        liveUrl = "https://plus.rtl.de/video-tv/live-tv",
        store = "RTL+",
        webUrl = "https://plus.rtl.de/video-tv/live-tv",
    )

    fun of(kind: Kind): Partner? = when (kind) {
        Kind.JOYN -> JOYN
        Kind.RTL -> RTL
        Kind.STREAM -> null
    }

    /** Paketname der installierten App – über bekannte Namen oder den angezeigten App-Namen. */
    fun installedPackage(context: Context, p: Partner): String? {
        val pm = context.packageManager
        for (pkg in p.packages) {
            if (launchIntent(pm, pkg) != null) return pkg
        }
        val intents = listOf(
            Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LEANBACK_LAUNCHER),
            Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER),
        )
        for (intent in intents) {
            for (info in pm.queryIntentActivities(intent, 0)) {
                val label = info.loadLabel(pm).toString().trim()
                if (p.labels.any { it.containsMatchIn(label) }) return info.activityInfo.packageName
            }
        }
        return null
    }

    private fun launchIntent(pm: PackageManager, pkg: String): Intent? =
        pm.getLeanbackLaunchIntentForPackage(pkg) ?: pm.getLaunchIntentForPackage(pkg)

    /** Startet die App, möglichst direkt im Live-TV. Gibt false zurück, wenn sie fehlt. */
    fun open(context: Context, p: Partner): Boolean {
        val pkg = installedPackage(context, p) ?: return false
        val pm = context.packageManager
        val live = Intent(Intent.ACTION_VIEW, Uri.parse(p.liveUrl)).setPackage(pkg)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        val start = if (live.resolveActivity(pm) != null) live else launchIntent(pm, pkg)?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return runCatching { context.startActivity(start); true }.getOrDefault(false)
    }

    /** Amazon Appstore mit der Suche nach der App öffnen. */
    fun openStore(context: Context, p: Partner) {
        val intents = listOf(
            Intent(Intent.ACTION_VIEW, Uri.parse("amzn://apps/android?s=" + Uri.encode(p.store))),
            Intent(Intent.ACTION_VIEW, Uri.parse("market://search?q=" + Uri.encode(p.store))),
        )
        for (i in intents) {
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            if (runCatching { context.startActivity(i); true }.getOrDefault(false)) return
        }
    }
}
