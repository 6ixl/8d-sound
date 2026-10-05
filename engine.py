"""Аудио-движок: захват системного звука, 8D-обработка и вывод в наушники."""
import math
import threading
import time

import numpy as np
import sounddevice as sd
from scipy.signal import lfilter


def one_pole(fc, sr):
    a = math.exp(-2.0 * math.pi * fc / sr)
    return np.array([1.0 - a]), np.array([1.0, -a])


class _Delay:
    """Линия задержки длиной >= блока, которую можно обрабатывать векторно."""

    def __init__(self, length):
        self.length = length
        self.buf = np.zeros(length, np.float32)


class Reverb:
    """Упрощённый Freeverb (параллельные комбы + последовательные allpass)."""

    COMBS = [1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617]
    ALLPASS = [556, 441, 341, 225]
    SPREAD = 23

    def __init__(self, sr):
        k = sr / 44100.0
        self.combs = [[_Delay(int(d * k)) for d in self.COMBS],
                      [_Delay(int((d + self.SPREAD) * k)) for d in self.COMBS]]
        self.aps = [[_Delay(int(d * k)) for d in self.ALLPASS],
                    [_Delay(int((d + self.SPREAD) * k)) for d in self.ALLPASS]]
        self.chunk = min(d.length for side in self.aps for d in side)
        self.feedback = 0.82
        self.damp_b, self.damp_a = one_pole(5500, sr)
        self.damp_zi = [np.zeros(1), np.zeros(1)]

    def _side(self, x, side):
        out = np.zeros_like(x)
        for c in self.combs[side]:
            n = len(x)
            y = x + self.feedback * c.buf[:n]
            c.buf = np.concatenate((c.buf[n:], y))
            out += y
        for a in self.aps[side]:
            n = len(out)
            delayed = a.buf[:n]
            v = out + 0.5 * delayed
            a.buf = np.concatenate((a.buf[n:], v))
            out = delayed - 0.5 * v
        return out

    def process(self, mono):
        x = mono * 0.015
        res = np.zeros((len(x), 2), np.float32)
        for start in range(0, len(x), self.chunk):
            seg = x[start:start + self.chunk]
            res[start:start + len(seg), 0] = self._side(seg, 0)
            res[start:start + len(seg), 1] = self._side(seg, 1)
        for ch in range(2):
            res[:, ch], self.damp_zi[ch] = lfilter(self.damp_b, self.damp_a, res[:, ch], zi=self.damp_zi[ch])
        return res


