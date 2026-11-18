package io.github.blueraddish.ytmp3;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

/** Private, bounded snapshots. Repeated updates to one incident coalesce off the player thread. */
final class PlaybackReportStore implements AutoCloseable {
    static final int MAX_REPORTS = 64;
    static final int MAX_REPORT_BYTES = 64 * 1024;
    static final long MAX_TOTAL_BYTES = 2 * 1024 * 1024;
    private final File directory;
    private final Map<String, String> pending = new LinkedHashMap<>();
    private final ExecutorService writer = Executors.newSingleThreadExecutor(action -> {
        Thread thread = new Thread(action, "ytmp3-playback-reports");
        thread.setDaemon(true);
        return thread;
    });
    private boolean draining;
    private volatile String lastError;

    PlaybackReportStore(File directory) { this.directory = directory; }

    synchronized void save(String id, String json) {
        if (!id.matches("[0-9]+-[a-f0-9-]+")) throw new IllegalArgumentException("Invalid report ID");
        if (json.getBytes(StandardCharsets.UTF_8).length > MAX_REPORT_BYTES)
            throw new IllegalArgumentException("Playback report exceeds size limit");
        pending.put(id, json);
        while (pending.size() > MAX_REPORTS) pending.remove(pending.keySet().iterator().next());
        if (!draining) {
            draining = true;
            writer.execute(this::drain);
        }
    }

    private void drain() {
        while (true) {
            String id;
            String json;
            synchronized (this) {
                if (pending.isEmpty()) { draining = false; return; }
                id = pending.keySet().iterator().next();
                json = pending.remove(id);
            }
            try { write(id, json); }
            catch (IOException | RuntimeException error) {
                lastError = error.getClass().getSimpleName() + ": report could not be saved";
            }
        }
    }

    private void write(String id, String json) throws IOException {
        if (!directory.isDirectory() && !directory.mkdirs()) throw new IOException("Report directory unavailable");
        File target = new File(directory, id + ".json");
        File temporary = new File(directory, id + ".tmp");
        try {
            try (FileOutputStream output = new FileOutputStream(temporary)) {
                output.write(json.getBytes(StandardCharsets.UTF_8));
                output.getFD().sync();
            }
            try {
                Files.move(temporary.toPath(), target.toPath(), StandardCopyOption.ATOMIC_MOVE,
                    StandardCopyOption.REPLACE_EXISTING);
            } catch (AtomicMoveNotSupportedException unsupported) {
                Files.move(temporary.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING);
            }
            prune();
        } finally { if (temporary.exists()) temporary.delete(); }
    }

    private File[] files() throws IOException {
        if (!directory.exists()) return new File[0];
        File[] unfinished = directory.listFiles(file -> file.isFile() && file.getName().endsWith(".tmp"));
        if (unfinished == null) throw new IOException("Report directory could not be read");
        for (File file : unfinished)
            if (!file.delete()) throw new IOException("Interrupted report write could not be cleaned up");
        File[] files = directory.listFiles(file -> file.isFile() && file.getName().endsWith(".json"));
        if (files == null) throw new IOException("Saved reports could not be read");
        Arrays.sort(files, Comparator.comparing(File::getName));
        return files;
    }

    private void prune() throws IOException {
        File[] files = files();
        long bytes = 0;
        for (File file : files) bytes += file.length();
        for (int i = 0; i < files.length && (files.length - i > MAX_REPORTS || bytes > MAX_TOTAL_BYTES); i++) {
            long length = files[i].length();
            if (!files[i].delete()) throw new IOException("Old playback report could not be removed");
            bytes -= length;
        }
    }

    Future<List<String>> read() {
        return writer.submit(() -> {
            List<String> reports = new ArrayList<>();
            for (File file : files()) {
                if (file.length() > MAX_REPORT_BYTES) throw new IOException("Saved playback report is too large");
                reports.add(new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8));
            }
            return reports;
        });
    }

    String lastError() { return lastError; }
    @Override public void close() { writer.shutdown(); }
}
