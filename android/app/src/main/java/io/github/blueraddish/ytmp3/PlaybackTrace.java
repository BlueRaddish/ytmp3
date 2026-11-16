package io.github.blueraddish.ytmp3;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.SystemClock;
import android.util.Log;

import androidx.media3.common.Player;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/** Bounded, on-device history of playback changes; no titles, URLs or periodic polling. */
final class PlaybackTrace {
    private static final int LIMIT = 64;
    private final SharedPreferences preferences;
    private final long session = System.currentTimeMillis();
    private JSONArray events;

    PlaybackTrace(Context context) {
        preferences = context.getSharedPreferences("playback-trace", Context.MODE_PRIVATE);
        try { events = new JSONArray(preferences.getString("events", "[]")); }
        catch (JSONException | ClassCastException error) { events = new JSONArray(); }
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
                .put("index", player.getCurrentMediaItemIndex())
                .put("count", player.getMediaItemCount());
            if (player.getPlayerError() != null)
                entry.put("error", player.getPlayerError().getErrorCodeName());
            JSONArray recent = new JSONArray();
            for (int i = Math.max(0, events.length() - LIMIT + 1); i < events.length(); i++)
                recent.put(events.get(i));
            recent.put(entry);
            events = recent;
            preferences.edit().putString("events", events.toString()).apply();
            Log.i("ytmp3-playback", entry.toString());
        } catch (JSONException error) {
            Log.w("ytmp3-playback", "Could not record playback change", error);
        }
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
