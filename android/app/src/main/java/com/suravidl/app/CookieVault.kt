package com.suravidl.app

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.io.File
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Cookies at rest, on Android.
 *
 * The imported cookies.txt is encrypted with an AES-256-GCM key that lives in
 * the Android Keystore and cannot be exported — the ciphertext (cookies.enc)
 * is useless on another device or after a factory reset. A readable copy
 * (cookies.session.txt) is created only while the app runs, is owner-only,
 * and is deleted on quit, on delete, or on the next start; the engine reads
 * that file and nothing else.
 *
 * Out of scope by design: a rooted device or a live memory dump can read the
 * session file while the app runs — that is the price of handing yt-dlp a
 * plain Netscape cookie file at all.
 */
object CookieVault {
    private const val KEY_ALIAS = "suravidl-cookies-v1"
    private const val ENC = "cookies.enc"
    private const val SESSION = "cookies.session.txt"
    private const val LEGACY = "cookies.txt"
    private const val IV_LEN = 12

    private fun key(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getEntry(KEY_ALIAS, null) as? KeyStore.SecretKeyEntry)?.let {
            return it.secretKey
        }
        val gen = KeyGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        gen.init(
            KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build())
        return gen.generateKey()
    }

    private fun ownerOnly(f: File) {
        f.setReadable(false, false)
        f.setReadable(true, true)
        f.setWritable(false, false)
        f.setWritable(true, true)
    }

    private fun sessionFile(context: Context) = File(context.filesDir, SESSION)

    fun has(context: Context): Boolean = File(context.filesDir, ENC).exists()

    /** Encrypt the imported cookies and drop every readable copy. */
    fun save(context: Context, plaintext: ByteArray) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val blob = cipher.iv + cipher.doFinal(plaintext)
        val target = File(context.filesDir, ENC)
        target.outputStream().use { it.write(blob) }
        ownerOnly(target)
        // the SAF copy the user picked is outside our storage; ours must go
        File(context.filesDir, LEGACY).delete()
        File(context.filesDir, SESSION).delete()
    }

    /** Decrypt into the session file the engine reads. Null when nothing is stored. */
    fun unlockForSession(context: Context): File? {
        val source = File(context.filesDir, ENC)
        if (!source.exists()) return null
        val blob = source.readBytes()
        val out = File(context.filesDir, SESSION)
        try {
            require(blob.size > IV_LEN) { "cookie blob is truncated" }
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, key(),
                        GCMParameterSpec(128, blob.copyOfRange(0, IV_LEN)))
            val plain = cipher.doFinal(blob.copyOfRange(IV_LEN, blob.size))
            out.outputStream().use { it.write(plain) }
            ownerOnly(out)
            plain.fill(0)
            File(context.filesDir, LEGACY).delete()
            return out
        } catch (t: Throwable) {
            // A blob this device's key cannot open is unreadable forever: that
            // key never leaves the Keystore and does not survive a reinstall or
            // a restore from backup. Keeping it would leave the settings row
            // promising cookies the engine can never get, and every start
            // retrying the same failure (v0.21.1 audit) — drop it and say so.
            delete(context)
            throw IllegalStateException(
                "the saved cookies cannot be read on this device (the key does " +
                "not survive a reinstall or a restore) — import cookies.txt again",
                t)
        }
    }

    fun sessionPath(context: Context): String =
        File(context.filesDir, SESSION).absolutePath

    fun lockSession(context: Context) {
        sessionFile(context).delete()
    }

    fun delete(context: Context) {
        File(context.filesDir, ENC).delete()
        sessionFile(context).delete()
        File(context.filesDir, LEGACY).delete()
    }

    /** Versions before the vault kept cookies.txt in the clear: fold it in. */
    fun migrateLegacy(context: Context): Boolean {
        val legacy = File(context.filesDir, LEGACY)
        if (!legacy.exists()) return false
        if (File(context.filesDir, ENC).exists()) {
            legacy.delete()          // vault already has the newer import
            return false
        }
        return try {
            save(context, legacy.readBytes())
            true
        } catch (e: Throwable) {
            legacy.delete()          // never leave a half-migrated readable copy
            false
        }
    }

    /** What the settings row shows. */
    fun status(context: Context): String = when {
        has(context) -> "stored and encrypted (Android Keystore) — a readable copy " +
            "exists only while the app runs"
        else -> "no stored cookies"
    }
}
