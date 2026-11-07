package app.narra.audiolivro;

import android.media.MediaCodec;
import android.media.MediaCodecInfo;
import android.media.MediaFormat;
import android.media.MediaMuxer;

import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.util.List;

/** Junta vários WAV PCM 16 bits (saída do TextToSpeech) em um único arquivo M4A (AAC-LC). */
final class AacEncoder {

    private AacEncoder() { }

    static final class WavInfo {
        int sampleRate = 24000;
        int channels = 1;
        int bits = 16;
        long dataOffset = 44;
        long dataSize = -1;
    }

    static WavInfo readHeader(File f) throws IOException {
        WavInfo w = new WavInfo();
        try (InputStream in = new BufferedInputStream(new FileInputStream(f))) {
            byte[] h = new byte[12];
            if (in.read(h) != 12 || h[0] != 'R' || h[1] != 'I' || h[2] != 'F' || h[3] != 'F') {
                throw new IOException("arquivo de voz em formato inesperado");
            }
            long pos = 12;
            byte[] ch = new byte[8];
            while (true) {
                if (readFully(in, ch) != 8) break;
                pos += 8;
                String id = new String(ch, 0, 4, "US-ASCII");
                long size = le32(ch, 4);
                if (id.equals("fmt ")) {
                    byte[] fmt = new byte[(int) size];
                    readFully(in, fmt);
                    w.channels = le16(fmt, 2);
                    w.sampleRate = (int) le32(fmt, 4);
                    w.bits = le16(fmt, 14);
                    pos += size;
                } else if (id.equals("data")) {
                    w.dataOffset = pos;
                    w.dataSize = (size <= 0 || size == 0xFFFFFFFFL) ? f.length() - pos : Math.min(size, f.length() - pos);
                    break;
                } else {
                    skipFully(in, size + (size & 1));
                    pos += size + (size & 1);
                }
            }
        }
        if (w.dataSize < 0) w.dataSize = Math.max(0, f.length() - w.dataOffset);
        if (w.bits != 16) throw new IOException("áudio de " + w.bits + " bits não suportado");
        return w;
    }

    static void encode(List<File> wavs, File out) throws Exception {
        if (wavs.isEmpty()) throw new IOException("nada para gravar");
        WavInfo first = readHeader(wavs.get(0));
        int rate = first.sampleRate, ch = first.channels;

        MediaFormat fmt = MediaFormat.createAudioFormat(MediaFormat.MIMETYPE_AUDIO_AAC, rate, ch);
        fmt.setInteger(MediaFormat.KEY_AAC_PROFILE, MediaCodecInfo.CodecProfileLevel.AACObjectLC);
        fmt.setInteger(MediaFormat.KEY_BIT_RATE, ch == 1 ? 64000 : 96000);
        fmt.setInteger(MediaFormat.KEY_MAX_INPUT_SIZE, 16384);

        MediaCodec codec = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_AUDIO_AAC);
        codec.configure(fmt, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE);
        codec.start();
        MediaMuxer mux = new MediaMuxer(out.getAbsolutePath(), MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4);
        int track = -1;
        boolean muxing = false;
        MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
        long samples = 0;
        int frame = 2 * ch;

        int fileIdx = 0;
        InputStream cur = null;
        long remaining = 0;
        boolean inputDone = false, outputDone = false;
        byte[] tmp = new byte[8192];

        try {
            while (!outputDone) {
                if (!inputDone) {
                    int inIdx = codec.dequeueInputBuffer(10000);
                    if (inIdx >= 0) {
                        ByteBuffer buf = codec.getInputBuffer(inIdx);
                        buf.clear();
                        int want = Math.min(buf.remaining(), tmp.length);
                        want -= want % frame;
                        int got = 0;
                        while (got < want) {
                            if (cur == null || remaining <= 0) {
                                if (cur != null) { cur.close(); cur = null; }
                                if (fileIdx >= wavs.size()) break;
                                File f = wavs.get(fileIdx++);
                                WavInfo w = readHeader(f);
                                if (w.sampleRate != rate || w.channels != ch) {
                                    throw new IOException("trechos com formatos de áudio diferentes");
                                }
                                cur = new BufferedInputStream(new FileInputStream(f), 65536);
                                skipFully(cur, w.dataOffset);
                                remaining = w.dataSize - (w.dataSize % frame);
                                continue;
                            }
                            int n = cur.read(tmp, got, (int) Math.min(want - got, remaining));
                            if (n <= 0) { remaining = 0; continue; }
                            got += n;
                            remaining -= n;
                        }
                        got -= got % frame;
                        long pts = samples * 1000000L / rate;
                        if (got == 0) {
                            codec.queueInputBuffer(inIdx, 0, 0, pts, MediaCodec.BUFFER_FLAG_END_OF_STREAM);
                            inputDone = true;
                        } else {
                            buf.put(tmp, 0, got);
                            codec.queueInputBuffer(inIdx, 0, got, pts, 0);
                            samples += got / frame;
                        }
                    }
                }
                int outIdx = codec.dequeueOutputBuffer(info, 10000);
                if (outIdx == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    track = mux.addTrack(codec.getOutputFormat());
                    mux.start();
                    muxing = true;
                } else if (outIdx >= 0) {
                    if ((info.flags & MediaCodec.BUFFER_FLAG_CODEC_CONFIG) != 0) info.size = 0;
                    if (info.size > 0 && muxing) {
                        ByteBuffer ob = codec.getOutputBuffer(outIdx);
                        ob.position(info.offset);
                        ob.limit(info.offset + info.size);
                        mux.writeSampleData(track, ob, info);
                    }
                    codec.releaseOutputBuffer(outIdx, false);
                    if ((info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) outputDone = true;
                }
            }
        } finally {
            if (cur != null) cur.close();
            try { codec.stop(); } catch (Exception ignored) { }
            codec.release();
            try { if (muxing) mux.stop(); } catch (Exception ignored) { }
            mux.release();
        }
    }

    private static int readFully(InputStream in, byte[] b) throws IOException {
        int got = 0;
        while (got < b.length) {
            int n = in.read(b, got, b.length - got);
            if (n < 0) break;
            got += n;
        }
        return got;
    }

    private static void skipFully(InputStream in, long n) throws IOException {
        while (n > 0) {
            long s = in.skip(n);
            if (s <= 0) {
                if (in.read() < 0) return;
                s = 1;
            }
            n -= s;
        }
    }

    private static int le16(byte[] b, int o) { return (b[o] & 0xff) | (b[o + 1] & 0xff) << 8; }

    private static long le32(byte[] b, int o) {
        return (b[o] & 0xffL) | (b[o + 1] & 0xffL) << 8 | (b[o + 2] & 0xffL) << 16 | (b[o + 3] & 0xffL) << 24;
    }
}
