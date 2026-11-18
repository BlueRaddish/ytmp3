package io.github.blueraddish.ytmp3;

import android.content.Context;
import android.content.SharedPreferences;
import android.app.ActivityManager;
import android.app.ApplicationExitInfo;
import android.media.AudioDeviceInfo;
import android.media.AudioManager;
import android.os.BatteryManager;
import android.os.Build;
import android.os.PowerManager;
import android.os.SystemClock;
import android.util.Log;

import androidx.media3.common.Player;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

/** Saves interruptions separately from the rolling history, so continuing playback keeps the evidence. */
final class PlaybackTrace {
    private static final int LIMIT = 64;
    private final SharedPreferences preferences;
    private final Context context;
    private final long session = System.currentTimeMillis();
    private JSONArray events;
    private JSONObject incident;
    private String incidentId;
    private long incidentAt;
    private static PlaybackReportStore reports;

    PlaybackTrace(Context context) {
        this.context = context.getApplicationContext();
        preferences = context.getSharedPreferences("playback-trace", Context.MODE_PRIVATE);
        try {
            String saved = preferences.getString("events", "[]");
            events = new JSONArray(saved == null ? "[]" : saved);
        }
        catch (JSONException | ClassCastException error) { events = new JSONArray(); }
    }

    private static synchronized PlaybackReportStore store(Context context) {
        if (reports == null) reports = new PlaybackReportStore(new File(context.getFilesDir(), "playback-reports"));
        return reports;
    }

    void begin(Player player) {
        JSONObject previous = events.optJSONObject(events.length() - 1);
        if (previous != null && previous.optBoolean("playWhenReady")
                && !"service_destroyed".equals(previous.optString("event"))) {
            try {
                pin("previous_session_interrupted", previous);
                incident.put("processExits", processExits(context));
                store(context).save(incidentId, incident.toString());
            } catch (Exception error) { Log.w("ytmp3-playback", "Could not save previous session", error); }
        }
        record("service_created", player, "");
    }

    void record(String event, Player player, String detail) {
        try {
            JSONObject entry = new JSONObject()
                .put("time", System.currentTimeMillis())
                .put("elapsed", SystemClock.elapsedRealtime())
                .put("session", session)
                .put("event", event)
                .put("detail", detail)
                .put("state", player.getPlaybackState())
                .put("playWhenReady", player.getPlayWhenReady())
                .put("suppression", player.getPlaybackSuppressionReason())
                .put("position", player.getCurrentPosition())
                .put("bufferedPosition", player.getBufferedPosition())
                .put("duration", player.getDuration())
                .put("speed", player.getPlaybackParameters().speed)
                .put("repeat", player.getRepeatMode())
                .put("index", player.getCurrentMediaItemIndex())
                .put("count", player.getMediaItemCount())
                .put("device", deviceState(context));
            if (player.getPlayerError() != null)
                entry.put("error", player.getPlayerError().getErrorCodeName());
            JSONArray recent = new JSONArray();
            for (int i = Math.max(0, events.length() - LIMIT + 1); i < events.length(); i++)
                recent.put(events.get(i));
            recent.put(entry);
            events = recent;
            preferences.edit().putString("events", events.toString()).apply();
            // Keep the controller request and subsequent resume in the same saved report.
            if (incident != null && SystemClock.elapsedRealtime() - incidentAt <= 120_000
                    && incident.getJSONArray("after").length() < 16) {
                incident.getJSONArray("after").put(entry);
                store(context).save(incidentId, incident.toString());
            }
            if ("error".equals(event)
                    || ("play_when_ready".equals(event) && !player.getPlayWhenReady())
                    || ("suppression".equals(event) && player.getPlaybackSuppressionReason() != 0))
                pin(event.equals("play_when_ready") ? detail : event, entry);
            Log.i("ytmp3-playback", entry.toString());
        } catch (Exception error) {
            Log.w("ytmp3-playback", "Could not record playback change", error);
        }
    }

