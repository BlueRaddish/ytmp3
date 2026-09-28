package io.github.blueraddish.ytmp3;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;

import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.OutputStream;

/** Supplies one cover on demand, so long play queues do not carry image bytes. */
public final class CoverProvider extends ContentProvider {
    private AndroidLibrary library;

    @Override public boolean onCreate() {
        library = new AndroidLibrary(getContext());
        return true;
    }

    private byte[] image(Uri uri) throws FileNotFoundException {
        if (!"io.github.blueraddish.ytmp3.covers".equals(uri.getAuthority()))
            throw new FileNotFoundException();
        byte[] data = library.cover(uri.getLastPathSegment());
        if (data == null) throw new FileNotFoundException();
        return data;
    }

    @Override public String getType(Uri uri) {
        try { return AndroidLibrary.coverType(image(uri)); }
        catch (FileNotFoundException error) { return null; }
    }

    @Override public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        if (!"r".equals(mode)) throw new FileNotFoundException();
        byte[] data = image(uri);
        try {
            ParcelFileDescriptor[] pipe = ParcelFileDescriptor.createPipe();
            new Thread(() -> {
                try (OutputStream output = new ParcelFileDescriptor.AutoCloseOutputStream(pipe[1])) {
                    output.write(data);
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