class Spatializer:
    """Бинауральное позиционирование: ILD + ITD + тень головы + задние полусферы + дистанция."""

    def __init__(self, sr):
        self.sr = sr
        self.max_itd = 0.00068 * sr
        self.hist_len = int(self.max_itd) + 3
        self.hist = np.zeros(self.hist_len, np.float32)
        self.prev_theta = 0.0
        self.prev_dist = 0.5
        # кроссовер: бас остаётся по центру
        self.xb, self.xa = one_pole(150, sr)
        self.xzi = [np.zeros(1), np.zeros(1)]
        self.sb, self.sa = one_pole(1600, sr)  # тень головы
        self.szi = [np.zeros(1), np.zeros(1)]
        self.rb, self.ra = one_pole(4500, sr)  # звук сзади
        self.rzi = [np.zeros(1), np.zeros(1)]
        self.reverb = Reverb(sr)
        self.eb, self.ea = one_pole(5000, sr)  # высота: «ушная раковина»
        self.ezi = np.zeros(1)
        self.prev_elev = 0.0

    def process(self, block, theta, dist, room, elev=0.0):
        n = len(block)
        mono = block.mean(axis=1).astype(np.float32)

        lo, self.xzi[0] = lfilter(self.xb, self.xa, mono, zi=self.xzi[0])
        lo, self.xzi[1] = lfilter(self.xb, self.xa, lo, zi=self.xzi[1])
        hi = mono - lo

        # высота: сверху — ярче, снизу — глуше
        ev = self.prev_elev + (elev - self.prev_elev) * np.arange(1, n + 1, dtype=np.float32) / n
        self.prev_elev = elev
        dull, self.ezi = lfilter(self.eb, self.ea, hi, zi=self.ezi)
        air = hi - dull
        hi = hi + air * (0.9 * np.maximum(ev, 0)) - air * (0.75 * np.maximum(-ev, 0))
        hi = hi * (1.0 - 0.18 * np.maximum(-ev, 0))
        narrow = np.cos(ev * math.pi / 2 * 0.75)  # над/под головой звук менее «боковой»

        # плавная интерполяция позиции по сэмплам
        dth = (theta - self.prev_theta + math.pi) % (2 * math.pi) - math.pi
        ramp = np.arange(1, n + 1, dtype=np.float32) / n
        th = self.prev_theta + dth * ramp
        d = self.prev_dist + (dist - self.prev_dist) * ramp
        self.prev_theta = (self.prev_theta + dth) % (2 * math.pi)
        self.prev_dist = dist

        p = np.sin(th) * np.clip(d * 1.6, 0.0, 1.0) * narrow  # у самой головы — ближе к центру
        f = np.cos(th)

        # ITD: дальнее ухо слышит позже
        buf = np.concatenate((self.hist, hi))
        base = self.hist_len + np.arange(n)

        def delayed(delay):
            pos = base - delay
            i0 = np.floor(pos).astype(np.int64)
            fr = (pos - i0).astype(np.float32)
            return buf[i0] * (1 - fr) + buf[np.minimum(i0 + 1, len(buf) - 1)] * fr

        left = delayed(np.maximum(p, 0) * self.max_itd)
        right = delayed(np.maximum(-p, 0) * self.max_itd)
        self.hist = buf[-self.hist_len:]

        # ILD (constant power)
        ang = (p * 0.94 + 1.0) * (math.pi / 4)
        gl, gr = np.cos(ang), np.sin(ang)

        # тень головы на дальнем ухе
        shl, shr = np.maximum(p, 0) * 0.85, np.maximum(-p, 0) * 0.85
        lpl, self.szi[0] = lfilter(self.sb, self.sa, left, zi=self.szi[0])
        lpr, self.szi[1] = lfilter(self.sb, self.sa, right, zi=self.szi[1])
        left = left * (1 - shl) + lpl * shl
        right = right * (1 - shr) + lpr * shr

        # сзади — глуше
        rear = np.maximum(-f, 0) * 0.55
        rl, self.rzi[0] = lfilter(self.rb, self.ra, left, zi=self.rzi[0])
        rr, self.rzi[1] = lfilter(self.rb, self.ra, right, zi=self.rzi[1])
        left = left * (1 - rear) + rl * rear
        right = right * (1 - rear) + rr * rear

        dist_gain = 1.25 * (1.0 - 0.4 * d) * (1.0 - 0.12 * rear)
        out = np.empty((n, 2), np.float32)
        out[:, 0] = left * gl * dist_gain + lo
        out[:, 1] = right * gr * dist_gain + lo

        send = room + 0.45 * float(dist) * room + 0.08 * float(dist)
        if send > 0.001:
            out += self.reverb.process(hi) * send
        else:
            self.reverb.process(np.zeros_like(hi))
        return out


class Fifo:
    """Буфер между вводом и выводом: копит запас, не рвёт звук при дрейфе часов."""

    def __init__(self, cap, target):
        self.buf = np.zeros((cap, 2), np.float32)
        self.n = 0
        self.target = target
        self.primed = False
        self.underruns = 0
        self.lock = threading.Lock()

    def push(self, x):
        with self.lock:
            cap = len(self.buf)
            if self.n + len(x) > cap:
                drop = self.n + len(x) - cap
                self.buf[:self.n - drop] = self.buf[drop:self.n]
                self.n -= drop
            self.buf[self.n:self.n + len(x)] = x[-cap:]
            self.n += len(x[-cap:])

    def pop(self, count):
        with self.lock:
            if not self.primed:
                if self.n < self.target + count:
                    return np.zeros((0, 2), np.float32)
                self.primed = True
            if self.n > self.target * 3:  # вход спешит — плавно выкидываем пару сэмплов
                skip = min(self.n - self.target * 2, 16)
                self.buf[:self.n - skip] = self.buf[skip:self.n]
                self.n -= skip
            if self.n < count:  # не хватило — копим заново, вместо рваного звука
                self.primed = False
                self.underruns += 1
                k = self.n
            else:
                k = count
            out = self.buf[:k].copy()
            self.buf[:self.n - k] = self.buf[k:self.n]
            self.n -= k
            if k < count and k > 0:  # плавное затухание в конце куска
                out *= np.linspace(1, 0, k, dtype=np.float32)[:, None]
            return out


