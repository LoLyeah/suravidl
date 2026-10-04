package com.suravidl.app

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Pure logic for update installation safety on the JVM. */
class UpdateInstallTest {

    @Test
    fun traversalAttemptsAndInvalidNamesAreRejected() {
        assertFalse(UpdateInstallPolicy.safeName("../x.apk"))
        assertFalse(UpdateInstallPolicy.safeName("a/b.apk"))
        assertFalse(UpdateInstallPolicy.safeName("a\\b.apk"))
        assertFalse(UpdateInstallPolicy.safeName("x.exe"))
        assertFalse(UpdateInstallPolicy.safeName(""))
        assertFalse(UpdateInstallPolicy.safeName(".apk"))
    }

    @Test
    fun validApkNameIsAccepted() {
        assertTrue(UpdateInstallPolicy.safeName("app-release.apk"))
    }

    @Test
    fun needsUnknownSourcesPromptMatrix() {
        // sdk 24: no per-app toggle existed
        assertFalse(UpdateInstallPolicy.needsUnknownSourcesPrompt(24, canRequest = false))
        assertFalse(UpdateInstallPolicy.needsUnknownSourcesPrompt(24, canRequest = true))

        // sdk 26: prompts only when permission has not been granted
        assertFalse(UpdateInstallPolicy.needsUnknownSourcesPrompt(26, canRequest = true))
        assertTrue(UpdateInstallPolicy.needsUnknownSourcesPrompt(26, canRequest = false))
    }
}
