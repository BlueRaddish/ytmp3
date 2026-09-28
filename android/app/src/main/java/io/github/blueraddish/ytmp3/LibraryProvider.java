package io.github.blueraddish.ytmp3;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.OutputStream;

/** Reads private MP3s for share targets and artwork for the media session. */
public final class LibraryProvider extends ContentProvider {
    private AndroidLibrary library;

    @Override public boolean onCreate() {
        library = new AndroidLibrary(getContext());
        return true;
    }

    private String kind(Uri uri) throws FileNotFoundException {
        if (!"io.github.blueraddish.ytmp3.files".equals(uri.getAuthority())
                || uri.getPathSegments().size() != 2) throw new FileNotFoundException();
        return uri.getPathSegments().get(0);
    }

    @Override public String getType(Uri uri) {
        try {
            String kind = kind(uri);
            if ("shares".equals(kind))
                return library.file(uri.getLastPathSegment()) == null ? null : "audio/mpeg";
            if ("covers".equals(kind)) {
                byte[] image = library.cover(uri.getLastPathSegment());
                return image == null ? null : AndroidLibrary.coverType(image);
            }
        } catch (FileNotFoundException ignored) { }
        return null;
    }

    @Override public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        if (!"r".equals(mode)) throw new FileNotFoundException();
        String kind = kind(uri);
        if ("shares".equals(kind)) {
            File file = library.file(uri.getLastPathSegment());
            if (file == null) throw new FileNotFoundException();
            return ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY);
        }
        if (!"covers".equals(kind)) throw new FileNotFoundException();
        byte[] image = library.cover(uri.getLastPathSegment());
        if (image == null) throw new FileNotFoundException();
        try {
            ParcelFileDescriptor[] pipe = ParcelFileDescriptor.createPipe();
            new Thread(() -> {
                try (OutputStream output = new ParcelFileDescriptor.AutoCloseOutputStream(pipe[1])) {
                    output.write(image);
                } catch (IOException ignored) { }
            }, "ytmp3-cover").start();
            return pipe[0];
        } catch (IOException error) { throw new FileNotFoundException("Could not open cover."); }
    }

    @Override public Cursor query(Uri uri, String[] projection, String selection,
            String[] selectionArgs, String sortOrder) { return null; }
    @Override public Uri insert(Uri uri, ContentValues values) { return null; }
    @Override public int delete(Uri uri, String selection, String[] selectionArgs) { return 0; }
    @Override public int update(Uri uri, ContentValues values, String selection, String[] selectionArgs) { return 0; }
}
