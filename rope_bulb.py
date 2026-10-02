#!/usr/bin/env python3
"""Old-style glowing bulb on a rope for the corner of your desktop.
Pull / click the bulb -> light turns on and VS Code opens. Settings: config.py

Nothing else on your screen is blocked: the picture window ignores the mouse,
only a tiny invisible hit-box that follows the bulb receives clicks."""
import math
import os
import random
import shlex
import shutil
import subprocess
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "xcb")     # also works on Wayland sessions

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QRadialGradient,
                         QLinearGradient, QPainterPath)
from PyQt6.QtWidgets import QApplication, QWidget, QMenu

import config


def cfg(name, default):
    return getattr(config, name, default)


BULB_SCALE = cfg("BULB_SCALE", 1.4)
GLASS_TINT = cfg("GLASS_TINT", (255, 244, 220))
BRASS = cfg("BRASS_COLOR", (176, 132, 62))
FILAMENT = cfg("FILAMENT_COLOR", (255, 214, 140))
GLOW_COLOR = cfg("GLOW_COLOR", (255, 186, 82))
GLOW_RADIUS = cfg("GLOW_RADIUS", 170)
GLOW_STRENGTH = cfg("GLOW_STRENGTH", 1.0)
GLOW_PULSE = cfg("GLOW_PULSE", 0.04)
SHIMMER = cfg("SHIMMER", 0.03)
WARMUP = cfg("WARMUP_SPEED", 0.10)
COOLDOWN = cfg("COOLDOWN_SPEED", 0.05)
FLICKER = cfg("FLICKER_ON_START", True)
FLICKER_SECS = cfg("FLICKER_SECONDS", 0.8)
ON_CMD = cfg("LIGHT_ON_COMMAND", ["code"])
OFF_CMD = cfg("LIGHT_OFF_COMMAND", None)
LAUNCH_COOLDOWN = cfg("LAUNCH_COOLDOWN", 3.0)
AUTO_OFF = cfg("AUTO_OFF_SECONDS", 0)
ROPE_LENGTH = cfg("ROPE_LENGTH", 150)
ROPE_SEGMENTS = cfg("ROPE_SEGMENTS", "auto")
ROPE_THICK = cfg("ROPE_THICKNESS", 4.5)
ROPE_COLOR = cfg("ROPE_COLOR", (88, 60, 36))
ROPE_TWIST = cfg("ROPE_TWIST_COLOR", (172, 136, 92))
SHOW_MOUNT = cfg("SHOW_MOUNT", True)
MOUNT_COLOR = cfg("MOUNT_COLOR", (45, 45, 52))
MOUNT_W = cfg("MOUNT_WIDTH", 28)
CORNER = cfg("ANCHOR_CORNER", "top-right")
OFF_X = cfg("ANCHOR_OFFSET_X", 150)
OFF_Y = cfg("ANCHOR_OFFSET_Y", 0)
GRAVITY = cfg("GRAVITY", 0.55)
WEIGHT = cfg("BULB_WEIGHT", 2.0)
DAMPING = cfg("DAMPING", 0.992)
STIFF = int(cfg("STIFFNESS", 14))
ANG_SMOOTH = cfg("ANGLE_SMOOTHING", 0.25)
PUSH_R = cfg("MOUSE_PUSH_RADIUS", 22)
PUSH_ROPE = cfg("MOUSE_PUSH_STRENGTH", 0.4)
PUSH_BULB = cfg("BULB_PUSH_STRENGTH", 0.5)
FPS = cfg("FPS", 60)
SWING_SPACE = cfg("SWING_SPACE", "auto")

S = BULB_SCALE
GLASS_CENTER = 42 * S          # distance from rope end to middle of the glass
BULB_LEN = 62 * S
ANCHOR_LOCAL_Y = 6


