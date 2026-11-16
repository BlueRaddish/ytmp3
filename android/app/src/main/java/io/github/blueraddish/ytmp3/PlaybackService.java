package io.github.blueraddish.ytmp3;

import android.app.PendingIntent;
import android.content.Intent;
import android.os.SystemClock;

import androidx.annotation.Nullable;
import androidx.media3.common.AudioAttributes;
import androidx.media3.common.C;
import androidx.media3.common.MediaItem;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.Player;
import androidx.media3.common.util.StuckPlayerException;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.session.MediaSession;
import androidx.media3.session.MediaSessionService;

public final class PlaybackService extends MediaSessionService {
    private MediaSession session;
    private PlaybackTrace trace;
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
        trace = new PlaybackTrace(this);
        trace.record("service_created", player, "");
        player.addListener(new Player.Listener() {
            @Override public void onPlayWhenReadyChanged(boolean playWhenReady, int reason) {
                trace.record("play_when_ready", player, PlaybackTrace.playWhenReadyReason(reason));
            }
            @Override public void onPlaybackSuppressionReasonChanged(int reason) {
                trace.record("suppression", player, Integer.toString(reason));
            }
            @Override public void onPlaybackStateChanged(int state) {
                trace.record("state", player, Integer.toString(state));
            }
            @Override public void onMediaItemTransition(@Nullable MediaItem item, int reason) {
                trace.record("media_transition", player, Integer.toString(reason));
            }
            @Override public void onPlayerError(PlaybackException error) {
                trace.record("error", player, error.getErrorCodeName());
                android.util.Log.e("ytmp3-playback", "Playback failed", error);
                if (error.errorCode != PlaybackException.ERROR_CODE_TIMEOUT ||
                    !(error.getCause() instanceof StuckPlayerException)) return;
                long now = SystemClock.elapsedRealtime();
                // One retry per minute avoids a retry loop if the media or decoder stays broken.
                if (lastStallRetryAt != 0 && now - lastStallRetryAt < 60_000) {
                    trace.record("retry_skipped", player, "rate_limit");
                    return;
                }
                lastStallRetryAt = now;
                android.util.Log.w("ytmp3-playback", "Retrying stalled playback");
                trace.record("retry", player, "stalled_playback");
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
            .setCallback(new MediaSession.Callback() {
                @Override public void onPlayerInteractionFinished(MediaSession mediaSession,
                        MediaSession.ControllerInfo controller, Player.Commands commands) {
                    if (commands.contains(Player.COMMAND_PLAY_PAUSE) || commands.contains(Player.COMMAND_STOP)
                            || commands.contains(Player.COMMAND_CHANGE_MEDIA_ITEMS))
                        trace.record("controller", player, controller.getPackageName());
                }
            })
            .build();
    }

    @Nullable @Override public MediaSession onGetSession(MediaSession.ControllerInfo controllerInfo) {
        return session;
    }

    @Override public void onTaskRemoved(@Nullable Intent rootIntent) {
        if (session != null) trace.record("task_removed", session.getPlayer(), "");
        super.onTaskRemoved(rootIntent);
    }

    @Override public void onDestroy() {
        if (session != null) {
            trace.record("service_destroyed", session.getPlayer(), "");
            session.getPlayer().release();
            session.release();
            session = null;
        }
        super.onDestroy();
    }
}
