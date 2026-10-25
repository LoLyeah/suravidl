package com.suravidl.app

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

/**
 * v0.47.14 "the seal": the hand-off boundary is canonical, so neither a
 * look-alike sibling directory nor a `..` climb can pass for a download.
 */
class PathGuardTest {
    @get:Rule
    val tmp = TemporaryFolder()

    @Test
    fun aFileBelowTheRootIsInside() {
        val root = tmp.newFolder("suravidl")
        val file = File(root, "Movie.mp4")
        file.writeText("x")
        assertTrue(PathGuard.inside(file, root))
        assertTrue(PathGuard.inside(root, root))
    }

    @Test
    fun aLookAlikeSiblingIsNotInside() {
        val root = tmp.newFolder("suravidl")
        val sibling = tmp.newFolder("suravidl2")
        val file = File(sibling, "Movie.mp4")
        file.writeText("x")
        assertFalse(PathGuard.inside(file, root))
    }

    @Test
    fun aClimbOutIsNotInside() {
        val root = tmp.newFolder("suravidl")
        val outside = File(root, "../updates/update.apk")
        outside.parentFile?.mkdirs()
        outside.writeText("x")
        assertFalse(PathGuard.inside(outside, root))
    }

    @Test
    fun anyRootSufficesAndAnEmptyListRefuses() {
        val movies = tmp.newFolder("movies")
        val files = tmp.newFolder("files")
        val f = File(files, "a.mkv")
        f.writeText("x")
        assertTrue(PathGuard.insideAny(f, listOf(movies, files)))
        assertFalse(PathGuard.insideAny(f, emptyList()))
    }
}
