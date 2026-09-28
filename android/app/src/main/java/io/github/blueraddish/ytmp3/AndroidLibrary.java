package io.github.blueraddish.ytmp3;

import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.media.MediaMetadataRetriever;
import android.media.RingtoneManager;
import android.os.Environment;
import android.provider.DocumentsContract;
import android.provider.MediaStore;
import android.provider.Settings;
import android.util.Log;
import android.widget.Toast;

import com.yausername.ffmpeg.FFmpeg;
import com.yausername.youtubedl_android.YoutubeDL;
import com.yausername.youtubedl_android.YoutubeDLRequest;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Comparator;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

final class AndroidLibrary {
    private final Context context;
    private final File directory;
    private final ExecutorService downloads = Executors.newSingleThreadExecutor();
    private final ExecutorService exports = Executors.newSingleThreadExecutor();
    private final Map<String, Job> jobs = new ConcurrentHashMap<>();
    private final Map<String, Uri> indexedFiles = new ConcurrentHashMap<>();
    private final Map<String, JSONObject> tagCache = new ConcurrentHashMap<>();
    private boolean ready;
    private static final String FOLDERS = "folders";

    private static final class Job {
        final String id;
        volatile String state = "queued";
        volatile String error;
        volatile String track;
        volatile int total;
        volatile int completed;
        volatile int saved;
        volatile int failed;
        volatile String playlist;
        final JSONArray tracks = new JSONArray();

        Job(String id) { this.id = id; }

        JSONObject json() throws JSONException {
            JSONObject out = new JSONObject().put("id", id).put("state", state);
            if (error != null) out.put("error", error);
            if (track != null) out.put("track", track);
            if (total > 0) out.put("total", total).put("completed", completed)
                .put("saved", saved).put("failed", failed);
            if (playlist != null) out.put("playlist", playlist);
            if (state.equals("done")) out.put("tracks", tracks);
            return out;
        }
    }

    AndroidLibrary(Context context) {
        this.context = context.getApplicationContext();
        File root = context.getExternalFilesDir(Environment.DIRECTORY_MUSIC);
        directory = new File(root == null ? context.getFilesDir() : root, "ytmp3");
        if (!directory.exists() && !directory.mkdirs()) {
            throw new IllegalStateException("Could not create the phone library.");
        }
    }

    String tracks() {
        JSONArray tracks = new JSONArray();
        indexedFiles.clear();
        File[] files = directory.listFiles(file -> file.isFile() && file.getName().toLowerCase().endsWith(".mp3"));
        if (files != null) {
            Arrays.sort(files, Comparator.comparingLong(File::lastModified).reversed());
            for (File file : files) {
                try {
                    tracks.put(track(file.getName(), file.getName(), Uri.fromFile(file),
                        file.length(), file.lastModified(), directory.getName(), "own", "own", false));
                } catch (JSONException ignored) { /* Values come from local filenames. */ }
            }
        }
        for (String raw : folderUris()) {
            try {
                Uri tree = Uri.parse(raw);
                String root = DocumentsContract.getTreeDocumentId(tree);
                String label = root;
                try (Cursor cursor = context.getContentResolver().query(
                        DocumentsContract.buildDocumentUriUsingTree(tree, root),
                        new String[] { DocumentsContract.Document.COLUMN_DISPLAY_NAME }, null, null, null)) {
                    if (cursor != null && cursor.moveToFirst()) label = cursor.getString(0);
                }
                scan(tree, root, tracks, 0, label, raw);
            }
            catch (Exception error) { Log.w("ytmp3", "Could not scan selected folder", error); }
        }
        try { return new JSONObject().put("tracks", tracks).toString(); }
        catch (JSONException ignored) { return "{\"tracks\":[]}"; }
    }

