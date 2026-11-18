package io.github.blueraddish.ytmp3;

import java.io.File;
import java.nio.file.Files;
import java.util.List;
import java.util.concurrent.ExecutionException;

public final class PlaybackReportStoreCheck {
    private static String id(int i) { return String.format("%013d-abcd", i); }
    public static void main(String[] args) throws Exception {
        File root = new File(args[0]);
        File reports = new File(root, "reports");
        try (PlaybackReportStore store = new PlaybackReportStore(reports)) {
            assert store.read().get().isEmpty();
            store.save(id(0), "{\"reason\":\"audio_focus_loss\"}");
            assert store.read().get().size() == 1;
            for (int i = 0; i < 100; i++) store.save(id(0), "{\"resumed\":" + i + "}");
            List<String> saved = store.read().get();
            assert saved.size() == 1 && saved.get(0).equals("{\"resumed\":99}");
            boolean rejected = false;
            try { store.save("../escape", "{}"); } catch (IllegalArgumentException expected) { rejected = true; }
            assert rejected;
            rejected = false;
            try { store.save(id(1), "x".repeat(65537)); } catch (IllegalArgumentException expected) { rejected = true; }
            assert rejected;
            assert !new File(root, "escape.json").exists();
        }
        Files.write(new File(reports,"interrupted.tmp").toPath(),new byte[] {1});
        try (PlaybackReportStore store = new PlaybackReportStore(reports)) {
            assert store.read().get().get(0).equals("{\"resumed\":99}") : "Recreation lost a saved report";
            assert !new File(reports,"interrupted.tmp").exists() : "Interrupted write leaked after restart";
            for (int i = 1; i < 81; i++) store.save(id(i), "{\"pause\":" + i + "}");
            List<String> saved = store.read().get();
            assert saved.size() == 64 && saved.get(63).equals("{\"pause\":80}");
            for (int i = 100; i < 140; i++) store.save(id(i), "x".repeat(60000));
            assert store.read().get().size() == 34;
            long bytes = 0;
            for (File file : reports.listFiles()) {
                assert file.getName().endsWith(".json") : "Temporary write leaked";
                bytes += file.length();
            }
            assert bytes <= 2 * 1024 * 1024 : "Storage budget exceeded";
        }
        File blocked = new File(root, "blocked");
        Files.write(blocked.toPath(), new byte[] {1});
        try (PlaybackReportStore store = new PlaybackReportStore(blocked)) {
            store.save(id(1), "{}");
            boolean failed = false;
            try { store.read().get(); } catch (ExecutionException expected) { failed = true; }
            assert failed && store.lastError() != null : "Storage failure looked like an empty success";
        }
        System.out.println("PASS: snapshot updates, persistence, 64-report/2MiB retention, safe paths, size cap and real IO failure");
    }
}
