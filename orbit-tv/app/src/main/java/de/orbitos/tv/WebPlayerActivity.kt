package de.orbitos.tv

import android.annotation.SuppressLint
import android.app.Activity
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.TextView
import android.widget.Toast

/**
 * Offizieller Web-Player von Joyn bzw. RTL+ in Orbit TV. Du meldest dich dort selbst mit deinem
 * Konto an; der Kopierschutz (Widevine) läuft über den Browser des Fire TV – nichts wird umgangen.
 * Die Fernbedienung steuert einen Mauszeiger: Pfeile bewegen, OK klickt, ☰ öffnet die App,
 * Zurück geht eine Seite zurück bzw. schließt den Player.
 */
class WebPlayerActivity : Activity() {
    private lateinit var web: WebView
    private lateinit var cursor: CursorView
    private lateinit var root: FrameLayout
    private var fullscreen: View? = null
    private var fullscreenCallback: WebChromeClient.CustomViewCallback? = null
    private var partnerKind: Kind = Kind.JOYN
    private var held = 0
    private val ui = Handler(Looper.getMainLooper())

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        partnerKind = if (intent.getStringExtra(EXTRA_KIND) == "rtl") Kind.RTL else Kind.JOYN
        root = FrameLayout(this).apply { setBackgroundColor(Color.BLACK) }
        web = WebView(this)
        cursor = CursorView(this)
        root.addView(web, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        root.addView(cursor, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        root.addView(TextView(this).apply {
            text = "Pfeile: Zeiger · OK: klicken · ☰: ${Partners.of(partnerKind)?.name}-App · Zurück: schließen"
            setTextColor(0xCCDCE6FF.toInt())
            textSize = 13f
            setBackgroundColor(0x9912151B.toInt())
            setPadding(24, 10, 24, 10)
        }, FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
            gravity = android.view.Gravity.BOTTOM or android.view.Gravity.END
        })
        setContentView(root)

        CookieManager.getInstance().setAcceptCookie(true)
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, true)
        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            mediaPlaybackRequiresUserGesture = false
            loadWithOverviewMode = true
            useWideViewPort = true
            // Wie ein Desktop-Chrome, damit die Seiten ihren normalen Web-Player zeigen
            userAgentString = DESKTOP_UA
        }
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val scheme = request.url.scheme ?: ""
                return scheme != "http" && scheme != "https"      // App-Links o. Ä. nicht öffnen
            }
        }
        web.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(request: PermissionRequest) {
                // Nur den Kopierschutz für Videos erlauben – sonst spielen die Sender nicht
                val allowed = request.resources.filter { it == PermissionRequest.RESOURCE_PROTECTED_MEDIA_ID }
                if (allowed.isNotEmpty()) request.grant(allowed.toTypedArray()) else request.deny()
            }

            override fun onShowCustomView(view: View, callback: CustomViewCallback) {
                fullscreen = view
                fullscreenCallback = callback
                root.addView(view, 1, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
            }

            override fun onHideCustomView() {
                fullscreen?.let { root.removeView(it) }
                fullscreen = null
                fullscreenCallback?.onCustomViewHidden()
                fullscreenCallback = null
            }
        }
        web.loadUrl(intent.getStringExtra(EXTRA_URL) ?: "about:blank")
        cursor.post { cursor.moveTo(root.width / 2f, root.height / 2f) }
    }

    override fun onPause() {
        super.onPause()
        web.onPause()
        CookieManager.getInstance().flush()
    }

    override fun onResume() {
        super.onResume()
        web.onResume()
    }

    override fun onDestroy() {
        web.destroy()
        super.onDestroy()
    }

    private fun click() {
        val x = cursor.x0
        val y = cursor.y0
        val t = SystemClock.uptimeMillis()
        val target: View = fullscreen ?: web
        val loc = IntArray(2)
        target.getLocationInWindow(loc)
        val down = MotionEvent.obtain(t, t, MotionEvent.ACTION_DOWN, x - loc[0], y - loc[1], 0)
        val up = MotionEvent.obtain(t, t + 60, MotionEvent.ACTION_UP, x - loc[0], y - loc[1], 0)
        target.dispatchTouchEvent(down)
        target.dispatchTouchEvent(up)
        down.recycle()
        up.recycle()
        cursor.pulse()
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        val code = event.keyCode
        // Texteingabe (Anmeldung): Tastatur-Tasten an die Seite weitergeben
        val arrows = code == KeyEvent.KEYCODE_DPAD_UP || code == KeyEvent.KEYCODE_DPAD_DOWN ||
            code == KeyEvent.KEYCODE_DPAD_LEFT || code == KeyEvent.KEYCODE_DPAD_RIGHT
        if (event.action == KeyEvent.ACTION_UP) {
            if (arrows) held = 0
            return if (arrows || code == KeyEvent.KEYCODE_DPAD_CENTER || code == KeyEvent.KEYCODE_ENTER ||
                code == KeyEvent.KEYCODE_MENU || code == KeyEvent.KEYCODE_BACK) true else super.dispatchKeyEvent(event)
        }
        if (arrows) {
            held++
            val step = (14f + held * 6f).coerceAtMost(70f) * resources.displayMetrics.density / 2f
            var dx = 0f
            var dy = 0f
            when (code) {
                KeyEvent.KEYCODE_DPAD_UP -> dy = -step
                KeyEvent.KEYCODE_DPAD_DOWN -> dy = step
                KeyEvent.KEYCODE_DPAD_LEFT -> dx = -step
                KeyEvent.KEYCODE_DPAD_RIGHT -> dx = step
            }
            val nx = (cursor.x0 + dx).coerceIn(0f, root.width.toFloat() - 1)
            val ny = cursor.y0 + dy
            // Am oberen/unteren Rand blättert die Seite
            if (ny < 0f) web.scrollBy(0, dy.toInt()) else if (ny > root.height - 1) web.scrollBy(0, dy.toInt())
            cursor.moveTo(nx, ny.coerceIn(0f, root.height.toFloat() - 1))
            return true
        }
        when (code) {
            KeyEvent.KEYCODE_DPAD_CENTER, KeyEvent.KEYCODE_ENTER -> { if (event.repeatCount == 0) click(); return true }
            KeyEvent.KEYCODE_MENU -> {
                val p = Partners.of(partnerKind)
                if (p != null && !Partners.open(this, p)) Toast.makeText(this, "${p.name}-App ist nicht installiert", Toast.LENGTH_SHORT).show()
                return true
            }
            KeyEvent.KEYCODE_BACK -> {
                when {
                    fullscreen != null -> web.webChromeClient?.onHideCustomView()
                    web.canGoBack() -> web.goBack()
                    else -> finish()
                }
                return true
            }
            KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE -> {
                web.evaluateJavascript("(function(){var v=document.querySelector('video');if(v){v.paused?v.play():v.pause();}})()", null)
                return true
            }
        }
        return super.dispatchKeyEvent(event)
    }

    /** Einfacher Mauszeiger für die Fernbedienung. */
    class CursorView(context: Context) : View(context) {
        var x0 = 0f
            private set
        var y0 = 0f
            private set
        private var pulseUntil = 0L
        private val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.WHITE }
        private val edge = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = 0xFF12151B.toInt(); style = Paint.Style.STROKE; strokeWidth = 3f
        }
        private val ring = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = 0xFF8FB3FF.toInt(); style = Paint.Style.STROKE; strokeWidth = 5f
        }

        fun moveTo(x: Float, y: Float) { x0 = x; y0 = y; invalidate() }

        fun pulse() { pulseUntil = SystemClock.uptimeMillis() + 250; invalidate(); postDelayed({ invalidate() }, 260) }

        override fun onDraw(c: Canvas) {
            val s = resources.displayMetrics.density * 14
            val p = Path().apply {
                moveTo(x0, y0); lineTo(x0, y0 + s * 1.6f); lineTo(x0 + s * 0.45f, y0 + s * 1.2f)
                lineTo(x0 + s * 0.8f, y0 + s * 1.9f); lineTo(x0 + s * 1.05f, y0 + s * 1.75f)
                lineTo(x0 + s * 0.7f, y0 + s * 1.08f); lineTo(x0 + s * 1.2f, y0 + s * 1.08f); close()
            }
            c.drawPath(p, fill)
            c.drawPath(p, edge)
            if (SystemClock.uptimeMillis() < pulseUntil) c.drawCircle(x0, y0, s * 1.1f, ring)
        }
    }

    companion object {
        const val EXTRA_URL = "url"
        const val EXTRA_KIND = "kind"
        const val DESKTOP_UA =
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    }
}