class Resampler:
    def __init__(self, sr_in, sr_out):
        self.step = sr_in / sr_out
        self.pos = 0.0
        self.prev = np.zeros((1, 2), np.float32)

    def process(self, x):
        buf = np.vstack((self.prev, x))
        last = len(buf) - 1
        if self.pos >= last:
            self.pos -= len(x)
            self.prev = buf[-1:]
            return np.zeros((0, 2), np.float32)
        count = int(math.floor((last - self.pos) / self.step)) + 1
        idx = self.pos + self.step * np.arange(count)
        idx = idx[idx <= last]
        grid = np.arange(len(buf))
        out = np.stack([np.interp(idx, grid, buf[:, c]) for c in range(2)], axis=1).astype(np.float32)
        self.pos = idx[-1] + self.step - len(x)
        self.prev = buf[-1:]
        return out


PATTERNS = ["Круг", "Восьмёрка", "Маятник", "Спираль"]
SPLITS = ["Один источник", "Два источника: инструменты и верха в разные стороны", "Вокал отдельно (его можно таскать и вращать)"]


class BandSplit:
    """Стерео-фильтр с сохранением состояния между блоками."""

    def __init__(self, sos):
        self.sos = sos
        self.zi = np.zeros((sos.shape[0], 2, 2))

    def __call__(self, x):
        from scipy.signal import sosfilt
        y, self.zi = sosfilt(self.sos, x, axis=0, zi=self.zi)
        return y.astype(np.float32)
EQ_FREQS = [60, 250, 1000, 4000, 12000]


def _peaking(f, gain_db, sr, q=1.0):
    a = 10 ** (gain_db / 40)
    w = 2 * math.pi * f / sr
    alpha = math.sin(w) / (2 * q)
    c = math.cos(w)
    b = [1 + alpha * a, -2 * c, 1 - alpha * a]
    den = [1 + alpha / a, -2 * c, 1 - alpha / a]
    return [x / den[0] for x in b] + [1.0] + [x / den[0] for x in den[1:]]


def _low_shelf(f, gain_db, sr):
    a = 10 ** (gain_db / 40)
    w = 2 * math.pi * f / sr
    c, sn = math.cos(w), math.sin(w)
    alpha = sn / 2 * math.sqrt(2)
    sa = 2 * math.sqrt(a) * alpha
    b = [a * ((a + 1) - (a - 1) * c + sa), 2 * a * ((a - 1) - (a + 1) * c), a * ((a + 1) - (a - 1) * c - sa)]
    den = [(a + 1) + (a - 1) * c + sa, -2 * ((a - 1) + (a + 1) * c), (a + 1) + (a - 1) * c - sa]
    return [x / den[0] for x in b] + [1.0] + [x / den[0] for x in den[1:]]


class Equalizer:
    """5 полос + бас-буст (low shelf 90 Гц)."""

    def __init__(self, sr):
        self.sr = sr
        self.key = None
        self.sos = None
        self.zi = None

    def process(self, x, gains, bass):
        from scipy.signal import sosfilt
        key = (tuple(round(g, 1) for g in gains), round(bass, 1))
        if all(g == 0 for g in key[0]) and key[1] == 0:
            self.key = None
            return x
        if key != self.key:
            sos = [_peaking(f, g, self.sr) for f, g in zip(EQ_FREQS, key[0]) if g]
            if key[1]:
                sos.append(_low_shelf(90, key[1], self.sr))
            sos = np.array(sos)
            if self.zi is None or self.zi.shape[0] != len(sos):
                self.zi = np.zeros((len(sos), 2, 2))
            self.sos, self.key = sos, key
        y, self.zi = sosfilt(self.sos, x, axis=0, zi=self.zi)
        # чтобы буст не перегружал: мягкая компенсация
        boost = max([0.0] + list(key[0]) + [key[1]])
        return (y * 10 ** (-boost * 0.6 / 20)).astype(np.float32)


