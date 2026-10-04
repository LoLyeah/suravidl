package com.suravidl.app

/**
 * pure-logic validation for update installation requests arriving via the
 * JS bridge. no android framework dependencies so this can be unit tested
 * on a standard jvm.
 */
object UpdateInstallPolicy {

    /**
     * accept only a plain "*.apk" name with no path traversal components.
     * prevents an in-app page from asking the installer to resolve files
     * outside the updates staging directory.
     */
    fun safeName(fileName: String): Boolean {
        if (fileName.isEmpty() || !fileName.endsWith(".apk")) return false
        if (fileName.contains('/') || fileName.contains('\\') || fileName.contains("..")) return false
        return fileName != ".apk"
    }

    /**
     * on android 8.0+ (api 26), apps require the REQUEST_INSTALL_PACKAGES
     * permission and the user must grant "install unknown apps" for this app.
     * prior to api 26, unknown sources was a global device setting rather
     * than a per-app toggle.
     */
    fun needsUnknownSourcesPrompt(sdk: Int, canRequest: Boolean): Boolean =
        if (sdk < 26) false else !canRequest
}
