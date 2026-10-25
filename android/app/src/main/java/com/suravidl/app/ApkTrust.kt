package com.suravidl.app

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import java.io.File

/**
 * Is this update APK really *ours*? (v0.47.14 "the seal")
 *
 * The sha256 in version.json protects the bytes in transit, but it comes
 * from the same channel as the file: whoever can rewrite one can rewrite
 * both. The signing certificate is the only part of an update a hostile
 * channel cannot forge — so an APK is only handed to the installer when it
 * carries exactly the certificate the installed app already has, and the
 * package name matches too.
 */
object ApkTrust {

    /** The package name inside an APK, or null when it cannot be read. */
    fun packageOf(context: Context, apk: File): String? = try {
        context.packageManager
            .getPackageArchiveInfo(apk.absolutePath, 0)?.packageName
    } catch (_: Throwable) {
        null
    }

    /**
     * True when `apk` is signed with the same certificate set as the
     * running app. False on anything unexpected — a refusal is the safe
     * answer here, never a benefit of the doubt.
     */
    fun signedLikeSelf(context: Context, apk: File): Boolean {
        val pm = context.packageManager
        val flags = if (Build.VERSION.SDK_INT >= 28) {
            PackageManager.GET_SIGNING_CERTIFICATES
        } else {
            @Suppress("DEPRECATION")
            PackageManager.GET_SIGNATURES
        }
        val incoming = try {
            pm.getPackageArchiveInfo(apk.absolutePath, flags)
        } catch (_: Throwable) {
            null
        } ?: return false
        val mine = try {
            pm.getPackageInfo(context.packageName, flags)
        } catch (_: Throwable) {
            null
        } ?: return false
        val theirs = signaturesOf(incoming)
        val ours = signaturesOf(mine)
        if (theirs.isEmpty() || ours.isEmpty()) return false
        // every signer of the update must be one of ours, and vice versa:
        // an update signed by an extra key is still a different identity
        return theirs == ours
    }

    /** A comparable identity for a package: its signer certificates. */
    fun signaturesOf(info: android.content.pm.PackageInfo): Set<String> {
        val out = mutableSetOf<String>()
        try {
            if (Build.VERSION.SDK_INT >= 28) {
                val si = info.signingInfo ?: return out
                val signers = if (si.hasMultipleSigners()) {
                    si.apkContentsSigners
                } else {
                    si.signingCertificateHistory
                }
                signers?.forEach { out.add(it.toCharsString()) }
            } else {
                @Suppress("DEPRECATION")
                info.signatures?.forEach { out.add(it.toCharsString()) }
            }
        } catch (_: Throwable) {
            return emptySet()
        }
        return out
    }
}
