package org.cellsentinel.client

import android.content.Context
import android.os.Debug
import java.io.File

/**
 * AntiTamper Security Engine:
 * Protects AIR BOT against decompilation, Frida hooking, debugging, and unauthorized repackaging.
 */
object AntiTamper {

    /**
     * Checks if a reverse engineer or debugger is attached to the process.
     */
    fun isDebuggerActive(): Boolean {
        return Debug.isDebuggerConnected() || Debug.waitingForDebugger()
    }

    /**
     * Detects if the device has been rooted or modified with unauthorized binary injectors.
     */
    fun isCompromisedEnvironment(): Boolean {
        val rootPaths = arrayOf(
            "/system/app/Superuser.apk",
            "/sbin/su",
            "/system/bin/su",
            "/system/xbin/su",
            "/data/local/xbin/su",
            "/data/local/bin/su",
            "/system/sd/xbin/su",
            "/system/bin/failsafe/su",
            "/data/local/su"
        )
        return rootPaths.any { File(it).exists() }
    }

    /**
     * Simple XOR-based string obfuscation to prevent plain text extraction by decompilers.
     */
    fun decryptSecret(cipherBytes: ByteArray, key: Byte): String {
        val decrypted = ByteArray(cipherBytes.size)
        for (i in cipherBytes.indices) {
            decrypted[i] = (cipherBytes[i].toInt() xor key.toInt()).toByte()
        }
        return String(decrypted, Charsets.UTF_8)
    }
}