class Engine:
    BLOCK = 1024

    def __init__(self):
        self.mode_8d = True
        self.auto = True
        self.pattern = 0
        self.speed = 0.12      # оборотов в секунду
        self.distance = 0.75   # 0..1
        self.room = 0.25       # 0..1
        self.volume = 0.9
        self.elevation = 0.0   # -1 (снизу) .. 1 (сверху)
        self.elev_wobble = 0.0  # 0..1 качание по высоте в авто-режиме
        self.eq = [0.0] * 5    # дБ
        self.bass = 0.0        # дБ
        self.buffer_ms = 50    # запас буфера
        self.vocal_xy = (0.0, 0.25)  # где стоит голос в режиме «Вокал»
        self.vocal_auto = False      # вокал вращается сам
        self.vocal_speed = -0.1      # об/с, минус — в обратную сторону
        self.split = 0         # см. SPLITS
        self.rate = 1.0        # скорость трека (slowed)
        self.pos_z = 0.0
        self.manual_xy = (0.0, 0.75)  # x вправо, y вперёд
        self.pos_xy = (0.0, 0.75)
        self.phase = 0.0
        self.mix = 1.0
        self.level = 0.0
        self.in_level = 0.0
        self.source = "system"  # system | file
        self.track = None       # np.ndarray (N, 2) на частоте вывода
        self.track_name = ""
        self.track_pos = 0.0
        self.track_sr = 48000
        self.playing = False
        self.loop = True
        self.scope = np.zeros(2048, np.float32)
        self.running = False
        self.error = ""
        self._in = self._out = None

    def _init_split(self, sr):
        from scipy.signal import butter
        self.spat2 = Spatializer(sr)
        self.hp_split = BandSplit(butter(2, 3500, "highpass", fs=sr, output="sos"))
        self.voc_split = BandSplit(butter(2, [280, 3800], "bandpass", fs=sr, output="sos"))

    def block(self):
        return 256 if self.buffer_ms <= 25 else 512 if self.buffer_ms <= 60 else 1024

    # ---------- устройства ----------
    @staticmethod
    def wasapi_devices():
        apis = sd.query_hostapis()
        idx = next((i for i, a in enumerate(apis) if "WASAPI" in a["name"]), None)
        ins, outs = [], []
        for i, d in enumerate(sd.query_devices()):
            if idx is not None and d["hostapi"] != idx:
                continue
            if d["max_input_channels"] > 0:
                ins.append((i, d["name"]))
            if d["max_output_channels"] > 0:
                outs.append((i, d["name"]))
        default_out = apis[idx]["default_output_device"] if idx is not None else -1
        return ins, outs, default_out

    # ---------- движение ----------
    def _advance(self, n, sr):
        if not self.auto:
            x, y = self.manual_xy
        else:
            self.phase = (self.phase + self.speed * n / sr) % 1.0
            a = 2 * math.pi * self.phase
            r = self.distance
            if self.pattern == 0:
                x, y = math.sin(a) * r, math.cos(a) * r
            elif self.pattern == 1:
                x, y = math.sin(a) * r, math.sin(2 * a) * r * 0.55
            elif self.pattern == 2:
                x, y = math.sin(a) * r, 0.35 * r + 0.15 * abs(math.cos(a)) * r
            else:
                rr = r * (0.35 + 0.65 * (0.5 + 0.5 * math.sin(a * 0.25)))
                x, y = math.sin(a * 2) * rr, math.cos(a * 2) * rr
        if self.vocal_auto and self.split == 2:
            vx, vy = self.vocal_xy
            r = max(0.15, math.hypot(vx, vy))
            a = math.atan2(vx, vy) + 2 * math.pi * self.vocal_speed * n / sr
            self.vocal_xy = (math.sin(a) * r, math.cos(a) * r)
        z = self.elevation
        if self.auto and self.elev_wobble:
            z += self.elev_wobble * math.sin(2 * math.pi * self.phase * 3)
        z = max(-1.0, min(1.0, z))
        self.pos_xy = (x, y)
        self.pos_z = z
        dist = min(1.0, math.hypot(x, y))
        theta = math.atan2(x, y)
        return theta, dist, z

    # ---------- поток ----------
    def start(self, in_dev, out_dev):
        self.stop()
        self.error = ""
        try:
            din, dout = sd.query_devices(in_dev), sd.query_devices(out_dev)
            sr_in, sr_out = int(din["default_samplerate"]), int(dout["default_samplerate"])
            ch_in = min(2, din["max_input_channels"])
            self.spat = Spatializer(sr_in)
            self._init_split(sr_in)
            self.equalizer = Equalizer(sr_in)
            self.resampler = Resampler(sr_in, sr_out) if sr_in != sr_out else None
            self.fifo = Fifo(sr_out * 4, int(sr_out * self.buffer_ms / 1000))
            self.sr = sr_in

            def in_cb(indata, frames, t, status):
                block = indata if ch_in == 2 else np.repeat(indata, 2, axis=1)
                self.in_level = self.in_level * 0.8 + 0.2 * float(np.sqrt(np.mean(block ** 2)))
                out = self.process(block.astype(np.float32), sr_in)
                if self.resampler:
                    out = self.resampler.process(out)
                self.fifo.push(out)

            def out_cb(outdata, frames, t, status):
                data = self.fifo.pop(frames)
                outdata[:len(data)] = data
                outdata[len(data):] = 0

            self._in = sd.InputStream(device=in_dev, channels=ch_in, samplerate=sr_in,
                                      blocksize=self.block(), dtype="float32", latency="high", callback=in_cb)
            self._out = sd.OutputStream(device=out_dev, channels=2, samplerate=sr_out,
                                        blocksize=self.block(), dtype="float32", latency="high", callback=out_cb)
            self._out.start()
            self._in.start()
            self.running = True
        except Exception as e:  # noqa: BLE001
            self.error = str(e)
            self.stop()
        return self.running

    def load_track(self, data, sr, name):
        """data: (N, ch) float32. Переводим в стерео на частоте 48 кГц."""
        if data.ndim == 1:
            data = data[:, None]
        data = data[:, :2] if data.shape[1] >= 2 else np.repeat(data, 2, axis=1)
        if sr != 48000:
            from math import gcd
            from scipy.signal import resample_poly
            g = gcd(int(sr), 48000)
            data = resample_poly(data, 48000 // g, int(sr) // g, axis=0)
        self.track = np.ascontiguousarray(data, dtype=np.float32)
        self.track_name = name
        self.track_pos = 0
        self.track_sr = 48000

    def start_file(self, out_dev):
        self.stop()
        self.error = ""
        try:
            sr = self.track_sr
            self.spat = Spatializer(sr)
            self._init_split(sr)
            self.equalizer = Equalizer(sr)

            def out_cb(outdata, frames, t, status):
                block = np.zeros((frames, 2), np.float32)
                tr = self.track
                if self.playing and tr is not None:
                    # slowed: читаем медленнее с интерполяцией (тон тоже ниже — как в slowed-треках)
                    pos = self.track_pos + self.rate * np.arange(frames)
                    valid = pos < len(tr) - 1
                    pv = pos[valid]
                    i0 = pv.astype(np.int64)
                    fr = (pv - i0)[:, None].astype(np.float32)
                    block[:len(pv)] = tr[i0] * (1 - fr) + tr[i0 + 1] * fr
                    self.track_pos += self.rate * frames
                    if self.track_pos >= len(tr) - 1:
                        self.track_pos = 0.0
                        if not self.loop:
                            self.playing = False
                self.in_level = self.in_level * 0.8 + 0.2 * float(np.sqrt(np.mean(block ** 2)))
                outdata[:] = self.process(block, sr)

            self._out = sd.OutputStream(device=out_dev, channels=2, samplerate=sr,
                                        blocksize=self.block(), dtype="float32",
                                        latency=max(0.1, self.buffer_ms / 1000), callback=out_cb)
            self._out.start()
            self.running = True
        except Exception as e:  # noqa: BLE001
            self.error = str(e)
            self.stop()
        return self.running

    def stop(self):
        for s in (self._in, self._out):
            if s is not None:
                try:
                    s.stop()
                    s.close()
                except Exception:  # noqa: BLE001
                    pass
        self._in = self._out = None
        self.running = False

    def process(self, block, sr):
        n = len(block)
        theta, dist, elev = self._advance(n, sr)
        room = self.room * 0.9
        if self.split == 1:  # верха летят с противоположной стороны
            top = self.hp_split(block)
            wet = self.spat.process(block - top, theta, dist, room, elev)
            wet += self.spat2.process(top, theta + math.pi, dist, room * 0.3, -elev)
        elif self.split == 2:  # голос спереди по центру, остальное кружит
            mid = block.mean(axis=1, keepdims=True)
            voc = self.voc_split(np.repeat(mid, 2, axis=1)) * 0.85
            wet = self.spat.process(block - voc, theta, dist, room, elev)
            vx, vy = self.vocal_xy
            wet += self.spat2.process(voc, math.atan2(vx, vy), min(1.0, math.hypot(vx, vy)), room * 0.5, 0.0)
        else:
            wet = self.spat.process(block, theta, dist, room, elev)
        target = 1.0 if self.mode_8d else 0.0
        ramp = np.linspace(self.mix, target, n, dtype=np.float32)[:, None]
        self.mix = target
        out = (wet * ramp + block * (1 - ramp)) * self.volume
        out = self.equalizer.process(out, self.eq, self.bass)
        a = np.abs(out)
        out = np.where(a < 0.85, out, np.sign(out) * (0.85 + 0.15 * np.tanh((a - 0.85) / 0.15)))
        mono = out.mean(axis=1)
        self.scope = np.concatenate((self.scope[n:], mono))
        self.level = self.level * 0.8 + 0.2 * float(np.sqrt(np.mean(mono ** 2)))
        return out.astype(np.float32)


def demo_track(sr=48000, seconds=16):
    """Синтезированный луп для проверки 8D: бочка, хэт, арпеджио, бас."""
    t = np.arange(int(sr * seconds)) / sr
    out = np.zeros_like(t)
    bpm = 110
    beat = 60 / bpm
    notes = [57, 60, 64, 69, 67, 64, 60, 64]
    bass = [45, 45, 41, 43]
    step = beat / 2
    for i in range(int(seconds / step)):
        st = int(i * step * sr)
        seg = t[: int(step * sr)]
        f = 440 * 2 ** ((notes[i % 8] - 69) / 12)
        tone = (np.sin(2 * np.pi * f * seg) + 0.3 * np.sin(4 * np.pi * f * seg)) * np.exp(-seg * 5)
        out[st:st + len(seg)] += 0.22 * tone[: len(out) - st]
        hat = np.random.randn(len(seg)) * np.exp(-seg * 60) * 0.06
        out[st:st + len(seg)] += hat[: len(out) - st]
    for i in range(int(seconds / beat)):
        st = int(i * beat * sr)
        seg = t[: int(beat * sr)]
        kick = np.sin(2 * np.pi * (50 + 90 * np.exp(-seg * 30)) * seg) * np.exp(-seg * 9) * 0.5
        fb = 440 * 2 ** ((bass[(i // 4) % 4] - 69) / 12)
        b = np.sin(2 * np.pi * fb * seg) * 0.18 * (1 - np.exp(-seg * 80))
        out[st:st + len(seg)] += (kick + b)[: len(out) - st]
    out /= np.abs(out).max() * 1.4
    return np.stack([out, out], axis=1).astype(np.float32)
