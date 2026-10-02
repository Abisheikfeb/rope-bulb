# =====================================================================
#  ROPE BULB - SETTINGS.  Change anything, save, then restart:
#      pkill -f rope_bulb.py ; setsid nohup python ~/rope-bulb/rope_bulb.py >/dev/null 2>&1 &
#  (or right-click the bulb -> "Reload config")
# =====================================================================

# ------------------------------ BULB ---------------------------------
BULB_SCALE = 1.4                    # bulb size (1.0 = small, 2.0 = big)
GLASS_TINT = (255, 244, 220)        # colour of the glass when OFF
BRASS_COLOR = (176, 132, 62)        # metal socket colour
FILAMENT_COLOR = (255, 214, 140)    # wire colour when lit

# ------------------------------ GLOW ---------------------------------
GLOW_COLOR = (255, 186, 82)         # warm yellow-orange (try (255,120,60) for red, (150,200,255) for cool)
GLOW_RADIUS = 170                   # how far the light spreads (px)
GLOW_STRENGTH = 1.0                 # 0.3 = soft ... 2.0 = very bright
GLOW_PULSE = 0.04                   # slow breathing of the light (0 = off)
SHIMMER = 0.03                      # fast filament shimmer (0 = off)
WARMUP_SPEED = 0.10                 # how fast it lights up (0.02 slow ... 0.5 instant)
COOLDOWN_SPEED = 0.05               # how fast it fades out
FLICKER_ON_START = True             # old bulb flicker when switching on
FLICKER_SECONDS = 0.8

# ----------------------------- ACTIONS -------------------------------
LIGHT_ON_COMMAND = ["code"]         # runs when the light turns ON (VS Code). None = nothing
LIGHT_OFF_COMMAND = None            # runs when the light turns OFF. Example: ["notify-send", "Light off"]
LAUNCH_COOLDOWN = 3.0               # seconds before the ON command can run again
AUTO_OFF_SECONDS = 0                # light switches itself off after N seconds (0 = stays on)

# ------------------------------ ROPE ---------------------------------
ROPE_LENGTH = 160                   # total rope length (px)
ROPE_SEGMENTS = "auto"              # "auto" or a number (more = smoother)
ROPE_THICKNESS = 5.5
ROPE_COLOR = (88, 60, 36)
ROPE_TWIST_COLOR = (172, 136, 92)   # twisted-fibre look, None = plain rope
SHOW_MOUNT = True                   # small plate where the rope is fixed
MOUNT_COLOR = (45, 45, 52)
MOUNT_WIDTH = 28

# ----------------------------- POSITION ------------------------------
ANCHOR_CORNER = "top-right"         # "top-right", "top-left" or "top-center"
ANCHOR_OFFSET_X = 150               # px from that corner (top-center: + right, - left)
ANCHOR_OFFSET_Y = 0                 # px down from the top of the screen

# ----------------------------- MOVEMENT ------------------------------
GRAVITY = 0.55
BULB_WEIGHT = 2.0                   # heavier = hangs straighter
DAMPING = 0.992                     # closer to 1.0 = swings longer (max 0.999)
STIFFNESS = 14                      # rope stiffness (8-20)
ANGLE_SMOOTHING = 0.25              # bulb tilt follow speed (low = floaty)
MOUSE_PUSH_RADIUS = 22              # how close the mouse must be to push the rope
MOUSE_PUSH_STRENGTH = 0.4
BULB_PUSH_STRENGTH = 0.5
FPS = 60

# ------------------------------ WINDOW -------------------------------
SWING_SPACE = "auto"                # room each side of the rope in px ("auto" or number)
