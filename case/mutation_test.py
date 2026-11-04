"""Mutation test di check_fit: ogni difetto introdotto apposta deve far fallire i controlli.

    python case/mutation_test.py      # ogni riga deve dire OK; MISS = check_fit non se ne accorge

Lancialo dopo aver cambiato check_fit.py o le quote in build_case.py.
"""
import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_case as b  # noqa: E402
import check_fit  # noqa: E402

orig_tray = b.build_tray


def run(label, patch, undo):
    patch()
    check_fit.failures.clear()
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = check_fit.main()
    except AssertionError as e:
        rc, check_fit.failures[:] = 1, [f"assert del generatore: {e}"]
    finally:
        undo()
    print(f"{'OK  ' if rc == 1 else 'MISS'} {label}: rc={rc}, {len(check_fit.failures)} fallimenti"
          + (f" -> {check_fit.failures[0][:70]}" if check_fit.failures else ""))


def no_posts():
    def t():
        m = orig_tray()
        for u, v in b.BUTTONS.values():
            x, y = b.ctrl(u, v)
            m -= b.box(x - 6, y - 6, b.FLOOR + 1, x + 6, y + 6, 40)
        return m
    b.build_tray = t


saved = {}


def setp(**kw):
    def f():
        for k, v in kw.items():
            saved[k] = getattr(b, k)
            setattr(b, k, v)
    return f


def restore():
    for k, v in saved.items():
        setattr(b, k, v)
    saved.clear()
    b.build_tray = orig_tray


run("niente piedistalli switch", no_posts, restore)
run("NUB_GAP = 0", setp(NUB_GAP=0.0), restore)
run("NUB_GAP = 0.9", setp(NUB_GAP=0.9), restore)
run("BAFFLE_FOOT = 4", setp(BAFFLE_FOOT=4.0), restore)
old_m = [(b.T + 3.5, b.T + 3.5), (b.T + 3.5, b.D - b.T - 3.5), (b.X_STEP - 3.5, b.T + 3.5), (b.X_STEP - 3.5, b.D - b.T - 3.5)]
run("colonne diffusore al bordo (vecchie)", setp(SCREWS_M=old_m), restore)
run("JACK_Z = 9", setp(JACK_Z=9.0), restore)
run("HP_R = 3 (apertura cuffie bassa)", setp(HP_R=3.0), restore)
run("TEENSY_X = CX0 + 20", setp(TEENSY_X=b.CX0 + 20), restore)
run("stack 11 mm più alto, case no", setp(STACK_GAP=b.STACK_GAP + 11, Z_AUDIO=b.Z_AUDIO + 11, HP_Z=b.HP_Z + 11), restore)
run("jack LINE IN lungo 30 mm (entra sulla scheda audio)", setp(JACK_DEPTH=30.0), restore)
run("zona comandi alta come il prototipo (19)", setp(Z_WALL_C=19.0, Z_TOP_C=21.5), restore)
run("pin del Teensy 4 mm più lunghi", setp(HDR_PIN_UP=b.HDR_PIN_UP + 4), restore)
run("jack LINE IN tondo Ø26", setp(JACK_BODY_H=27.0), restore)
