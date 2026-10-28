package io.github.blueraddish.ytmp3;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

/** An unprivileged website surface: no JS bridge, app assets, files, or downloads. */
public final class SourcePreviewActivity extends Activity {
    private WebView page;
    private TextView address, status;
    private Button back, save;
    private ProgressBar progress;
    private String initialUrl;
    private boolean search, failed;
    private int ink, muted, accent, surface;

    static boolean safeUrl(String raw) {
        if (raw == null || raw.length() > 4096) return false;
        try {
            Uri uri = Uri.parse(raw);
            return "https".equalsIgnoreCase(uri.getScheme()) && uri.getHost() != null
                && !uri.getHost().isEmpty() && uri.getUserInfo() == null
                && !"appassets.androidplatform.net".equalsIgnoreCase(uri.getHost());
        } catch (RuntimeException error) { return false; }
    }

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }

    @SuppressLint("SetJavaScriptEnabled")
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        initialUrl = getIntent().getStringExtra("url");
        search = getIntent().getBooleanExtra("search", false);
        if (!safeUrl(initialUrl)) { finish(); return; }
        boolean light = "light".equals(getIntent().getStringExtra("theme"));
        surface = Color.parseColor(light ? "#ffffff" : "#172123");
        ink = Color.parseColor(light ? "#15221e" : "#f0f6f4");
        muted = Color.parseColor(light ? "#52645e" : "#9badab");
        accent = Color.parseColor(light ? "#146d54" : "#70d7b4");
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(surface);
        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setPadding(dp(4), dp(4), dp(4), dp(4));
        back = button("‹", "Back in website");
        back.setTextSize(28);
        back.setOnClickListener(view -> goBack());
        toolbar.addView(back, new LinearLayout.LayoutParams(dp(48), dp(48)));
        address = new TextView(this);
        address.setTextColor(ink);
        address.setTextSize(13);
        address.setMaxLines(2);
        address.setEllipsize(android.text.TextUtils.TruncateAt.END);
        toolbar.addView(address, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        Button reload = button("↻", "Reload website");
        reload.setTextSize(24);
        reload.setOnClickListener(view -> page.reload());
        toolbar.addView(reload, new LinearLayout.LayoutParams(dp(48), dp(48)));
        Button close = button("×", "Close website preview");
        close.setTextSize(26);
        close.setOnClickListener(view -> finish());
        toolbar.addView(close, new LinearLayout.LayoutParams(dp(48), dp(48)));
        root.addView(toolbar);
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setProgressTintList(ColorStateList.valueOf(accent));
        root.addView(progress, new LinearLayout.LayoutParams(-1, dp(3)));
        page = new WebView(this);
        page.setBackgroundColor(surface);
        WebSettings settings = page.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setMediaPlaybackRequiresUserGesture(true);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setSupportMultipleWindows(false);
        // Never attach Ytmp3Android (or any native bridge) to third-party pages.
        page.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (safeUrl(request.getUrl().toString())) return false;
                if (request.isForMainFrame()) status.setText("This link cannot open in the preview. Choose an HTTPS track page.");
                return true;
            }
            @Override public void onPageStarted(WebView view, String url, android.graphics.Bitmap icon) {
                failed = false;
                update(url);
            }
            @Override public void doUpdateVisitedHistory(WebView view, String url, boolean reload) { update(url); }
            @Override public void onPageFinished(WebView view, String url) { update(url); }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (!request.isForMainFrame()) return;
                failed = true;
                update(view.getUrl());
                status.setText("Could not load this page. Check your connection and tap Reload.");
            }
        });
        page.setWebChromeClient(new WebChromeClient() {
            @Override public void onProgressChanged(WebView view, int value) {
                progress.setProgress(value);
                progress.setVisibility(value == 100 ? android.view.View.INVISIBLE : android.view.View.VISIBLE);
            }
            @Override public void onReceivedTitle(WebView view, String title) { update(view.getUrl()); }
        });
        root.addView(page, new LinearLayout.LayoutParams(-1, 0, 1));
        LinearLayout footer = new LinearLayout(this);
        footer.setOrientation(LinearLayout.VERTICAL);
        footer.setPadding(dp(12), dp(8), dp(12), dp(12));
        status = new TextView(this);
        status.setTextColor(muted);
        status.setTextSize(12);
        status.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);
        footer.addView(status);
        save = button("Save MP3", "Save MP3 from this page");
        save.setTextColor(light ? Color.WHITE : Color.parseColor("#102822"));
        save.setBackgroundTintList(ColorStateList.valueOf(accent));
        save.setOnClickListener(view -> {
            String url = page.getUrl();
            if (!canSave(url)) return;
            setResult(RESULT_OK, new Intent().putExtra("url", url));
            finish();
        });
        LinearLayout.LayoutParams saveSize = new LinearLayout.LayoutParams(-1, dp(48));
        saveSize.topMargin = dp(8);
        footer.addView(save, saveSize);
        root.addView(footer);
        setContentView(root);
        update(initialUrl);
        if (state == null || page.restoreState(state) == null) page.loadUrl(initialUrl);
    }

    private Button button(String text, String description) {
        Button button = new Button(this);
        button.setText(text);
        button.setAllCaps(false);
        button.setTextColor(ink);
        button.setTextSize(14);
        button.setMinWidth(0);
        button.setMinimumWidth(0);
        button.setPadding(0, 0, 0, 0);
        button.setBackgroundTintList(ColorStateList.valueOf(surface));
        button.setContentDescription(description);
        return button;
    }

    private boolean canSave(String url) {
        if (failed || !safeUrl(url)) return false;
        Uri uri = Uri.parse(url);
        String path = uri.getPath() == null ? "" : uri.getPath();
        if (path.equals("/results") || path.toLowerCase(java.util.Locale.ROOT).contains("search")) return false;
        // Redirecting a search to a mobile hostname does not turn it into a track.
        if (!search) return true;
        Uri initial = Uri.parse(initialUrl);
        return !path.equals(initial.getPath()) || !uri.getQueryParameterNames().equals(initial.getQueryParameterNames());
    }

    private void update(String url) {
        if (address == null || save == null) return;
        Uri uri = Uri.parse(url == null ? initialUrl : url);
        String title = page.getTitle();
        address.setText((title == null || title.isEmpty() ? "Website preview" : title) + "\n" + uri.getHost());
        back.setContentDescription(page.canGoBack() ? "Back in website" : "Close website preview");
        save.setEnabled(canSave(url));
        if (!failed) status.setText(canSave(url) ? "Save audio from the page shown above." : "Open a track or playlist, then tap Save MP3.");
    }

    @Override protected void onStart() {
        super.onStart();
        Window window = getWindow();
        window.setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(Color.TRANSPARENT));
        window.addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);
        WindowManager.LayoutParams params = window.getAttributes();
        params.width = ViewGroup.LayoutParams.MATCH_PARENT;
        params.height = (int) (getResources().getDisplayMetrics().heightPixels * .94);
        params.gravity = Gravity.BOTTOM;
        params.dimAmount = .35f;
        window.setAttributes(params);
    }

    private void goBack() { if (page.canGoBack()) page.goBack(); else finish(); }
    @Override @SuppressWarnings("deprecation") public void onBackPressed() { goBack(); }
    @Override protected void onSaveInstanceState(Bundle state) { page.saveState(state); super.onSaveInstanceState(state); }
    @Override protected void onPause() { if (page != null) page.onPause(); super.onPause(); }
    @Override protected void onResume() { super.onResume(); if (page != null) page.onResume(); }
    @Override protected void onDestroy() { if (page != null) { page.stopLoading(); page.destroy(); } super.onDestroy(); }
}
