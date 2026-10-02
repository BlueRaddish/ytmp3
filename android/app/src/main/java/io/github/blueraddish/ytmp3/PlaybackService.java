package io.github.blueraddish.ytmp3;

import android.app.PendingIntent;
import android.content.Intent;
import android.os.SystemClock;

import androidx.annotation.Nullable;
import androidx.media3.common.AudioAttributes;
import androidx.media3.common.C;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.Player;
import androidx.media3.common.util.StuckPlayerException;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.session.MediaSession;
import androidx.media3.session.MediaSessionService;

public final class PlaybackService extends MediaSessionService {
    private MediaSession session;
    private long lastStallRetryAt;

    @Override public void onCreate() {
        super.onCreate();
        ExoPlayer player = new ExoPlayer.Builder(this)
            .setAudioAttributes(AudioAttributes.DEFAULT, true)
            .setHandleAudioBecomingNoisy(true)
            // Avoid matching the same position on repeated 10-second tracks.
            // Other durations can still align; use loop-aware detection if they do.
            .setStuckPlayingDetectionTimeoutMs(7_333)
            .setWakeMode(C.WAKE_MODE_LOCAL)
            .build();
        player.addListener(new Player.Listener() {
            @Override public void onPlayerError(PlaybackException error) {
                android.util.Log.e("ytmp3-playback", "Playback failed", error);
                if (error.errorCode != PlaybackException.ERROR_CODE_TIMEOUT ||
                    !(error.getCause() instanceof StuckPlayerException)) return;
                long now = SystemClock.elapsedRealtime();
                // One retry per minute avoids a retry loop if the media or decoder stays broken.
                if (lastStallRetryAt != 0 && now - lastStallRetryAt < 60_000) return;
                lastStallRetryAt = now;
                android.util.Log.w("ytmp3-playback", "Retrying stalled playback");
                player.prepare();
                player.play();
            }
        });
        Intent openApp = new Intent(this, MainActivity.class)
            .setAction(Intent.ACTION_MAIN)
            .addCategory(Intent.CATEGORY_LAUNCHER)
            .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent sessionActivity = PendingIntent.getActivity(this, 0, openApp,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        session = new MediaSession.Builder(this, player)
            .setSessionActivity(sessionActivity)
            .build();
    }

    @Nullable @Override public MediaSession onGetSession(MediaSession.ControllerInfo controllerInfo) {
        return session;
    }

    @Override public void onDestroy() {
        if (session != null) {
            session.getPlayer().release();
            session.release();
            session = null;
        }
        super.onDestroy();
    }
}
