package org.cellsentinel.client

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.telephony.SmsManager
import android.telephony.TelephonyManager
import android.util.Log

/**
 * SimChangeReceiver: Fires immediately when SIM card state changes.
 * If thief removes owner's SIM and inserts their own, this extracts the thief's SIM details
 * and uses their network to broadcast an emergency SMS to the owner's alternate contact.
 */
class SimChangeReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val tm = context.getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager ?: return
        val currentOperator = tm.simOperatorName
        val currentSimState = tm.simState

        if (currentSimState == TelephonyManager.SIM_STATE_READY) {
            val prefs = context.getSharedPreferences("sentinel_vault", Context.MODE_PRIVATE)
            val registeredOperator = prefs.getString("registered_operator", "")
            val emergencyNumber = prefs.getString("emergency_contact", "")

            Log.d("CellSentinel", "SIM state ready. Current: $currentOperator, Saved: $registeredOperator")

            // If a different SIM is detected
            if (!registeredOperator.isNullOrEmpty() && currentOperator != registeredOperator) {
                Log.w("CellSentinel", "ALERT: Rogue SIM inserted! Firing emergency silent SMS...")

                // Harvest current tower data
                val tower = TelemetryWorker.getPrimaryCellTower(context)
                val imei = prefs.getString("imei_number", "UNKNOWN_IMEI")

                val smsText = "ALERT: NEW SIM INSERTED ($currentOperator). IMEI:$imei Tower:[MCC:${tower.mcc},MNC:${tower.mnc},LAC:${tower.lac},CID:${tower.cellId}]"

                if (!emergencyNumber.isNullOrEmpty()) {
                    try {
                        val smsManager = SmsManager.getDefault()
                        smsManager.sendTextMessage(emergencyNumber, null, smsText, null, null)
                        Log.i("CellSentinel", "Emergency SMS successfully dispatched to $emergencyNumber")
                    } catch (e: Exception) {
                        Log.e("CellSentinel", "Failed to send emergency SMS: ${e.message}")
                    }
                }
            }
        }
    }
}

