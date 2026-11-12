package org.cellsentinel.client

import android.Manifest
import android.app.Activity
import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.telephony.TelephonyManager
import android.widget.Button
import android.widget.EditText
import android.widget.Toast

class MainActivity : Activity() {

    private fun ensureSentinelPermissions() {
        val required = arrayOf(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION,
            Manifest.permission.READ_PHONE_STATE,
            Manifest.permission.SEND_SMS
        )
        val missing = required.filter {
            checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) {
            requestPermissions(missing.toTypedArray(), 1001)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ensureSentinelPermissions()

        // Simple programmatically-styled setup screen
        val layout = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            setPadding(50, 50, 50, 50)
        }

        val title = android.widget.TextView(this).apply {
            text = "🛡️ CellSentinel Client Sentinel"
            textSize = 20f
            setTypeface(null, android.graphics.Typeface.BOLD)
            setPadding(0, 0, 0, 30)
        }
        layout.addView(title)

        val editServer = EditText(this).apply {
            hint = "CellSentinel Server URL (e.g. https://air-bot-ndb9.onrender.com)"
            setText("https://air-bot-ndb9.onrender.com")
        }
        layout.addView(editServer)

        val editToken = EditText(this).apply {
            hint = "Device API Token"
        }
        layout.addView(editToken)

        val editImei = EditText(this).apply {
            hint = "Device IMEI (e.g. 358941098765432)"
            setText("358941098765432")
        }
        layout.addView(editImei)

        val editEmergency = EditText(this).apply {
            hint = "Emergency Phone Number (e.g. +919876543210)"
        }
        layout.addView(editEmergency)

        val btnSave = Button(this).apply {
            text = "Activate Sentinel Protection"
            setOnClickListener {
                val prefs = getSharedPreferences("sentinel_vault", Context.MODE_PRIVATE)
                val tm = getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager

                prefs.edit()
                    .putString("server_url", editServer.text.toString().trim())
                    .putString("device_token", editToken.text.toString().trim())
                    .putString("imei_number", editImei.text.toString().trim())
                    .putString("emergency_contact", editEmergency.text.toString().trim())
                    .putString("registered_operator", tm.simOperatorName)
                    .apply()

                Toast.makeText(this@MainActivity, "Sentinel Protection Activated! Firing initial beacon...", Toast.LENGTH_LONG).show()
                TelemetryWorker.enqueueImmediateBeacon(this@MainActivity)
            }
        }
        layout.addView(btnSave)

        val btnAdmin = Button(this).apply {
            text = "Lock Against Uninstall (Device Admin)"
            setOnClickListener {
                val comp = ComponentName(this@MainActivity, DeviceAdminLockReceiver::class.java)
                val intent = Intent(DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN).apply {
                    putExtra(DevicePolicyManager.EXTRA_DEVICE_ADMIN, comp)
                    putExtra(DevicePolicyManager.EXTRA_ADD_EXPLANATION, "Required to prevent thieves from uninstalling CellSentinel.")
                }
                startActivity(intent)
            }
        }
        layout.addView(btnAdmin)

        setContentView(layout)
    }
}