    private void pin(String reason, JSONObject trigger) throws JSONException {
        JSONArray before = new JSONArray();
        for (int i = Math.max(0, events.length() - 16); i < events.length(); i++) before.put(events.get(i));
        incidentId = System.currentTimeMillis() + "-" + UUID.randomUUID();
        incidentAt = SystemClock.elapsedRealtime();
        incident = new JSONObject().put("schema", 1).put("savedAt", System.currentTimeMillis())
            .put("reason", reason).put("trigger", trigger).put("before", before).put("after", new JSONArray());
        store(context).save(incidentId, incident.toString());
    }

    private static JSONObject deviceState(Context context) throws JSONException {
        JSONObject state = new JSONObject();
        PowerManager power = context.getSystemService(PowerManager.class);
        BatteryManager battery = context.getSystemService(BatteryManager.class);
        AudioManager audio = context.getSystemService(AudioManager.class);
        if (power != null) state.put("interactive", power.isInteractive()).put("powerSave", power.isPowerSaveMode());
        if (battery != null) state.put("charging", battery.isCharging())
            .put("batteryPercent", battery.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY));
        JSONArray outputs = new JSONArray();
        try {
            if (audio != null) for (AudioDeviceInfo device : audio.getDevices(AudioManager.GET_DEVICES_OUTPUTS))
                outputs.put(device.getType());
        } catch (SecurityException unavailable) { state.put("audioOutputsUnavailable", true); }
        return state.put("connectedOutputTypes", outputs);
    }

    static JSONArray processExits(Context context) throws JSONException {
        JSONArray exits = new JSONArray();
        if (Build.VERSION.SDK_INT >= 30) {
            ActivityManager manager = context.getSystemService(ActivityManager.class);
            if (manager != null) for (ApplicationExitInfo exit : manager.getHistoricalProcessExitReasons(null, 0, 5))
                exits.put(new JSONObject().put("time", exit.getTimestamp()).put("reason", exit.getReason())
                    .put("status", exit.getStatus()).put("importance", exit.getImportance())
                    .put("pid", exit.getPid()));
        }
        return exits;
    }

    /** Called on the existing library worker, never on the UI/player thread. */
    static String export(Context context) throws Exception {
        JSONArray saved = new JSONArray();
        for (String json : store(context).read().get(10, TimeUnit.SECONDS)) saved.put(new JSONObject(json));
        JSONArray history = new JSONArray(context.getSharedPreferences("playback-trace", Context.MODE_PRIVATE)
            .getString("events", "[]"));
        JSONObject report = new JSONObject().put("schema", 2).put("exportedAt", System.currentTimeMillis())
            .put("appVersion", context.getPackageManager().getPackageInfo(context.getPackageName(), 0).versionName)
            .put("androidSdk", Build.VERSION.SDK_INT).put("deviceModel", Build.MODEL)
            .put("savedReports", saved).put("recentEvents", history).put("processExits", processExits(context));
        String warning = store(context).lastError();
        if (warning != null) report.put("storageWarning", warning);
        return report.toString(2);
    }

    static String playWhenReadyReason(int reason) {
        switch (reason) {
            case Player.PLAY_WHEN_READY_CHANGE_REASON_USER_REQUEST: return "user_request";
            case Player.PLAY_WHEN_READY_CHANGE_REASON_AUDIO_FOCUS_LOSS: return "audio_focus_loss";
            case Player.PLAY_WHEN_READY_CHANGE_REASON_AUDIO_BECOMING_NOISY: return "audio_output_disconnected";
            case Player.PLAY_WHEN_READY_CHANGE_REASON_REMOTE: return "remote";
            case Player.PLAY_WHEN_READY_CHANGE_REASON_END_OF_MEDIA_ITEM: return "end_of_media_item";
            case Player.PLAY_WHEN_READY_CHANGE_REASON_SUPPRESSED_TOO_LONG: return "suppressed_too_long";
            default: return "unknown_" + reason;
        }
    }
}
