package app.narra.audiolivro;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.database.Cursor;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;
import android.util.Base64;
import android.view.View;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * Narra para Android: a interface é a versão web (assets/www), e a narração usa o
 * motor de voz do próprio Android (TextToSpeech), exposto ao JavaScript como "NarraTTS".
 */
public class MainActivity extends Activity implements TextToSpeech.OnInitListener {

    private static final int REQ_PICK = 1;
    private static final int REQ_SAVE = 2;
    private static final long MAX_OPEN_BYTES = 60L * 1024 * 1024;

    private WebView web;
    private TextToSpeech tts;
    private volatile boolean ttsReady = false;
    private ValueCallback<Uri[]> fileCallback;
    private volatile String pendingFile = null;

    // gravação em arquivo
    private final Map<String, CountDownLatch> synthLatches = new ConcurrentHashMap<>();
    private final Map<String, Boolean> synthOk = new ConcurrentHashMap<>();
    private volatile boolean exportCancel = false;
    private volatile boolean exporting = false;
    private String[] exportChunks;
    private String exportVoice, exportLang;
    private float exportRate, exportPitch;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Color.parseColor("#1a2333"));

        web = new WebView(this);
        WebSettings ws = web.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setDatabaseEnabled(true);
        ws.setMediaPlaybackRequiresUserGesture(false);
        ws.setTextZoom(100);
        web.setBackgroundColor(Color.parseColor("#eef1f4"));
        web.addJavascriptInterface(new Bridge(), "NarraTTS");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                if (url.startsWith("file:///android_asset/")) return false;
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
                } catch (Exception ignored) { }
                return true;
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                                             FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                Intent i = new Intent(Intent.ACTION_GET_CONTENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("*/*");
                i.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{
                        "application/pdf", "application/msword",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "text/plain", "application/octet-stream"});
                try {
                    startActivityForResult(Intent.createChooser(i, "Escolher documento"), REQ_PICK);
                } catch (ActivityNotFoundException e) {
                    fileCallback = null;
                    return false;
                }
                return true;
            }
        });
        setContentView(web);

        tts = new TextToSpeech(this, this);
        tts.setOnUtteranceProgressListener(new Progress());

        handleIntent(getIntent());
        web.loadUrl("file:///android_asset/www/index.html");
    }

    // ------------------------------------------------------------ TTS
    @Override
    public void onInit(int status) {
        ttsReady = status == TextToSpeech.SUCCESS;
        js("window.__ttsReady&&window.__ttsReady(" + ttsReady + ")");
    }

    private class Progress extends UtteranceProgressListener {
        @Override
        public void onStart(String id) { event(id, "start"); }

        @Override
        public void onDone(String id) {
            if (id.startsWith("x_")) { synthOk.put(id, true); release(id); }
            else event(id, "done");
        }

        @Override
        public void onError(String id) {
            if (id.startsWith("x_")) { synthOk.put(id, false); release(id); }
            else event(id, "error");
        }

        @Override
        public void onError(String id, int code) { onError(id); }

        @Override
        public void onStop(String id, boolean interrupted) {
            if (id.startsWith("x_")) { synthOk.put(id, false); release(id); }
        }

        private void release(String id) {
            CountDownLatch l = synthLatches.get(id);
            if (l != null) l.countDown();
        }

        /** ids de fala: p_<geração>_<frase> */
        private void event(String id, String ev) {
            if (!id.startsWith("p_")) return;
            String[] p = id.split("_");
            if (p.length < 3) return;
            js("window.__tts&&window.__tts('" + ev + "'," + p[1] + "," + p[2] + ")");
        }
    }

    private void applyVoice(String voiceName, String lang, float rate, float pitch) {
        Voice chosen = null;
        try {
            if (voiceName != null && voiceName.length() > 0 && tts.getVoices() != null) {
                for (Voice v : tts.getVoices()) {
                    if (v.getName().equals(voiceName)) { chosen = v; break; }
                }
            }
        } catch (Exception ignored) { }
        if (chosen != null) tts.setVoice(chosen);
        else tts.setLanguage(Locale.forLanguageTag(lang));
        tts.setSpeechRate(rate);
        tts.setPitch(pitch);
    }

    private static String pretty(Voice v) {
        Locale l = v.getLocale();
        String country = l.getDisplayCountry(new Locale("pt", "BR"));
        String n = v.getName().toLowerCase(Locale.ROOT);
        String code = "";
        String[] parts = n.split("-");
        for (int i = 0; i < parts.length - 1; i++) {
            if (parts[i].equals("x") && i + 1 < parts.length) { code = parts[i + 1]; break; }
        }
        StringBuilder sb = new StringBuilder();
        sb.append(country.length() > 0 ? country : l.getDisplayLanguage());
        if (code.length() > 0) sb.append(" ").append(code.toUpperCase(Locale.ROOT));
        else if (!n.contains("language")) sb.append(" ").append(v.getName());
        if (v.isNetworkConnectionRequired()) sb.append(" (online)");
        return sb.toString();
    }

    // ------------------------------------------------------------ ponte JS
    private class Bridge {
        @JavascriptInterface
        public String getVoices() {
            JSONArray arr = new JSONArray();
            if (!ttsReady) return arr.toString();
            try {
                for (Voice v : tts.getVoices()) {
                    if (v.getFeatures() != null && v.getFeatures().contains(
                            TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED)) continue;
                    String lang = v.getLocale().getLanguage();
                    if (!lang.equals("pt") && !lang.equals("en") && !lang.equals("es")) continue;
                    JSONObject o = new JSONObject();
                    o.put("name", v.getName());
                    o.put("lang", v.getLocale().toLanguageTag());
                    o.put("label", pretty(v));
                    o.put("neural", v.getQuality() >= Voice.QUALITY_HIGH || v.isNetworkConnectionRequired());
                    arr.put(o);
                }
            } catch (Exception ignored) { }
            return arr.toString();
        }

        @JavascriptInterface
        public void speakQueue(String json, int start, int gen, String voice, String lang,
                               double rate, double pitch, boolean flush) {
            if (!ttsReady) { toast("O motor de voz ainda não está pronto."); return; }
            try {
                JSONArray a = new JSONArray(json);
                applyVoice(voice, lang, (float) rate, (float) pitch);
                for (int i = 0; i < a.length(); i++) {
                    int mode = (flush && i == 0) ? TextToSpeech.QUEUE_FLUSH : TextToSpeech.QUEUE_ADD;
                    String id = gen < 0 ? "t_" + i : "p_" + gen + "_" + (start + i);
                    tts.speak(a.getString(i), mode, null, id);
                }
            } catch (Exception e) {
                toast("Erro na fala: " + e.getMessage());
            }
        }

        @JavascriptInterface
        public void stop() {
            if (ttsReady && !exporting) tts.stop();
        }

        @JavascriptInterface
        public void openSettings() {
            runOnUiThread(new Runnable() { public void run() {
                try {
                    startActivity(new Intent("com.android.settings.TTS_SETTINGS"));
                } catch (Exception e) {
                    try {
                        startActivity(new Intent(TextToSpeech.Engine.ACTION_INSTALL_TTS_DATA));
                    } catch (Exception e2) {
                        toast("Abra Configurações > Acessibilidade > Saída de texto para fala.");
                    }
                }
            }});
        }

        @JavascriptInterface
        public String takePendingFile() {
            String f = pendingFile;
            pendingFile = null;
            return f == null ? "" : f;
        }

        @JavascriptInterface
        public void exportAudio(String chunksJson, String title, String voice, String lang,
                                double rate, double pitch) {
            if (exporting) return;
            try {
                JSONArray a = new JSONArray(chunksJson);
                exportChunks = new String[a.length()];
                for (int i = 0; i < a.length(); i++) exportChunks[i] = a.getString(i);
            } catch (Exception e) {
                exp("error", e.getMessage());
                return;
            }
            exportVoice = voice;
            exportLang = lang;
            exportRate = (float) rate;
            exportPitch = (float) pitch;
            String safe = title.replaceAll("[\\\\/:*?\"<>|]+", " ").trim();
            if (safe.isEmpty()) safe = "audiolivro";
            final String fname = safe + ".m4a";
            runOnUiThread(new Runnable() { public void run() {
                Intent i = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("audio/mp4");
                i.putExtra(Intent.EXTRA_TITLE, fname);
                try {
                    startActivityForResult(i, REQ_SAVE);
                } catch (ActivityNotFoundException e) {
                    exp("error", "nenhum app para salvar arquivos");
                }
            }});
        }

        @JavascriptInterface
        public void cancelExport() {
            exportCancel = true;
            if (ttsReady) tts.stop();
        }
    }

    // ------------------------------------------------------------ gravação
    private void runExport(final Uri target) {
        exporting = true;
        exportCancel = false;
        new Thread(new Runnable() { public void run() {
            File dir = new File(getCacheDir(), "export");
            List<File> wavs = new ArrayList<>();
            File m4a = new File(getCacheDir(), "narra-export.m4a");
            try {
                deleteDir(dir);
                dir.mkdirs();
                tts.stop();
                applyVoice(exportVoice, exportLang, exportRate, exportPitch);
                int total = exportChunks.length;
                for (int i = 0; i < total; i++) {
                    if (exportCancel) throw new InterruptedException();
                    exp("progress", (i + 1) + "," + total);
                    File f = new File(dir, String.format(Locale.ROOT, "c%05d.wav", i));
                    String id = "x_" + i;
                    CountDownLatch latch = new CountDownLatch(1);
                    synthLatches.put(id, latch);
                    Bundle params = new Bundle();
                    int r = tts.synthesizeToFile(exportChunks[i], params, f, id);
                    if (r != TextToSpeech.SUCCESS) throw new Exception("o motor de voz recusou o trecho " + (i + 1));
                    if (!latch.await(180, TimeUnit.SECONDS)) throw new Exception("tempo esgotado no trecho " + (i + 1));
                    synthLatches.remove(id);
                    if (exportCancel) throw new InterruptedException();
                    Boolean ok = synthOk.remove(id);
                    if (ok == null || !ok || !f.exists() || f.length() <= 44) {
                        throw new Exception("falha ao gravar o trecho " + (i + 1)
                                + ". Se a voz é online, verifique a internet.");
                    }
                    wavs.add(f);
                }
                exp("encoding", "");
                AacEncoder.encode(wavs, m4a);
                try (InputStream in = new java.io.FileInputStream(m4a);
                     java.io.OutputStream out = getContentResolver().openOutputStream(target)) {
                    if (out == null) throw new Exception("não foi possível abrir o destino");
                    byte[] buf = new byte[65536];
                    int n;
                    while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
                }
                exp("done", displayName(target));
            } catch (InterruptedException e) {
                deleteTarget(target);
                exp("cancel", "");
            } catch (Throwable e) {
                deleteTarget(target);
                exp("error", e.getMessage() == null ? e.toString() : e.getMessage());
            } finally {
                deleteDir(dir);
                m4a.delete();
                exporting = false;
                runOnUiThread(new Runnable() { public void run() {
                    getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
                }});
            }
        }}, "narra-export").start();
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    private void deleteTarget(Uri u) {
        try {
            android.provider.DocumentsContract.deleteDocument(getContentResolver(), u);
        } catch (Exception ignored) { }
    }

    private static void deleteDir(File d) {
        File[] fs = d.listFiles();
        if (fs != null) for (File f : fs) f.delete();
        d.delete();
    }

    private void exp(String ev, String arg) {
        String a, b = "0";
        if (ev.equals("progress")) {
            String[] p = arg.split(",");
            a = p[0];
            b = p[1];
        } else {
            a = JSONObject.quote(arg);
        }
        js("window.__exp&&window.__exp('" + ev + "'," + a + "," + b + ")");
    }

    // ------------------------------------------------------------ arquivos
    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        handleIntent(intent);
        js("window.__checkPending&&window.__checkPending()");
    }

    private void handleIntent(Intent intent) {
        if (intent == null) return;
        Uri uri = null;
        if (Intent.ACTION_VIEW.equals(intent.getAction())) uri = intent.getData();
        else if (Intent.ACTION_SEND.equals(intent.getAction())) uri = intent.getParcelableExtra(Intent.EXTRA_STREAM);
        if (uri == null) return;
        try (InputStream in = getContentResolver().openInputStream(uri)) {
            if (in == null) return;
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            byte[] buf = new byte[65536];
            int n;
            long total = 0;
            while ((n = in.read(buf)) > 0) {
                total += n;
                if (total > MAX_OPEN_BYTES) { toast("Arquivo grande demais (máx. 60 MB)."); return; }
                bos.write(buf, 0, n);
            }
            JSONObject o = new JSONObject();
            o.put("name", displayName(uri));
            o.put("b64", Base64.encodeToString(bos.toByteArray(), Base64.NO_WRAP));
            pendingFile = o.toString();
        } catch (Exception e) {
            toast("Não foi possível abrir o arquivo: " + e.getMessage());
        }
    }

    private String displayName(Uri uri) {
        String name = null;
        try (Cursor c = getContentResolver().query(uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (c != null && c.moveToFirst()) name = c.getString(0);
        } catch (Exception ignored) { }
        if (name == null) name = uri.getLastPathSegment();
        return name == null ? "documento" : name;
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_PICK) {
            if (fileCallback == null) return;
            Uri[] result = null;
            if (resultCode == RESULT_OK && data != null) {
                if (data.getClipData() != null && data.getClipData().getItemCount() > 0) {
                    result = new Uri[]{data.getClipData().getItemAt(0).getUri()};
                } else if (data.getData() != null) {
                    result = new Uri[]{data.getData()};
                }
            }
            fileCallback.onReceiveValue(result);
            fileCallback = null;
        } else if (requestCode == REQ_SAVE) {
            if (resultCode == RESULT_OK && data != null && data.getData() != null) runExport(data.getData());
            else exp("cancel", "");
        }
    }

    // ------------------------------------------------------------ utilidades
    private void js(final String code) {
        runOnUiThread(new Runnable() { public void run() {
            if (web != null) web.evaluateJavascript(code, null);
        }});
    }

    private void toast(final String msg) {
        runOnUiThread(new Runnable() { public void run() {
            Toast.makeText(MainActivity.this, msg, Toast.LENGTH_LONG).show();
        }});
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack();
        else moveTaskToBack(true); // mantém a narração tocando em segundo plano
    }

    @Override
    protected void onDestroy() {
        if (tts != null) { tts.stop(); tts.shutdown(); }
        if (web != null) { web.destroy(); web = null; }
        super.onDestroy();
    }
}
