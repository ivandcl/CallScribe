import logging
import threading
import webbrowser

import pystray
from PIL import Image, ImageDraw

import config

logger = logging.getLogger(__name__)

ICON_SIZE = 64


def _create_icon_image(color: str) -> Image.Image:
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 8
    draw.ellipse(
        [margin, margin, ICON_SIZE - margin, ICON_SIZE - margin],
        fill=color,
    )
    return img


def _icon_inactive() -> Image.Image:
    return _create_icon_image("#888888")


def _icon_recording() -> Image.Image:
    return _create_icon_image("#e94560")


class TrayIcon:
    def __init__(self, on_toggle_recording, on_quit):
        self._on_toggle_recording = on_toggle_recording
        self._on_quit = on_quit
        self._is_recording = False
        self._icon: pystray.Icon | None = None

    def _build_menu(self):
        if self._is_recording:
            record_label = "Detener grabacion"
        else:
            record_label = "Iniciar grabacion"

        return pystray.Menu(
            pystray.MenuItem(record_label, self._toggle_recording, default=True),
            pystray.MenuItem(
                "Abrir panel",
                lambda: webbrowser.open(f"http://{config.HOST}:{config.PORT}"),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", self._quit),
        )

    def _toggle_recording(self):
        try:
            self._on_toggle_recording()
        except Exception as e:
            logger.error("Error toggling recording: %s", e)

    def _quit(self):
        try:
            self._on_quit()
        except Exception as e:
            logger.error("Error quitting: %s", e)
        if self._icon:
            self._icon.stop()

    def update_state(self, is_recording: bool):
        self._is_recording = is_recording
        if self._icon:
            self._icon.icon = _icon_recording() if is_recording else _icon_inactive()
            self._icon.menu = self._build_menu()

    def run(self):
        self._icon = pystray.Icon(
            "CallScribe",
            icon=_icon_inactive(),
            title="CallScribe",
            menu=self._build_menu(),
        )
        self._icon.run()

    def run_detached(self) -> threading.Thread:
        t = threading.Thread(target=self.run, daemon=True)
        t.start()
        return t

    def stop(self):
        if self._icon:
            self._icon.stop()
