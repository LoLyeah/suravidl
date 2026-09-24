package com.vidl.app

import android.os.Bundle
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val tv = TextView(this)
        tv.setPadding(48, 96, 48, 48)
        setContentView(tv)
        tv.text = try {
            if (!Python.isStarted()) Python.start(AndroidPlatform(this))
            val info = Python.getInstance().getModule("info")
            "vidl engine spike OK — bundled yt_dlp " + info.callAttr("yt_dlp_version").toString()
        } catch (e: Exception) {
            "spike FAILED: ${e.message}"
        }
    }
}
