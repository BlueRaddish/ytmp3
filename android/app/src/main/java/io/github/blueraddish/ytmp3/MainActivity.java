package io.github.blueraddish.ytmp3;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ComponentName;
import android.content.ClipData;
import android.content.Intent;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.Insets;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.OpenableColumns;
import android.provider.Settings;
import android.view.WindowInsets;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

import org.json.JSONObject;
import org.json.JSONArray;

import androidx.media3.common.MediaItem;
import androidx.media3.common.MediaMetadata;
import androidx.media3.common.PlaybackParameters;
import androidx.media3.session.MediaController;
import androidx.media3.session.SessionToken;
import com.google.common.util.concurrent.ListenableFuture;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FilterInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class MainActivity extends Activity {
    private static final String ORIGIN = "https://appassets.androidplatform.net";
    private static final Pattern SHARED_URL = Pattern.compile("https?://\\S+", Pattern.CASE_INSENSITIVE);
    private static final Pattern RANGE = Pattern.compile("bytes=(\\d*)-(\\d*)");
    private static final String UPDATE_FEED = "https://raw.githubusercontent.com/BlueRaddish/ytmp3/main/updates.json";
    private static final int PICK_FOLDER = 19;
    private static final int PICK_PLAYLIST = 20;
    private static final int PICK_COVER = 21;
    private static final int PICK_RINGTONE_PERMISSION = 22;
    private AndroidLibrary library;
    private WebView web;
    private MediaController controller;
    private ListenableFuture<MediaController> controllerFuture;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private volatile String playbackSnapshot = "{}";
    private final List<Runnable> pendingPlayback = new ArrayList<>();
    private String pendingCoverId;
    private String pendingRingtoneId;
    private volatile String latestApkUrl;

    @SuppressLint("SetJavaScriptEnabled")
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.rgb(16, 27, 28));
        getWindow().setNavigationBarColor(Color.rgb(16, 27, 28));
        library = new AndroidLibrary(this);
        web = new WebView(this);
        web.setBackgroundColor(Color.rgb(16, 27, 28));
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMediaPlaybackRequiresUserGesture(true);
        web.addJavascriptInterface(new Bridge(), "Ytmp3Android");
        web.setWebChromeClient(new WebChromeClient());
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (ORIGIN.equals(uri.getScheme() + "://" + uri.getHost())) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); }
                catch (Exception ignored) { }
                return true;
            }

            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (!ORIGIN.equals(uri.getScheme() + "://" + uri.getHost())) return response(403, "text/plain", "Blocked");
                String path = uri.getPath();
                if (path == null) return response(404, "text/plain", "Not found");
                if (path.startsWith("/media/")) {
                    String range = null;
                    for (Map.Entry<String, String> header : request.getRequestHeaders().entrySet()) {
                        if (header.getKey().equalsIgnoreCase("range")) range = header.getValue();
                    }
                    return media(uri.getLastPathSegment(), range);
                }
                if (path.startsWith("/cover/")) {
                    byte[] image = library.cover(uri.getLastPathSegment());
                    String type = image == null ? null : AndroidLibrary.coverType(image);
                    if (type == null) return response(404, "text/plain", "Not found");
                    return new WebResourceResponse(type, null, new ByteArrayInputStream(image));
                }
                String asset;
                String type;
                switch (path) {
                    case "/": asset = "index.html"; type = "text/html"; break;
                    case "/app.css": asset = "app.css"; type = "text/css"; break;
                    case "/app.js": asset = "app.js"; type = "text/javascript"; break;
                    case "/playlist-store.js": asset = "playlist-store.js"; type = "text/javascript"; break;
                    case "/manifest.webmanifest": asset = "manifest.webmanifest"; type = "application/manifest+json"; break;
                    case "/icon-192.png": asset = "icon-192.png"; type = "image/png"; break;
                    case "/icon-512.png": asset = "icon-512.png"; type = "image/png"; break;
                    case "/licenses/youtubedl-android-GPL-3.0.txt":
                        asset = "licenses/youtubedl-android-GPL-3.0.txt"; type = "text/plain"; break;
                    default: return response(404, "text/plain", "Not found");
                }
                try { return new WebResourceResponse(type, type.startsWith("image/") ? null : "UTF-8", getAssets().open(asset)); }
                catch (IOException error) { return response(500, "text/plain", "Could not load app asset"); }
            }
        });
        FrameLayout root = new FrameLayout(this);
        root.addView(web, new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        if (Build.VERSION.SDK_INT >= 30) root.setOnApplyWindowInsetsListener((view, insets) -> {
            int types = WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout();
            Insets bars = insets.getInsets(types);
            root.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return new WindowInsets.Builder(insets).setInsets(types, Insets.NONE).build();
        });
        setContentView(root);
        String shared = sharedUrl(getIntent());
        web.loadUrl(ORIGIN + "/" + (shared == null ? "" : "?url=" + Uri.encode(shared)));
    }

    @Override protected void onStart() {
        super.onStart();
        controllerFuture = new MediaController.Builder(this,
            new SessionToken(this, new ComponentName(this, PlaybackService.class))).buildAsync();
        controllerFuture.addListener(() -> {
            try {
                controller = controllerFuture.get();
                for (Runnable action : pendingPlayback) action.run();
                pendingPlayback.clear();
                updatePlayback();
            } catch (Exception ignored) { playbackSnapshot = "{}"; }
        }, getMainExecutor());
    }

    @Override protected void onStop() {
        handler.removeCallbacksAndMessages(null);
        controller = null;
        if (controllerFuture != null) MediaController.releaseFuture(controllerFuture);
        controllerFuture = null;
        super.onStop();
    }

    private void updatePlayback() {
        MediaController player = controller;
        if (player == null) return;
        try {
            MediaItem item = player.getCurrentMediaItem();
            playbackSnapshot = new JSONObject()
                .put("id", item == null ? JSONObject.NULL : item.mediaId)
                .put("playing", player.isPlaying())
                .put("position", Math.max(0, player.getCurrentPosition()))
                .put("duration", Math.max(0, player.getDuration()))
                .put("speed", player.getPlaybackParameters().speed)
                .put("shuffle", player.getShuffleModeEnabled())
                .put("repeat", player.getRepeatMode())
                .put("index", player.getCurrentMediaItemIndex()).toString();
        } catch (Exception ignored) { playbackSnapshot = "{}"; }
        handler.postDelayed(this::updatePlayback, 500);
    }

    private void withPlayer(Runnable action) {
        handler.post(() -> {
            if (controller != null) action.run();
            else pendingPlayback.add(action);
        });
    }

    private List<MediaItem> mediaItems(String json) throws Exception {
        JSONArray entries = new JSONArray(json);
        List<MediaItem> items = new ArrayList<>();
        for (int i = 0; i < entries.length(); i++) {
            JSONObject entry = entries.getJSONObject(i);
            String id = entry.getString("id");
            Uri uri = library.mediaUri(id);
            if (uri != null) {
                MediaMetadata.Builder metadata = new MediaMetadata.Builder().setTitle(entry.getString("title"))
                    .setArtist(entry.optString("artist")).setAlbumTitle(entry.optString("album"));
                if (entry.optBoolean("artwork")) metadata.setArtworkUri(
                    Uri.parse("content://io.github.blueraddish.ytmp3.files/covers/" + Uri.encode(id)));
                items.add(new MediaItem.Builder().setMediaId(id).setUri(uri)
                    .setMediaMetadata(metadata.build()).build());
            }
        }
        return items;
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        String shared = sharedUrl(intent);
        if (shared != null) web.evaluateJavascript("window.ytmp3Receive(" + JSONObject.quote(shared) + ")", null);
    }

    private static String sharedUrl(Intent intent) {
        if (intent == null || !Intent.ACTION_SEND.equals(intent.getAction())) return null;
        String text = intent.getStringExtra(Intent.EXTRA_TEXT);
        if (text == null) return null;
        Matcher match = SHARED_URL.matcher(text);
        return match.find() ? match.group() : null;
    }

    private final class Bridge {
        @JavascriptInterface public String tracks() { return library.tracks(); }
        @JavascriptInterface public String submit(String url) { return library.submit(url); }
        @JavascriptInterface public String job(String id) { return library.job(id); }
        @JavascriptInterface public String exportTrack(String id) { return library.exportTrack(id); }
        @JavascriptInterface public String folders() { return library.folders(); }
        @JavascriptInterface public String editTrack(String id, String title, String artist, String album) {
            return library.editTrack(id, title, artist, album);
        }
        @JavascriptInterface public String removeCover(String id) { return library.removeCover(id); }
        @JavascriptInterface public void checkAppUpdate() {
            new Thread(MainActivity.this::checkAppUpdate, "ytmp3-update-check").start();
        }
        @JavascriptInterface public void openAppUpdate() {
            handler.post(() -> {
                String url = latestApkUrl;
                if (url == null) return;
                try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); }
                catch (Exception error) {
                    android.widget.Toast.makeText(MainActivity.this, "Could not open the APK link.",
                        android.widget.Toast.LENGTH_LONG).show();
                }
            });
        }
        @JavascriptInterface public void shareTrack(String id) {
            shareTracks(new JSONArray().put(id).toString());
        }
        @JavascriptInterface public void shareTracks(String json) {
            handler.post(() -> {
                try {
                    JSONArray ids = new JSONArray(json);
                    if (ids.length() < 1 || ids.length() > 100) return;
                    ArrayList<Uri> uris = new ArrayList<>();
                    for (int i = 0; i < ids.length(); i++) {
                        String id = ids.getString(i);
                        Uri uri = library.mediaUri(id);
                        if (uri == null) continue;
                        uris.add("file".equals(uri.getScheme())
                            ? Uri.parse("content://io.github.blueraddish.ytmp3.files/shares/" + Uri.encode(id)) : uri);
                    }
                    if (uris.isEmpty()) return;
                    Intent share = new Intent(uris.size() == 1 ? Intent.ACTION_SEND : Intent.ACTION_SEND_MULTIPLE);
                    share.setType("audio/mpeg");
                    if (uris.size() == 1) share.putExtra(Intent.EXTRA_STREAM, uris.get(0));
                    else share.putParcelableArrayListExtra(Intent.EXTRA_STREAM, uris);
                    ClipData clip = ClipData.newRawUri("MP3", uris.get(0));
                    for (int i = 1; i < uris.size(); i++) clip.addItem(new ClipData.Item(uris.get(i)));
                    share.setClipData(clip);
                    share.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    startActivity(Intent.createChooser(share, "Share audio"));
                } catch (Exception error) {
                    android.widget.Toast.makeText(MainActivity.this, "Could not share those tracks.",
                        android.widget.Toast.LENGTH_LONG).show();
                }
            });
        }
        @JavascriptInterface public void setRingtone(String id) {
            handler.post(() -> {
                if (library.mediaUri(id) == null) return;
                if (Settings.System.canWrite(MainActivity.this)) startRingtone(id);
                else {
                    pendingRingtoneId = id;
                    startActivityForResult(new Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS,
                        Uri.parse("package:" + getPackageName())), PICK_RINGTONE_PERMISSION);
                }
            });
        }
        @JavascriptInterface public void pickCover(String id) {
            handler.post(() -> {
                if (library.mediaUri(id) == null) return;
                pendingCoverId = id;
                startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT)
                    .addCategory(Intent.CATEGORY_OPENABLE).setType("image/*")
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION), PICK_COVER);
            });
        }
        @JavascriptInterface public String removeFolder(String uri) { return library.removeFolder(uri); }
        @JavascriptInterface public void pickFolder() {
            handler.post(() -> startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION), PICK_FOLDER));
        }
        @JavascriptInterface public void pickPlaylist() {
            handler.post(() -> startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT)
                .addCategory(Intent.CATEGORY_OPENABLE).setType("*/*")
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION), PICK_PLAYLIST));
        }
        @JavascriptInterface public String playback() { return playbackSnapshot; }
        @JavascriptInterface public void playQueue(String json, int index) {
            withPlayer(() -> {
                try {
                    List<MediaItem> items = mediaItems(json);
                    if (items.isEmpty()) return;
                    controller.setMediaItems(items, Math.min(index, items.size() - 1), 0);
                    controller.prepare();
                    controller.play();
                } catch (Exception ignored) { }
            });
        }
        @JavascriptInterface public void replaceQueue(String json, int index) {
            withPlayer(() -> {
                try {
                    List<MediaItem> items = mediaItems(json);
                    if (items.isEmpty()) { controller.clearMediaItems(); return; }
                    MediaItem current = controller.getCurrentMediaItem();
                    String currentId = current == null ? null : current.mediaId;
                    int selected = Math.min(index, items.size() - 1);
                    if (currentId != null) {
                        for (int i = 0; i < items.size(); i++) {
                            if (items.get(i).mediaId.equals(currentId)) { selected = i; break; }
                        }
                    }
                    long position = Math.max(0, controller.getCurrentPosition());
                    boolean playing = controller.isPlaying();
                    controller.setMediaItems(items, selected, position);
                    controller.prepare();
                    if (playing) controller.play();
                } catch (Exception ignored) { }
            });
        }
        @JavascriptInterface public void command(String name, double value) {
            withPlayer(() -> {
                switch (name) {
                    case "play": controller.play(); break;
                    case "pause": controller.pause(); break;
                    case "next": controller.seekToNextMediaItem(); break;
                    case "previous":
                        if (controller.getCurrentPosition() > 3000) controller.seekTo(0);
                        else controller.seekToPreviousMediaItem();
                        break;
                    case "seek": controller.seekTo(Math.max(0, (long) value)); break;
                    case "speed": controller.setPlaybackParameters(new PlaybackParameters((float) value)); break;
                    case "volume": controller.setVolume((float) value); break;
                    case "shuffle": controller.setShuffleModeEnabled(value != 0); break;
                    case "repeat": controller.setRepeatMode((int) value); break;
                    case "stop": controller.stop(); break;
                }
            });
        }
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == PICK_PLAYLIST) {
            if (result == RESULT_OK && data != null && data.getData() != null) readPlaylist(data.getData());
            return;
        }
        if (request == PICK_COVER) {
            String id = pendingCoverId;
            pendingCoverId = null;
            if (id != null && result == RESULT_OK && data != null && data.getData() != null) {
                String resultJson = library.saveCover(id, data.getData());
                web.evaluateJavascript("window.ytmp3CoverChanged(" + resultJson + ")", null);
            }
            return;
        }
        if (request == PICK_RINGTONE_PERMISSION) {
            String id = pendingRingtoneId;
            pendingRingtoneId = null;
            if (id != null && Settings.System.canWrite(this)) startRingtone(id);
            else web.evaluateJavascript("window.ytmp3RingtoneResult({\"error\":\"Ringtone permission was not granted.\"})", null);
            return;
        }
        if (request != PICK_FOLDER || result != RESULT_OK || data == null || data.getData() == null) return;
        Uri uri = data.getData();
        try {
            getContentResolver().takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
            library.addFolder(uri);
            web.evaluateJavascript("window.ytmp3FoldersChanged()", null);
        } catch (SecurityException ignored) { }
    }

    private void startRingtone(String id) {
        new Thread(() -> {
            String result = library.setRingtone(id);
            handler.post(() -> web.evaluateJavascript("window.ytmp3RingtoneResult(" + result + ")", null));
        }, "ytmp3-ringtone").start();
    }

    private static boolean newerVersion(String candidate, String current) {
        if (!candidate.matches("\\d+\\.\\d+\\.\\d+") || !current.matches("\\d+\\.\\d+\\.\\d+"))
            throw new IllegalArgumentException("Invalid app version.");
        String[] left = candidate.split("\\.");
        String[] right = current.split("\\.");
        for (int i = 0; i < 3; i++) {
            int difference = Integer.compare(Integer.parseInt(left[i]), Integer.parseInt(right[i]));
            if (difference != 0) return difference > 0;
        }
        return false;
    }

    private void checkAppUpdate() {
        JSONObject result;
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) new URL(UPDATE_FEED).openConnection();
            connection.setConnectTimeout(5000);
            connection.setReadTimeout(5000);
            connection.setRequestProperty("User-Agent", "ytmp3-update-check");
            if (connection.getResponseCode() != 200) throw new IOException("Update feed unavailable.");
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            try (InputStream input = connection.getInputStream()) {
                byte[] buffer = new byte[1024];
                int count;
                while ((count = input.read(buffer)) != -1) {
                    output.write(buffer, 0, count);
                    if (output.size() > 8192) throw new IOException("Update feed is too large.");
                }
            }
            JSONObject feed = new JSONObject(output.toString("UTF-8"));
            String version = feed.getString("version");
            String url = feed.getString("android_apk_url");
            Uri parsed = Uri.parse(url);
            if (!"https".equals(parsed.getScheme()) || !"drive.google.com".equals(parsed.getHost())
                    || parsed.getUserInfo() != null) throw new IOException("Invalid APK link.");
            String notes = feed.optString("notes", "");
            if (notes.length() > 400) throw new IOException("Invalid update notes.");
            String current = getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
            boolean available = newerVersion(version, current);
            latestApkUrl = available ? url : null;
            result = new JSONObject().put("current", current).put("version", version)
                .put("available", available).put("notes", notes);
        } catch (Exception error) {
            android.util.Log.w("ytmp3", "Could not check app update", error);
            result = new JSONObject();
            try { result.put("error", "Could not check for updates."); }
            catch (Exception ignored) { }
        } finally {
            if (connection != null) connection.disconnect();
        }
        String json = result.toString();
        handler.post(() -> web.evaluateJavascript("window.ytmp3UpdateResult(" + json + ")", null));
    }

    private void readPlaylist(Uri uri) {
        new Thread(() -> {
            try {
                String name = "playlist.m3u";
                try (Cursor cursor = getContentResolver().query(uri,
                        new String[] { OpenableColumns.DISPLAY_NAME }, null, null, null)) {
                    if (cursor != null && cursor.moveToFirst()) name = cursor.getString(0);
                }
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                try (InputStream input = getContentResolver().openInputStream(uri)) {
                    if (input == null) throw new IOException("Could not open playlist.");
                    byte[] buffer = new byte[8192];
                    int count;
                    while ((count = input.read(buffer)) != -1) {
                        out.write(buffer, 0, count);
                        if (out.size() > 1024 * 1024) throw new IOException("Playlist is too large.");
                    }
                }
                String script = "window.ytmp3PlaylistFile(" + JSONObject.quote(name) + ","
                    + JSONObject.quote(out.toString("UTF-8")) + ")";
                handler.post(() -> web.evaluateJavascript(script, null));
            } catch (Exception error) {
                android.util.Log.w("ytmp3", "Playlist import failed", error);
                handler.post(() -> android.widget.Toast.makeText(this,
                    "Could not read that playlist file.", android.widget.Toast.LENGTH_LONG).show());
            }
        }).start();
    }

    private static WebResourceResponse response(int status, String type, String message) {
        byte[] bytes = message.getBytes(StandardCharsets.UTF_8);
        WebResourceResponse result = new WebResourceResponse(type, "UTF-8", new ByteArrayInputStream(bytes));
        result.setStatusCodeAndReasonPhrase(status, status == 404 ? "Not Found" : "Error");
        Map<String, String> headers = new HashMap<>();
        headers.put("Content-Length", Integer.toString(bytes.length));
        result.setResponseHeaders(headers);
        return result;
    }

    private WebResourceResponse media(String name, String range) {
        File file = library.file(name);
        if (file == null) return response(404, "text/plain", "Not found");
        long size = file.length();
        long start = 0, end = size - 1;
        boolean partial = range != null;
        if (partial) {
            Matcher match = RANGE.matcher(range.trim());
            if (!match.matches() || (match.group(1).isEmpty() && match.group(2).isEmpty())) return response(416, "text/plain", "Invalid range");
            try {
                if (!match.group(1).isEmpty()) {
                    start = Long.parseLong(match.group(1));
                    if (!match.group(2).isEmpty()) end = Math.min(end, Long.parseLong(match.group(2)));
                } else {
                    long length = Long.parseLong(match.group(2));
                    start = Math.max(0, size - length);
                }
            } catch (NumberFormatException error) { return response(416, "text/plain", "Invalid range"); }
            if (start > end || start >= size) return response(416, "text/plain", "Invalid range");
        }
        try {
            FileInputStream input = new FileInputStream(file);
            input.getChannel().position(start);
            WebResourceResponse result = new WebResourceResponse("audio/mpeg", null, new LimitedInput(input, end - start + 1));
            result.setStatusCodeAndReasonPhrase(partial ? 206 : 200, partial ? "Partial Content" : "OK");
            Map<String, String> headers = new HashMap<>();
            headers.put("Accept-Ranges", "bytes");
            headers.put("Content-Length", Long.toString(end - start + 1));
            if (partial) headers.put("Content-Range", "bytes " + start + "-" + end + "/" + size);
            result.setResponseHeaders(headers);
            return result;
        } catch (IOException error) { return response(500, "text/plain", "Could not read file"); }
    }

    private static final class LimitedInput extends FilterInputStream {
        private long left;
        LimitedInput(InputStream input, long length) { super(input); left = length; }
        @Override public int read() throws IOException {
            if (left <= 0) return -1;
            int value = super.read();
            if (value != -1) left--;
            return value;
        }
        @Override public int read(byte[] buffer, int offset, int length) throws IOException {
            if (length == 0) return 0;
            if (left <= 0) return -1;
            int count = super.read(buffer, offset, (int) Math.min(length, left));
            if (count > 0) left -= count;
            return count;
        }
    }

    @Override @SuppressWarnings("deprecation") public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    @Override protected void onDestroy() {
        web.destroy();
        super.onDestroy();
    }
}
