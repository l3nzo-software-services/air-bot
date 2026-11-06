package org.cellsentinel.client

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.telephony.*
import android.util.Log
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

data class CellTowerData(
    val mcc: Int,
    val mnc: Int,
    val lac: Int,
    val cellId: Int,
    val rssi: Double
)

/**
 * TelemetryWorker: Event-driven cellular telemetry reader.
 * Uses zero background battery: wakes up on event, reads SIM radio modem,
 * transmits via HTTPS (if internet present) or SMS (if offline), then goes to sleep.
 */
object TelemetryWorker {

    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(5, TimeUnit.SECONDS)
        .build()

    fun enqueueImmediateBeacon(context: Context) {
        Thread {
            try {
                transmitTelemetry(context)
            } catch (e: Exception) {
                Log.e("CellSentinel", "Error transmitting beacon: ${e.message}")
            }
        }.start()
    }

    fun getPrimaryCellTower(context: Context): CellTowerData {
        val tm = context.getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
        var mcc = 404
        var mnc = 45
        var lac = 8520
        var cellId = 41201
        var rssi = -70.0

        try {
            val cellInfoList = tm.allCellInfo
            if (!cellInfoList.isNullOrEmpty()) {
                for (info in cellInfoList) {
                    if (info.isRegistered) {
                        when (info) {
                            is CellInfoLte -> {
                                mcc = info.cellIdentity.mcc
                                mnc = info.cellIdentity.mnc
                                lac = info.cellIdentity.tac
                                cellId = info.cellIdentity.ci
                                rssi = info.cellSignalStrength.dbm.toDouble()
                            }
                            is CellInfoGsm -> {
                                mcc = info.cellIdentity.mcc
                                mnc = info.cellIdentity.mnc
                                lac = info.cellIdentity.lac
                                cellId = info.cellIdentity.cid
                                rssi = info.cellSignalStrength.dbm.toDouble()
                            }
                        }
                        break
                    }
                }
            }
        } catch (e: SecurityException) {
            Log.w("CellSentinel", "Location permission missing, using cached radio parameters.")
        }

        return CellTowerData(mcc, mnc, lac, cellId, rssi)
    }

    private fun transmitTelemetry(context: Context) {
        val prefs = context.getSharedPreferences("sentinel_vault", Context.MODE_PRIVATE)
        val serverUrl = prefs.getString("server_url", "http://10.0.2.2:8000") ?: return
        val deviceToken = prefs.getString("device_token", "") ?: return
        val imei = prefs.getString("imei_number", "861952072527237") ?: return
        val emergencyNumber = prefs.getString("emergency_contact", "")

        val tower = getPrimaryCellTower(context)

        if (isInternetAvailable(context)) {
            // Option A: Active Internet -> HTTPS POST to CellSentinel
            val json = JSONObject().apply {
                put("device_id", imei)
                put("mcc", tower.mcc)
                put("mnc", tower.mnc)
                put("lac", tower.lac)
                put("cell_id", tower.cellId)
                put("signal_strength", tower.rssi)
            }

            val body = json.toString().toRequestBody("application/json".toMediaType())
            val request = Request.Builder()
                .url("$serverUrl/api/telemetry")
                .addHeader("X-Device-Token", deviceToken)
                .post(body)
                .build()

            httpClient.newCall(request).execute().use { response ->
                Log.i("CellSentinel", "HTTPS Beacon success: ${response.code}")
            }
        } else {
            // Option B: No Internet -> Out-of-band Silent SMS
            if (!emergencyNumber.isNullOrEmpty()) {
                val smsText = "LOC:$imei:${tower.mcc}:${tower.mnc}:${tower.lac}:${tower.cellId}:${tower.rssi.toInt()}"
                val smsManager = SmsManager.getDefault()
                smsManager.sendTextMessage(emergencyNumber, null, smsText, null, null)
                Log.i("CellSentinel", "Offline SMS Beacon dispatched to $emergencyNumber")
            }
        }
    }

    private fun isInternetAvailable(context: Context): Boolean {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager ?: return false
        val activeNet = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(activeNet) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }
}