# ------------------------------ helpers ------------------------------
def run_command(cmd):
    if not cmd:
        return
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    cmd = list(cmd)
    if cmd[0] == "code" and not shutil.which("code"):
        for alt in ("code-oss", "vscodium", "codium", "visual-studio-code"):
            if shutil.which(alt):
                cmd[0] = alt
                break
    path = shutil.which(cmd[0])
    if not path:
        print(f"Command not found: {cmd[0]}   "
              "(install VS Code: yay -S visual-studio-code-bin  or  sudo pacman -S code)")
        return
    subprocess.Popen([path] + cmd[1:], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t, alpha=255):
    return QColor(int(lerp(c1[0], c2[0], t)), int(lerp(c1[1], c2[1], t)),
                  int(lerp(c1[2], c2[2], t)), int(max(0, min(255, alpha))))


def radial(cx, cy, radius, rgb, alpha, power=2.2, steps=12):
    g = QRadialGradient(QPointF(cx, cy), radius)
    for k in range(steps + 1):
        t = k / steps
        a = max(0, min(255, alpha * (1 - t) ** power))
        g.setColorAt(t, QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]), int(a)))
    return g


def single_instance():
    import fcntl
    path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "rope-bulb.lock")
    f = open(path, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("Rope Bulb is already running.")
    return f


class Node:
    __slots__ = ("x", "y", "px", "py")

    def __init__(self, x, y):
        self.x = self.px = x
        self.y = self.py = y


# --------------------- tiny invisible window on the bulb ---------------------
class HitBox(QWidget):
    """Only this small window receives the mouse. It follows the bulb."""

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.WindowDoesNotAcceptFocus |
                            Qt.WindowType.X11BypassWindowManagerHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.size_px = int(76 * S)
        self.setFixedSize(self.size_px, self.size_px)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def paintEvent(self, _):
        QPainter(self).fillRect(self.rect(), QColor(0, 0, 0, 1))   # invisible

    def mousePressEvent(self, e):
        self.owner.hit_press(e)

    def mouseMoveEvent(self, e):
        self.owner.hit_move(e)

    def mouseReleaseEvent(self, e):
        self.owner.hit_release(e)

    def leaveEvent(self, _):
        self.owner.last_mouse = None


# ------------------------------ main window ------------------------------
class RopeBulb(QWidget):
    def __init__(self, anchor_x, win_w, win_h):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.WindowTransparentForInput |
                            Qt.WindowType.X11BypassWindowManagerHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.W, self.H = win_w, win_h
        self.setFixedSize(win_w, win_h)
        self.origin = (0, 0)

        self.ax, self.ay = anchor_x, ANCHOR_LOCAL_Y
        count = (max(4, round(ROPE_LENGTH / 13))
                 if ROPE_SEGMENTS == "auto" else int(ROPE_SEGMENTS))
        self.seg_len = ROPE_LENGTH / count
        self.nodes = [Node(self.ax + (i / count) ** 2 * 40,
                           self.ay + i * self.seg_len) for i in range(count + 1)]
        self.angle = 0.0
        self.on = False
        self.brightness = 0.0
        self.flicker_until = 0.0
        self.on_since = 0.0
        self.last_launch = 0.0
        self.dragging = False
        self.grab_off = (0.0, 0.0)
        self.drag_target = (self.ax, self.ay)
        self.last_mouse = None
        self.frame = 0

        self.hit = HitBox(self)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(max(1, int(1000 / FPS)))

    # ---- light ----
    def set_light(self, state):
        if state == self.on:
            return
        self.on = state
        now = time.time()
        if state:
            self.on_since = now
            if FLICKER:
                self.flicker_until = now + FLICKER_SECS
            if now - self.last_launch > LAUNCH_COOLDOWN:
                self.last_launch = now
                run_command(ON_CMD)
        else:
            run_command(OFF_CMD)

    def toggle(self):
        self.set_light(not self.on)

    # ---- physics ----
    def pinned(self, i):
        return i == 0 or (self.dragging and i == len(self.nodes) - 1)

    def step(self):
        nodes, last = self.nodes, len(self.nodes) - 1
        for i, n in enumerate(nodes):
            if i == 0:
                n.x, n.y = self.ax, self.ay
                n.px, n.py = n.x, n.y
                continue
            if self.dragging and i == last:
                sx, sy = self.drag_target[0] - n.x, self.drag_target[1] - n.y
                d = math.hypot(sx, sy)
                if d > 30:
                    sx, sy = sx / d * 30, sy / d * 30
                n.px, n.py = n.x, n.y
                n.x += sx
                n.y += sy
                continue
            vx, vy = (n.x - n.px) * DAMPING, (n.y - n.py) * DAMPING
            n.px, n.py = n.x, n.y
            n.x += vx
            n.y += vy + GRAVITY * (WEIGHT if i == last else 1.0)
            if i == last:
                mx = 30 * S
                n.x = min(max(n.x, mx), self.W - mx)
                n.y = min(n.y, self.H - BULB_LEN - 4)
            else:
                n.x = min(max(n.x, 6), self.W - 6)
                n.y = min(max(n.y, 0), self.H - 6)
        for _ in range(STIFF):
            for i in range(last):
                a, b = nodes[i], nodes[i + 1]
                dx, dy = b.x - a.x, b.y - a.y
                d = math.hypot(dx, dy) or 1e-6
                diff = (d - self.seg_len) / d
                wa = 0 if self.pinned(i) else 1
                wb = 0 if self.pinned(i + 1) else 1
                if wa + wb == 0:
                    continue
                a.x += dx * diff * wa / (wa + wb)
                a.y += dy * diff * wa / (wa + wb)
                b.x -= dx * diff * wb / (wa + wb)
                b.y -= dy * diff * wb / (wa + wb)

    def tick(self):
        self.step()
        a, b = self.nodes[max(0, len(self.nodes) - 3)], self.nodes[-1]
        target = math.degrees(math.atan2(-(b.x - a.x), b.y - a.y))
        self.angle += ((target - self.angle + 180) % 360 - 180) * ANG_SMOOTH

        now = time.time()
        if self.on and AUTO_OFF and now - self.on_since > AUTO_OFF:
            self.set_light(False)
        goal = 1.0 if self.on else 0.0
        if self.on and now < self.flicker_until:
            goal = random.uniform(0.25, 1.0)
        rate = WARMUP if goal > self.brightness else COOLDOWN
        self.brightness += (goal - self.brightness) * rate

        # hit-box follows the bulb
        cx, cy = self.bulb_center()
        hs = self.hit.size_px
        self.hit.move(int(self.origin[0] + cx - hs / 2),
                      int(self.origin[1] + cy - hs / 2))
        self.frame += 1
        if self.frame % 90 == 0:
            self.raise_()
            self.hit.raise_()
        self.update()

    def bulb_dir(self):
        a, b = self.nodes[-2], self.nodes[-1]
        dx, dy = b.x - a.x, b.y - a.y
        d = math.hypot(dx, dy) or 1.0
        return dx / d, dy / d

    def bulb_center(self):
        # direction follows the smoothed angle so hit-box matches the drawing
        a = math.radians(self.angle)
        n = self.nodes[-1]
        return n.x - math.sin(a) * GLASS_CENTER, n.y + math.cos(a) * GLASS_CENTER

    def clamp_reach(self, x, y):
        reach = ROPE_LENGTH * 0.98
        dx, dy = x - self.ax, y - self.ay
        d = math.hypot(dx, dy)
        if d > reach:
            x, y = self.ax + dx / d * reach, self.ay + dy / d * reach
        return x, y

    # ---- mouse (arrives from the small hit-box only) ----
    def local(self, e):
        p = e.globalPosition()
        return p.x() - self.origin[0], p.y() - self.origin[1]

    def reload_config(self):
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def hit_press(self, e):
        x, y = self.local(e)
        if e.button() == Qt.MouseButton.RightButton:
            menu = QMenu()
            menu.addAction("Light on / off", self.toggle)
            menu.addAction("Reload config", self.reload_config)
            menu.addSeparator()
            menu.addAction("Quit", QApplication.quit)
            menu.exec(e.globalPosition().toPoint())
            return
        if e.button() == Qt.MouseButton.LeftButton:
            n = self.nodes[-1]
            self.grab_off = (n.x - x, n.y - y)
            self.drag_target = (n.x, n.y)
            self.dragging = True
            self.hit.setCursor(Qt.CursorShape.ClosedHandCursor)

    def hit_move(self, e):
        x, y = self.local(e)
        if self.dragging:
            self.drag_target = self.clamp_reach(x + self.grab_off[0],
                                                y + self.grab_off[1])
        elif self.last_mouse is not None:
            vx = max(-25, min(25, x - self.last_mouse[0]))
            vy = max(-25, min(25, y - self.last_mouse[1]))
            for nd in self.nodes[1:-1]:
                if math.hypot(nd.x - x, nd.y - y) < PUSH_R:
                    nd.x += vx * PUSH_ROPE
                    nd.y += vy * PUSH_ROPE
            self.nodes[-1].x += vx * PUSH_BULB
            self.nodes[-1].y += vy * PUSH_BULB
        self.last_mouse = (x, y)

    def hit_release(self, e):
        if self.dragging and e.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.hit.setCursor(Qt.CursorShape.OpenHandCursor)
            self.toggle()          # pull and let go -> light switches

    # ---- drawing ----
    def level(self):
        b = self.brightness
        if self.on and b > 0.3:
            t = time.time()
            b *= 1 + SHIMMER * math.sin(t * 41) + GLOW_PULSE * math.sin(t * 2.1)
        return max(0.0, b)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        b = self.level()
        t = min(1.0, b)

        if SHOW_MOUNT:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(*MOUNT_COLOR))
            p.drawRoundedRect(QRectF(self.ax - MOUNT_W / 2, 0, MOUNT_W, 8), 3, 3)

        path = QPainterPath(QPointF(self.nodes[0].x, self.nodes[0].y))
        for nd in self.nodes[1:]:
            path.lineTo(nd.x, nd.y)
        p.setBrush(Qt.BrushStyle.NoBrush)
        core = QPen(QColor(*ROPE_COLOR), ROPE_THICK)
        core.setCapStyle(Qt.PenCapStyle.RoundCap)
        core.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(core)
        p.drawPath(path)
        if ROPE_TWIST:
            tw = QPen(QColor(*ROPE_TWIST), ROPE_THICK)
            tw.setDashPattern([0.7, 1.6])
            p.setPen(tw)
            p.drawPath(path)

        cx, cy = self.bulb_center()
        # colour shifts from deep orange (cold) to full glow colour (hot)
        hot = (GLOW_COLOR[0], GLOW_COLOR[1] * 0.55, GLOW_COLOR[2] * 0.35)
        rgb = tuple(lerp(hot[i], GLOW_COLOR[i], t) for i in range(3))
        if b > 0.005:                       # light spreading on the rope + around
            st = GLOW_STRENGTH * min(b, 1.3)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(radial(cx, cy, GLOW_RADIUS, rgb, 150 * st, 2.4)))
            p.drawEllipse(QPointF(cx, cy), GLOW_RADIUS, GLOW_RADIUS)
            r2 = GLOW_RADIUS * 0.42
            p.setBrush(QBrush(radial(cx, cy, r2, (255, 226, 165), 150 * st, 2.0)))
            p.drawEllipse(QPointF(cx, cy), r2, r2)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        n = self.nodes[-1]
        p.save()
        p.translate(n.x, n.y)
        p.rotate(self.angle)
        p.scale(S, S)
        self.draw_bulb(p, t, rgb)
        p.restore()

        if b > 0.005:                       # bloom washing over the hot glass
            st = min(b, 1.3)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(radial(cx, cy, 34 * S, (255, 244, 215), 190 * st, 1.6)))
            p.drawEllipse(QPointF(cx, cy), 34 * S, 34 * S)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

    def draw_bulb(self, p, t, rgb):
        # brass socket
        dark = tuple(c * 0.45 for c in BRASS)
        light = tuple(min(255, c * 1.35 + 20) for c in BRASS)
        sg = QLinearGradient(-8, 0, 8, 0)
        sg.setColorAt(0.0, QColor(*[int(c) for c in dark]))
        sg.setColorAt(0.35, QColor(*[int(c) for c in light]))
        sg.setColorAt(1.0, QColor(*[int(c * 0.6) for c in BRASS]))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(55, 55, 60))
        p.drawRoundedRect(QRectF(-4, -4, 8, 5), 1.5, 1.5)
        p.setBrush(QBrush(sg))
        p.drawRoundedRect(QRectF(-8, 0, 16, 17), 2.5, 2.5)
        p.setPen(QPen(QColor(40, 30, 15, 170), 0.9))
        for y in (4, 8, 12):
            p.drawLine(QPointF(-8, y), QPointF(8, y + 1.5))

        # glass
        glass = QPainterPath()
        glass.addEllipse(QPointF(0, 42), 19, 20)
        neck = QPainterPath()
        neck.moveTo(-7, 16)
        neck.lineTo(7, 16)
        neck.lineTo(14, 32)
        neck.lineTo(-14, 32)
        neck.closeSubpath()
        glass = glass.united(neck)
        off_c = GLASS_TINT
        rg = QRadialGradient(QPointF(0, 38), 26)
        rg.setColorAt(0.0, mix(off_c, (255, 250, 228), t, 70 + 185 * t))
        rg.setColorAt(0.65, mix(off_c, rgb, t, 85 + 140 * t))
        rg.setColorAt(1.0, mix((165, 178, 192), rgb, t, 115 + 115 * t))
        p.setBrush(QBrush(rg))
        p.setPen(QPen(QColor(215, 225, 235, 150), 1.1))
        p.drawPath(glass)

        # filament (hairpin coil on two posts)
        p.setPen(QPen(QColor(110, 110, 116), 1))
        p.drawLine(QPointF(-5, 16), QPointF(-5, 32))
        p.drawLine(QPointF(5, 16), QPointF(5, 32))
        fil = QPainterPath(QPointF(-5, 32))
        for x, y in ((-3.5, 39), (-2, 32), (-0.5, 39), (1, 32), (2.5, 39), (4, 32), (5, 32)):
            fil.lineTo(x, y)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(mix((78, 66, 60), FILAMENT, t), 1.3 + 1.6 * t))
        p.drawPath(fil)
        if t > 0.02:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(radial(0, 35, 13, (255, 235, 180), 230 * t, 1.5)))
            p.drawEllipse(QPointF(0, 35), 13, 13)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        # glass highlights
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 120), 2))
        p.drawArc(QRectF(-14, 28, 28, 28), 110 * 16, 55 * 16)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 150))
        p.drawEllipse(QPointF(-9.5, 36), 1.6, 2.6)


def main():
    lock = single_instance()             # only one copy can run
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    reach = ROPE_LENGTH + BULB_LEN
    space = (reach * 0.8 + GLOW_RADIUS * 0.3 if SWING_SPACE == "auto"
             else float(SWING_SPACE))
    W, H = int(space * 2), int(reach + GLOW_RADIUS * 0.8 + 20)

    geo = app.primaryScreen().availableGeometry()
    if CORNER == "top-left":
        ax = geo.left() + OFF_X
    elif CORNER == "top-center":
        ax = geo.center().x() + OFF_X
    else:
        ax = geo.right() + 1 - OFF_X
    win_x = int(min(max(ax - W // 2, geo.left()), geo.right() + 1 - W))
    win_y = geo.top() + OFF_Y

    win = RopeBulb(ax - win_x, W, H)
    win.origin = (win_x, win_y)
    win.move(win_x, win_y)
    win.show()
    win.hit.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