    // The 10,000-entry cap keeps a giant document-provider tree from blocking the WebView bridge.
    // A paged media index is the upgrade path for libraries beyond this size.
    private void scan(Uri tree, String parent, JSONArray tracks, int depth, String folder, String folderId) {
        if (depth > 32 || tracks.length() >= 10000) return;
        Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, parent);
        String[] columns = { DocumentsContract.Document.COLUMN_DOCUMENT_ID,
            DocumentsContract.Document.COLUMN_DISPLAY_NAME, DocumentsContract.Document.COLUMN_MIME_TYPE,
            DocumentsContract.Document.COLUMN_SIZE, DocumentsContract.Document.COLUMN_LAST_MODIFIED };
        try (Cursor cursor = context.getContentResolver().query(children, columns, null, null, null)) {
            if (cursor == null) return;
            while (cursor.moveToNext() && tracks.length() < 10000) {
                String id = cursor.getString(0);
                String name = cursor.getString(1);
                String type = cursor.getString(2);
                if (DocumentsContract.Document.MIME_TYPE_DIR.equals(type)) {
                    scan(tree, id, tracks, depth + 1, folder + "/" + name, tree + "/" + id);
                } else if (name != null && name.toLowerCase(java.util.Locale.ROOT).endsWith(".mp3")) {
                    Uri uri = DocumentsContract.buildDocumentUriUsingTree(tree, id);
                    String key = uri.toString();
                    indexedFiles.put(key, uri);
                    try { tracks.put(track(key, name, uri,
                        cursor.isNull(3) ? 0 : cursor.getLong(3),
                        cursor.isNull(4) ? 0 : cursor.getLong(4), folder, folderId, tree.toString(), true)); }
                    catch (JSONException ignored) { }
                }
            }
        }
    }

    private JSONObject track(String id, String name, Uri uri, long size, long modified,
            String folder, String folderId, String rootFolderId, boolean external) throws JSONException {
        String cacheKey = id + "|" + size + "|" + modified;
        JSONObject tags = tagCache.get(cacheKey);
        if (tags == null) {
            tags = new JSONObject();
            try (MediaMetadataRetriever reader = new MediaMetadataRetriever()) {
                setSource(reader, uri);
                tags.put("title", reader.extractMetadata(MediaMetadataRetriever.METADATA_KEY_TITLE));
                tags.put("artist", reader.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ARTIST));
                tags.put("album", reader.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ALBUM));
                String duration = reader.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION);
                tags.put("duration", duration == null ? 0 : Long.parseLong(duration) / 1000);
                byte[] art = reader.getEmbeddedPicture();
                tags.put("artwork", art != null && art.length <= 1024 * 1024 && imageType(art) != null);
            } catch (Exception error) { Log.w("ytmp3", "Could not read MP3 tags", error); }
            tagCache.put(cacheKey, tags);
        }
        JSONObject edit = edits(id);
        File cover = coverFile(id);
        return new JSONObject().put("id", id)
            .put("title", edit.has("title") && !edit.optString("title").isEmpty() ? edit.optString("title")
                : tags.optString("title", name.replaceFirst("(?i)\\.mp3$", "")))
            .put("artist", edit.has("artist") ? edit.optString("artist") : tags.optString("artist"))
            .put("album", edit.has("album") ? edit.optString("album") : tags.optString("album"))
            .put("duration", tags.optLong("duration"))
            .put("artwork", cover.isFile() || tags.optBoolean("artwork"))
            .put("folder", folder).put("folderId", folderId)
            .put("rootFolder", folder.split("/", 2)[0])
            .put("rootFolderId", rootFolderId)
            .put("size", size).put("modified", modified / 1000).put("external", external);
    }

    private JSONObject edits(String id) {
        try { return new JSONObject(context.getSharedPreferences("track_edits", 0).getString(id, "{}")); }
        catch (JSONException ignored) { return new JSONObject(); }
    }

    private void setSource(MediaMetadataRetriever reader, Uri uri) {
        if ("file".equals(uri.getScheme())) reader.setDataSource(uri.getPath());
        else reader.setDataSource(context, uri);
    }

    String editTrack(String id, String title, String artist, String album) {
        if (mediaUri(id) == null) return failure("Track not found.");
        if (title == null || artist == null || album == null
                || title.length() > 160 || artist.length() > 160 || album.length() > 160) {
            return failure("Track details are too long.");
        }
        try {
            JSONObject edit = new JSONObject().put("title", title.trim())
                .put("artist", artist.trim()).put("album", album.trim());
            return context.getSharedPreferences("track_edits", 0).edit()
                .putString(id, edit.toString()).commit() ? "{}" : failure("Could not save track details.");
        } catch (JSONException error) { return failure("Could not save track details."); }
    }

    private File coverFile(String id) {
        try {
            byte[] hash = MessageDigest.getInstance("SHA-256").digest(id.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            StringBuilder name = new StringBuilder();
            for (byte value : hash) name.append(String.format(java.util.Locale.ROOT, "%02x", value & 0xff));
            return new File(new File(context.getFilesDir(), "covers"), name.toString());
        } catch (Exception error) { throw new IllegalStateException(error); }
    }

    private static String imageType(byte[] data) {
        if (data.length >= 3 && (data[0] & 0xff) == 0xff && (data[1] & 0xff) == 0xd8 && (data[2] & 0xff) == 0xff)
            return "image/jpeg";
        if (data.length >= 8 && data[0] == (byte) 0x89 && data[1] == 'P' && data[2] == 'N' && data[3] == 'G')
            return "image/png";
        return null;
    }

    byte[] cover(String id) {
        Uri uri = mediaUri(id);
        if (uri == null) return null;
        try {
            File custom = coverFile(id);
            if (custom.isFile()) return Files.readAllBytes(custom.toPath());
            try (MediaMetadataRetriever reader = new MediaMetadataRetriever()) {
                setSource(reader, uri);
                byte[] data = reader.getEmbeddedPicture();
                return data != null && data.length <= 1024 * 1024 && imageType(data) != null ? data : null;
            }
        } catch (Exception error) { return null; }
    }

    static String coverType(byte[] data) { return imageType(data); }

    String saveCover(String id, Uri source) {
        if (mediaUri(id) == null) return failure("Track not found.");
        File target = coverFile(id);
        File temporary = null;
        try (InputStream input = context.getContentResolver().openInputStream(source)) {
            if (input == null) return failure("Could not open cover image.");
            if (!target.getParentFile().exists() && !target.getParentFile().mkdirs())
                return failure("Could not save cover image.");
            temporary = File.createTempFile("cover-", ".tmp", target.getParentFile());
            try (OutputStream output = Files.newOutputStream(temporary.toPath())) {
                byte[] buffer = new byte[8192];
                int count, total = 0;
                while ((count = input.read(buffer)) != -1) {
                    total += count;
                    if (total > 1024 * 1024) return failure("Cover must be under 1 MB.");
                    output.write(buffer, 0, count);
                }
            }
            if (imageType(Files.readAllBytes(temporary.toPath())) == null)
                return failure("Choose a JPEG or PNG cover.");
            if (!temporary.renameTo(target)) return failure("Could not save cover image.");
            return "{}";
        } catch (Exception error) { return failure("Could not save cover image."); }
        finally { if (temporary != null) temporary.delete(); }
    }

    String removeCover(String id) {
        if (mediaUri(id) == null) return failure("Track not found.");
        File cover = coverFile(id);
        return !cover.exists() || cover.delete() ? "{}" : failure("Could not remove cover image.");
    }

    String setRingtone(String id) {
        Uri source = mediaUri(id);
        if (source == null) return failure("Track not found.");
        if (!Settings.System.canWrite(context)) return failure("Allow ytmp3 to change system settings first.");
        Uri saved = null;
        try {
            ContentValues values = new ContentValues();
            values.put(MediaStore.Audio.Media.DISPLAY_NAME, "ytmp3-ringtone-" + System.currentTimeMillis() + ".mp3");
            values.put(MediaStore.Audio.Media.MIME_TYPE, "audio/mpeg");
            values.put(MediaStore.Audio.Media.RELATIVE_PATH, Environment.DIRECTORY_RINGTONES + "/ytmp3");
            values.put(MediaStore.Audio.Media.IS_RINGTONE, 1);
            values.put(MediaStore.Audio.Media.IS_PENDING, 1);
            // Each selection keeps one copy in Ringtones/ytmp3. Reusing old
            // copies requires tracking MediaStore ownership and is the upgrade path.
            saved = context.getContentResolver().insert(MediaStore.Audio.Media.EXTERNAL_CONTENT_URI, values);
            if (saved == null) throw new IOException("Could not create ringtone.");
            File own = file(id);
            try (InputStream input = own == null ? context.getContentResolver().openInputStream(source)
                    : Files.newInputStream(own.toPath());
                 OutputStream output = context.getContentResolver().openOutputStream(saved)) {
                if (input == null || output == null) throw new IOException("Could not copy ringtone.");
                byte[] buffer = new byte[8192];
                int count;
                while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
            }
            values.clear();
            values.put(MediaStore.Audio.Media.IS_PENDING, 0);
            context.getContentResolver().update(saved, values, null, null);
            RingtoneManager.setActualDefaultRingtoneUri(context, RingtoneManager.TYPE_RINGTONE, saved);
            return "{}";
        } catch (Exception error) {
            Log.w("ytmp3", "Could not set ringtone", error);
            if (saved != null) {
                try { context.getContentResolver().delete(saved, null, null); }
                catch (Exception ignored) { }
            }
            return failure("Could not set this track as the ringtone.");
        }
    }

    private java.util.List<String> folderUris() {
        java.util.List<String> uris = new java.util.ArrayList<>();
        try {
            JSONArray array = new JSONArray(context.getSharedPreferences("library", 0).getString(FOLDERS, "[]"));
            for (int i = 0; i < array.length(); i++) uris.add(array.getString(i));
        } catch (JSONException ignored) { }
        return uris;
    }

    String folders() {
        JSONArray result = new JSONArray();
        for (String raw : folderUris()) {
            Uri uri = Uri.parse(raw);
            String label = DocumentsContract.getTreeDocumentId(uri);
            try (Cursor cursor = context.getContentResolver().query(
                    DocumentsContract.buildDocumentUriUsingTree(uri, label),
                    new String[] { DocumentsContract.Document.COLUMN_DISPLAY_NAME }, null, null, null)) {
                if (cursor != null && cursor.moveToFirst()) label = cursor.getString(0);
            } catch (Exception ignored) { }
            try { result.put(new JSONObject().put("uri", raw).put("name", label)); }
            catch (JSONException ignored) { }
        }
        return result.toString();
    }

    void addFolder(Uri uri) {
        java.util.List<String> uris = folderUris();
        if (!uris.contains(uri.toString())) uris.add(uri.toString());
        saveFolders(uris);
    }

    String removeFolder(String raw) {
        java.util.List<String> uris = folderUris();
        if (!uris.remove(raw)) return failure("Folder not found.");
        saveFolders(uris);
        try { context.getContentResolver().releasePersistableUriPermission(Uri.parse(raw), Intent.FLAG_GRANT_READ_URI_PERMISSION); }
        catch (SecurityException ignored) { }
        return "{}";
    }

    private void saveFolders(java.util.List<String> uris) {
        context.getSharedPreferences("library", 0).edit().putString(FOLDERS, new JSONArray(uris).toString()).apply();
    }

    Uri mediaUri(String id) {
        Uri selected = indexedFiles.get(id);
        if (selected != null) return selected;
        File own = file(id);
        if (own != null) return Uri.fromFile(own);
        if (id != null) {
            Uri uri = Uri.parse(id);
            if ("content".equals(uri.getScheme()) && DocumentsContract.isDocumentUri(context, uri)) {
                for (String tree : folderUris()) {
                    if (id.startsWith(tree + "/document/")) return uri;
                }
            }
        }
        return null;
    }

    File file(String name) {
        if (name == null || name.isEmpty() || !name.equals(new File(name).getName())
                || name.contains("/") || name.contains("\\") || !name.toLowerCase().endsWith(".mp3")) return null;
        File found = new File(directory, name);
        return found.isFile() ? found : null;
    }

    static String validUrl(String raw) {
        if (raw == null || raw.length() > 4096) throw new IllegalArgumentException("Enter one HTTP or HTTPS URL.");
        String value = raw.trim();
        Uri url = Uri.parse(value);
        String scheme = url.getScheme();
        String host = url.getHost();
        if ((scheme == null || !(scheme.equalsIgnoreCase("https") || scheme.equalsIgnoreCase("http")))
                || host == null || host.isEmpty() || url.getUserInfo() != null
                || host.equalsIgnoreCase("localhost") || host.endsWith(".local")) {
            throw new IllegalArgumentException("Enter one public HTTP or HTTPS URL.");
        }
        if (host.matches("[0-9.]+") || host.contains(":")) {
            try {
                InetAddress address = InetAddress.getByName(host);
                byte[] bytes = address.getAddress();
                if (address.isAnyLocalAddress() || address.isLoopbackAddress()
                        || address.isSiteLocalAddress() || address.isLinkLocalAddress()
                        || address.isMulticastAddress()
                        || (bytes.length == 16 && (bytes[0] & 0xfe) == 0xfc)) {
                    throw new IllegalArgumentException("Local and private network URLs are not accepted.");
                }
            } catch (java.net.UnknownHostException error) {
                throw new IllegalArgumentException("The URL host could not be resolved.");
            }
        }
        return value;
    }

    String submit(String raw) {
        try {
            String url = validUrl(raw);
            String id = UUID.randomUUID().toString();
            Job job = new Job(id);
            jobs.put(id, job);
            if (jobs.size() > 30) jobs.entrySet().removeIf(entry ->
                !entry.getKey().equals(id) && (entry.getValue().state.equals("done") || entry.getValue().state.equals("error")));
            downloads.execute(() -> download(job, url));
            return new JSONObject().put("job", id).toString();
        } catch (Exception error) { return failure(error.getMessage()); }
    }

    String job(String id) {
        Job found = jobs.get(id);
        if (found == null) return "null";
        try { return found.json().toString(); }
        catch (JSONException ignored) { return "null"; }
    }

    private void initialize() throws Exception {
        if (ready) return;
        YoutubeDL.getInstance().init(context);
        FFmpeg.getInstance().init(context);
        ready = true;
    }

    private void refreshExtractor() {
        long now = System.currentTimeMillis();
        android.content.SharedPreferences prefs = context.getSharedPreferences("downloader", 0);
        if (now - prefs.getLong("last_update", 0) < 24 * 60 * 60 * 1000L) return;
        prefs.edit().putLong("last_update", now).apply();
        try {
            YoutubeDL.getInstance().updateYoutubeDL(context, YoutubeDL.UpdateChannel._STABLE);
        } catch (Exception error) {
            // Keep the bundled extractor usable when the update endpoint is offline.
            Log.w("ytmp3", "yt-dlp update unavailable", error);
        }
    }

    private void download(Job job, String url) {
        job.state = "working";
        try {
            Uri source = Uri.parse(url);
            if ("open.spotify.com".equalsIgnoreCase(source.getHost())
                    && source.getPath() != null && source.getPath().startsWith("/playlist/")) {
                throw new IllegalArgumentException("Spotify playlist links are not supported. Import an M3U of local MP3s instead.");
            }
            initialize();
            refreshExtractor();
            YoutubeDLRequest probe = new YoutubeDLRequest(url);
            probe.addOption("--flat-playlist");
            probe.addOption("--dump-single-json");
            probe.addOption("--skip-download");
            probe.addOption("--playlist-end", "101");
            probe.addOption("--yes-playlist");
            probe.addOption("--no-warnings");
            JSONObject info = new JSONObject(YoutubeDL.getInstance().execute(probe).getOut());
            JSONArray entries = info.optJSONArray("entries");
            if (entries != null && entries.length() > 100)
                throw new IllegalArgumentException("This playlist has more than 100 items. Use a shorter playlist.");
            job.total = entries == null ? 1 : entries.length();
            if (job.total == 0) throw new IllegalArgumentException("This playlist has no available items.");
            if (entries != null) job.playlist = info.optString("title", "Playlist");
            for (int index = 0; index < job.total; index++) {
                try {
                    JSONObject entry = entries == null ? info : entries.optJSONObject(index);
                    if (entry == null) throw new IOException("Unavailable playlist item.");
                    String itemUrl = entries == null ? url : entry.optString("webpage_url", "");
                    if (itemUrl.isEmpty()) itemUrl = entry.optString("url", "");
                    if (!itemUrl.startsWith("http://") && !itemUrl.startsWith("https://")
                            && "Youtube".equals(entry.optString("ie_key")) && !entry.optString("id").isEmpty()) {
                        itemUrl = "https://www.youtube.com/watch?v=" + entry.optString("id");
                    }
                    job.track = downloadOne(job, validUrl(itemUrl));
                    job.tracks.put(job.track);
                    job.saved++;
                } catch (Exception error) {
                    Log.w("ytmp3", "Playlist item failed", error);
                    job.failed++;
                }
                job.completed++;
            }
            if (job.saved == 0) throw new IOException("No items could be saved.");
            job.state = "done";
        } catch (IllegalArgumentException error) {
            Log.w("ytmp3", "Download rejected", error);
            job.error = error.getMessage();
            job.state = "error";
        } catch (Exception error) {
            Log.e("ytmp3", "Download failed", error);
            job.error = "Could not save this link. Check the URL and connection, then try again.";
            job.state = "error";
        }
    }

    private String downloadOne(Job job, String url) throws Exception {
        File temp = new File(context.getCacheDir(), "ytmp3-" + job.id);
        try {
            if (!temp.mkdir()) throw new IOException("Could not prepare a download folder.");
            YoutubeDLRequest request = new YoutubeDLRequest(url);
            request.addOption("--no-playlist");
            request.addOption("--no-mtime");
            request.addOption("--no-warnings");
            request.addOption("-f", "bestaudio/best");
            request.addOption("--extract-audio");
            request.addOption("--audio-format", "mp3");
            request.addOption("--audio-quality", "0");
            request.addOption("-o", new File(temp, "%(title).120B [%(id)s].%(ext)s").getAbsolutePath());
            YoutubeDL.getInstance().execute(request);
            File[] produced = temp.listFiles(file -> file.isFile() && file.getName().toLowerCase().endsWith(".mp3"));
            if (produced == null || produced.length != 1) throw new IOException("yt-dlp did not produce one MP3 file.");
            String name = produced[0].getName();
            File target = new File(directory, name);
            int number = 2;
            while (target.exists()) {
                String stem = name.substring(0, name.length() - 4);
                target = new File(directory, stem + " (" + number++ + ").mp3");
            }
            File staged = new File(directory, "." + job.id + ".part");
            try {
                Files.copy(produced[0].toPath(), staged.toPath());
                Files.move(staged.toPath(), target.toPath());
            } finally { if (staged.exists()) staged.delete(); }
            return target.getName();
        } finally { deleteTemp(temp); }
    }

    private static void deleteTemp(File file) {
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) for (File child : children) deleteTemp(child);
        }
        if (file.exists()) file.delete();
    }

    String exportTrack(String name) {
        File source = file(name);
        if (source == null) return failure("File not found.");
        exports.execute(() -> {
            Uri uri = null;
            try {
                ContentValues values = new ContentValues();
                values.put(MediaStore.MediaColumns.DISPLAY_NAME, source.getName());
                values.put(MediaStore.MediaColumns.MIME_TYPE, "audio/mpeg");
                values.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_MUSIC + "/ytmp3");
                values.put(MediaStore.MediaColumns.IS_PENDING, 1);
                uri = context.getContentResolver().insert(MediaStore.Audio.Media.EXTERNAL_CONTENT_URI, values);
                if (uri == null) throw new IOException("Could not create the Music file.");
                try (FileInputStream input = new FileInputStream(source);
                     OutputStream output = context.getContentResolver().openOutputStream(uri)) {
                    if (output == null) throw new IOException("Could not open the Music file.");
                    byte[] buffer = new byte[65536];
                    int count;
                    while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
                }
                values.clear();
                values.put(MediaStore.MediaColumns.IS_PENDING, 0);
                context.getContentResolver().update(uri, values, null, null);
                toast("Saved to Music/ytmp3");
            } catch (Exception error) {
                if (uri != null) context.getContentResolver().delete(uri, null, null);
                Log.e("ytmp3", "Export failed", error);
                toast("Could not save the file to Music.");
            }
        });
        return "{}";
    }

    private void toast(String message) {
        new android.os.Handler(context.getMainLooper()).post(() ->
            Toast.makeText(context, message, Toast.LENGTH_LONG).show());
    }

    private static String failure(String message) {
        try { return new JSONObject().put("error", message == null ? "Operation failed." : message).toString(); }
        catch (JSONException ignored) { return "{\"error\":\"Operation failed.\"}"; }
    }
}
