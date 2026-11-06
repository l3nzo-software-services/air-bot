package org.cellsentinel.client

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

/**
 * BootReceiver: Automatically executes within seconds of phone startup.
 * Runs at OS boot before user unlocks screen.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED || 
            intent.action == "android.intent.action.QUICKBOOT_POWERON") {
            Log.d("CellSentinel", "Phone Boot / Restart detected! Initializing telemetry...")
            
            // Trigger immediate background cell tower inspection
            TelemetryWorker.enqueueImmediateBeacon(context)
        }
    }
}

