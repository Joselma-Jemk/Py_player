from PySide6 import QtCore, QtGui, QtWidgets, QtMultimedia
import src.main.python.ui.widget.constant as constant
from src.main.python.api.playlist import PlayMode


class VolumeWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Initialisation avec taille limitée
        self.setMaximumWidth(260)
        self.setMinimumHeight(45)

        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.lbl = QtWidgets.QLabel()
        self.btn = QtWidgets.QPushButton("\ue050")  # Icône volume haut par défaut
        self.setup_ui()

    def setup_ui(self):

        self.create_widgets()
        self.modify_widgets()
        self.create_layouts()
        self.setup_connections()

    def create_widgets(self):
        # Configuration du slider
        self.slider.setRange(0, 100)
        self.slider.setValue(20)
        self.slider.setFixedWidth(120)

        # Configuration du label (sans fond)
        self.lbl.setText("20")
        self.lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl.setFixedWidth(25)

        # Configuration du bouton mute
        self.btn.setFixedSize(32, 32)
        self.btn.setCheckable(True)
        self.mute_state = False

    def modify_widgets(self):
        self.lbl.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: white;
                font-size: 13px;
                font-weight: bold;
                padding: 0;
                margin: 0;
                border: none;
            }
        """)


        # Style épuré du slider avec couleurs vertes directes
        self.slider.setStyleSheet("""
            /* SLIDER DE VOLUME - ULTRA SIMPLE */
            QSlider::groove:horizontal {
                background-color: rgba(70, 70, 70, 0.8);
                border: 1px solid rgba(90, 90, 90, 0.6);
                height: 3px;
                border-radius: 0.2px;
            }
            
            QSlider::sub-page:horizontal {
                background-color: #4CAF50;
                border: none;
                height: 6px;
                border-radius: 3px;
            }
            
            QSlider::handle:horizontal {
                background-color: white;
                border: 2px solid #4CAF50;
                width: 6px;
                height: 6px;
                margin: -4px 0;
                border-radius: 4px;
            }
            
            QSlider::add-page:horizontal {
                background-color: rgba(80, 80, 80, 0.4);
                border: none;
                height: 6px;
                border-radius: 3px;
            }
            
            /* Désactivé (quand mute) */
            QSlider::groove:horizontal:disabled {
                background-color: rgba(70, 70, 70, 0.6);
                border: 1px solid rgba(90, 90, 90, 0.4);
            }
            
            QSlider::sub-page:horizontal:disabled {
                background-color: rgba(76, 175, 80, 0.2);
                border: 1px solid rgba(76, 175, 80, 0.1);
            }
            
            QSlider::handle:horizontal:disabled {
                background-color: rgba(180, 180, 180, 0.7);
                border: 2px solid rgba(140, 140, 140, 0.5);
            }
            """)

        # Style du bouton - épuré avec deux états (mute/unmute)
        self.btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(60, 60, 60, 0.7);
                border: 1px solid rgba(80, 80, 80, 0.5);
                border-radius: 4px;
                padding-top-bottom: 4px;
                color: #4CAF50;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: rgba(70, 70, 70, 0.8);
                border: 1px solid rgba(100, 100, 100, 0.7);
            }
            QPushButton:pressed {
                background-color: rgba(50, 50, 50, 0.8);
            }
            QPushButton:checked {
                color: #FF5252;
                background-color: rgba(255, 82, 82, 0.15);
                border: 1px solid rgba(255, 82, 82, 0.3);
            }
        """)

        # Tooltip simple
        self.btn.setToolTip("Mode mute désactivé")

    def create_layouts(self):
        # Layout principal avec alignement centré
        self.lyt = QtWidgets.QHBoxLayout(self)
        self.lyt.setContentsMargins(8, 6, 8, 6)
        self.lyt.setSpacing(10)

        # Organisation des widgets
        self.lyt.addWidget(self.btn)
        self.lyt.addWidget(self.slider)
        self.lyt.addWidget(self.lbl)

        # Pas de stretch, les widgets restent groupés

    def setup_connections(self):
        self.btn.clicked.connect(self.mute_on_off)
        self.slider.valueChanged.connect(self.volume_update)

    def volume_update(self):
        value = self.slider.value()
        self.lbl.setText(str(value))

        # Changer la couleur du texte selon le volume (fond transparent)
        if value == 0:
            self.lbl.setStyleSheet("""
                QLabel {
                    background-color: transparent;
                    color: #888;
                    font-size: 13px;
                    font-weight: bold;
                }
            """)
        elif value < 60:
            self.lbl.setStyleSheet("""
                QLabel {
                    background-color: transparent;
                    color: white;
                    font-size: 13px;
                    font-weight: bold;
                }
            """)
        elif value < 85:
            self.lbl.setStyleSheet("""
                QLabel {
                    background-color: transparent;
                    color: #FFC107;
                    font-size: 13px;
                    font-weight: bold;
                }
            """)
        else:
            self.lbl.setStyleSheet("""
                QLabel {
                    background-color: transparent;
                    color: #F44336;
                    font-size: 13px;
                    font-weight: bold;
                }
            """)

        # Mettre à jour l'icône du bouton
        self.update_button_icon()

    def update_button_icon(self):
        """Met à jour l'icône du bouton selon l'état"""
        if self.mute_state:
            # Icône muet : \ue04f
            self.btn.setText("\ue04f")
        else:
            value = self.slider.value()
            if value == 0:
                # Volume à 0 : \ue04f (même icône que muet)
                self.btn.setText("\ue04f")
            elif value < 33:
                # Volume bas : \ue04e
                self.btn.setText("\ue04e")
            elif value < 66:
                # Volume moyen : \ue04d
                self.btn.setText("\ue04d")
            else:
                # Volume élevé : \ue050
                self.btn.setText("\ue050")

    def volume_up_and_down(self, direction):
        value = self.slider.value()
        if direction == "+":
            new_value = min(value + 2, 100)
        else:
            new_value = max(value - 2, 0)
        self.slider.setValue(new_value)

    def mute_on_off(self):
        self.mute_state = not self.mute_state

        if self.mute_state:
            # Activer le mode muet
            self.slider.setEnabled(False)
            self.btn.setChecked(True)
            self.btn.setToolTip("Mode mute activé")
        else:
            # Désactiver le mode muet
            self.slider.setEnabled(True)
            self.btn.setChecked(False)
            self.btn.setToolTip("Mode mute désactivé")

        # Mettre à jour l'icône
        self.update_button_icon()

class PlayerControlsWidget(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.icon_font = None
        self._play_mode = PlayMode.NORMAL
        self.last_pressed_button = None  # Nouveau: garder trace du dernier bouton pressé
        self.setup_ui()

    def setup_ui(self):
        self.icon_font_initialize()
        self.create_widgets()
        self.modify_widgets()
        self.create_layouts()
        self.setup_connections()  # Nouvelle méthode pour les connexions

    def icon_font_initialize(self, size=14):
        dir = constant.find_path("material-symbols-outlined.ttf")
        font_id = QtGui.QFontDatabase.addApplicationFont(str(dir))
        self.icon_font = QtGui.QFont(QtGui.QFontDatabase.applicationFontFamilies(font_id)[0])
        self.icon_font.setPointSize(size)

    def create_widgets(self):
        self.btn_play_pause = QtWidgets.QPushButton("\ue037")
        self.btn_stop = QtWidgets.QPushButton("\ue047")
        self.btn_skipnext = QtWidgets.QPushButton("\ue044")
        self.btn_skipprevious = QtWidgets.QPushButton("\ue045")
        self.btn_play_mode = QtWidgets.QPushButton()
        self.btn_list = [self.btn_play_pause, self.btn_skipprevious, self.btn_stop, self.btn_skipnext,
                         self.btn_play_mode]

    def modify_widgets(self):
        # Stylesheet de base pour tous les boutons
        base_style = """
            QPushButton {
                background-color: rgba(50, 50, 55, 0.9);
                border: 1px solid rgba(80, 80, 85, 0.7);
                border-radius: 6px;
                color: #E0E0E0;
                font-size: 14px;
                padding: 0px;
                margin: 0px;
                qproperty-alignment: AlignCenter;
                min-width: 30px;
                min-height: 30px;
            }

            QPushButton:hover {
                background-color: rgba(76, 175, 80, 0.25);
                border: 1px solid #4CAF50;
                color: #4CAF50;
            }

            QPushButton:pressed {
                background-color: rgba(76, 175, 80, 0.35);
                border: 1px solid #2E7D32;
                color: #2E7D32;
            }

            QPushButton:disabled {
                color: #666666;
                background-color: rgba(50, 50, 55, 0.5);
                border: 1px solid rgba(80, 80, 85, 0.3);
            }
        """

        # Style spécial pour le bouton actif (dernier pressé)
        active_style = """
            QPushButton {
                background-color: rgba(50, 50, 55, 0.9);
                border: 1px solid #4CAF50;
                color: #4CAF50;
                border-radius: 6px;
                font-size: 14px;
                padding: 0px;
                margin: 0px;
                qproperty-alignment: AlignCenter;
                min-width: 30px;
                min-height: 30px;
            }

            QPushButton:hover {
                background-color: rgba(76, 175, 80, 0.35);
                border: 1px solid #66BB6A;
                color: #66BB6A;
            }

            QPushButton:pressed {
                background-color: rgba(76, 175, 80, 0.45);
                border: 1px solid #2E7D32;
                color: #2E7D32;
            }
        """

        # Appliquer le style de base à tous les boutons
        for btn in self.btn_list:
            btn.setFont(self.icon_font)
            btn.setFixedSize(30, 30)
            btn.setStyleSheet(base_style)
            # Stocker le style dans la propriété de l'objet
            btn.base_style = base_style
            btn.active_style = active_style

        # Style initial pour le bouton play (comme actif par défaut)
        self.last_pressed_button = self.btn_play_pause
        self.btn_play_pause.setStyleSheet(active_style)

        # Tooltips avec style vert
        self.btn_play_pause.setToolTip(
            "<div style='background-color: rgba(40, 40, 40, 0.95); padding: 6px; border-radius: 4px; border: 1px solid rgba(76, 175, 80, 0.3);'>"
            "<b style='color:#4CAF50; font-size: 12px;'>Lire</b>"
            "</div>"
        )
        self.btn_stop.setToolTip(
            "<div style='background-color: rgba(40, 40, 40, 0.95); padding: 6px; border-radius: 4px; border: 1px solid rgba(76, 175, 80, 0.3);'>"
            "<b style='color:#4CAF50; font-size: 12px;'>Stop</b>"
            "</div>"
        )
        self.btn_skipnext.setToolTip(
            "<div style='background-color: rgba(40, 40, 40, 0.95); padding: 6px; border-radius: 4px; border: 1px solid rgba(76, 175, 80, 0.3);'>"
            "<b style='color:#4CAF50; font-size: 12px;'>Lire le suivant</b>"
            "</div>"
        )
        self.btn_skipprevious.setToolTip(
            "<div style='background-color: rgba(40, 40, 40, 0.95); padding: 6px; border-radius: 4px; border: 1px solid rgba(76, 175, 80, 0.3);'>"
            "<b style='color:#4CAF50; font-size: 12px;'>Lire le précédent</b>"
            "</div>"
        )
        self.play_mode_tooltip()
        self.btn_play_mode_init()

    def setup_connections(self):
        """Configure les connexions pour gérer le bouton actif"""
        # Connecter tous les boutons à la méthode qui gère l'état actif
        self.btn_play_pause.clicked.connect(lambda: self.set_active_button(self.btn_play_pause))
        self.btn_stop.clicked.connect(lambda: self.set_active_button(self.btn_stop))
        self.btn_skipnext.clicked.connect(lambda: self.set_active_button(self.btn_skipnext))
        self.btn_skipprevious.clicked.connect(lambda: self.set_active_button(self.btn_skipprevious))
        self.btn_play_mode.clicked.connect(lambda: self.set_active_button(self.btn_play_mode))
        self.btn_play_pause.clicked.connect(self.btn_play_pause_tooltip)

    def set_active_button(self, button):
        """Définit le bouton actif et met à jour les styles"""
        # Réinitialiser le style du précédent bouton actif
        if self.last_pressed_button:
            self.last_pressed_button.setStyleSheet(self.last_pressed_button.base_style)

        # Mettre le nouveau bouton en style actif
        button.setStyleSheet(button.active_style)
        self.last_pressed_button = button

        # Animation visuelle (optionnelle)
        self.animate_button_press(button)

    def animate_button_press(self, button):
        """Animation visuelle pour le bouton pressé"""
        # Créer une animation de pulse
        original_size = button.size()

        # Animation de réduction/agrandissement
        animation = QtCore.QPropertyAnimation(button, b"geometry")
        animation.setDuration(150)
        animation.setStartValue(button.geometry())

        # Réduire légèrement
        small_rect = QtCore.QRect(
            button.x() + 1,
            button.y() + 1,
            original_size.width() - 2,
            original_size.height() - 2
        )
        animation.setKeyValueAt(0.5, small_rect)
        animation.setEndValue(button.geometry())
        animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        animation.start()

    def create_layouts(self):
        self.lyt = QtWidgets.QHBoxLayout(self)
        self.lyt.setSpacing(8)
        for btn in self.btn_list:
            self.lyt.addWidget(btn)

    @property
    def play_mode(self):
        return self._play_mode

    @play_mode.setter
    def play_mode(self, value):
        self._play_mode = value

    def btn_play_pause_tooltip(self):
        if self.btn_play_pause.text() == "\ue037":  # Icône play
            self.btn_play_pause.setToolTip(
                "<div style='background-color: rgba(40, 40, 40, 0.95); padding: 6px; border-radius: 4px; border: 1px solid rgba(76, 175, 80, 0.3);'>"
                "<b style='color:#4CAF50; font-size: 12px;'>Pause</b>"
                "</div>")
        else:
            self.btn_play_pause.setToolTip(
                "<div style='background-color: rgba(40, 40, 40, 0.95); padding: 6px; border-radius: 4px; border: 1px solid rgba(76, 175, 80, 0.3);'>"
                "<b style='color:#4CAF50; font-size: 12px;'>Lire</b>"
                "</div>")
        self.set_active_button(self.btn_play_pause)

    def btn_play_mode_init(self):
        if self.play_mode == PlayMode.NORMAL:
            self.btn_play_mode.setText("\ue14b")
        elif self.play_mode == PlayMode.LOOP_ONE:
            self.btn_play_mode.setText("\ue041")
        elif self.play_mode == PlayMode.LOOP_ALL:
            self.btn_play_mode.setText("\ue040")
        else:
            self.btn_play_mode.setText("\ue043")
        self.play_mode_tooltip()

    def player_mode_update(self):
        if self.play_mode == PlayMode.NORMAL:
            self.btn_play_mode.setText("\ue041")
        elif self.play_mode == PlayMode.LOOP_ONE:
            self.btn_play_mode.setText("\ue040")
        elif self.play_mode == PlayMode.LOOP_ALL:
            self.btn_play_mode.setText("\ue043")
        else:
            self.btn_play_mode.setText("\ue14b")
        self.play_mode_tooltip()

    def play_mode_tooltip(self):
        if self.btn_play_mode.text() == "\ue040":
            self.btn_play_mode.setToolTip(
                "<div style='background-color: rgba(40, 40, 40, 0.95); padding: 6px; border-radius: 4px; border: 1px solid rgba(76, 175, 80, 0.3);'>"
                "<b style='color:#4CAF50; font-size: 12px;'>Lecture de la playlist</b>"
                "</div>"
            )
            self.play_mode = PlayMode.LOOP_ALL

        elif self.btn_play_mode.text() == "\ue041":
            self.btn_play_mode.setToolTip(
                "<div style='background-color: rgba(40, 40, 40, 0.95); padding: 6px; border-radius: 4px; border: 1px solid rgba(76, 175, 80, 0.3);'>"
                "<b style='color:#4CAF50; font-size: 12px;'>Lecture en boucle du fichier actuel</b>"
                "</div>"
            )
            self.play_mode = PlayMode.LOOP_ONE
        elif self.btn_play_mode.text() == "\ue14b":
            self.btn_play_mode.setToolTip(
                "<div style='background-color: rgba(40, 40, 40, 0.95); padding: 6px; border-radius: 4px; border: 1px solid rgba(76, 175, 80, 0.3);'>"
                "<b style='color:#4CAF50; font-size: 12px;'>Lire une seule fois le fichier actuel</b>"
                "</div>"
            )
            self.play_mode = PlayMode.NORMAL
        else:
            self.btn_play_mode.setToolTip(
                "<div style='background-color: rgba(40, 40, 40, 0.95); padding: 6px; border-radius: 4px; border: 1px solid rgba(76, 175, 80, 0.3);'>"
                "<b style='color:#4CAF50; font-size: 12px;'>Lecture aléatoire de la playlist en boucle</b>"
                "</div>"
            )
            self.play_mode = PlayMode.SHUFFLE

class TimeLabelWidget(QtWidgets.QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Texte avec | au lieu de / et labels distincts
        self.current_time = "00:00:00"
        self.total_time = "00:00:00"
        self.update_display()
        self.setFixedHeight(40)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                background-color: transparent;
                border: none;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)

    def update_display(self):
        """Met à jour l'affichage avec le format demandé"""
        self.setText(
            f"<span style='color:#eaeaea;font-weight:bold;font-size:13px;'>{self.current_time}</span>"
            f"<span style='color:#4CAF50;font-weight:bold;font-size:15px;'> | </span>"
            f"<span style='color:#7f7f7f;font-weight:bold;font-size:13px;'>{self.total_time}</span>"
        )

    def set_times(self, current_time = None, total_time = None):
        """Définit les temps actuels et totaux"""
        if current_time:
            self.current_time = current_time
        if total_time:
            self.total_time = total_time
        self.update_display()

class PlaylistButtonWidget(QtWidgets.QPushButton):
    def __init__(self, parent=None):
        super().__init__("\ue0ee", parent)
        self.setFixedSize(40, 40)
        buttons_style = """
            QPushButton {
                background-color: transparent;
                border: 1px solid #4CAF50;
                border-radius: 4px;
                color: #4CAF50;
                font-size: 16px;
                padding: 8px;
            }

            QPushButton:hover {
                background-color: #4CAF50;
                color: white;
            }

            QPushButton:pressed {
                background-color: #2E7D32;
                border-color: #2E7D32;
                color: white;
            }
        """
        self.setStyleSheet(buttons_style)
        self.setToolTip("<b style='color:#f2f2f7;font-weight:bold;'>Masquer le panneau des playlists</b>")

class ToolBarWidget(QtWidgets.QToolBar):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self.setup_ui()

    def setup_ui(self):
        self.create_widgets()
        self.setup_connections()
        self.add_widgets_to_toolbar()

    def create_widgets(self):
        self.player_controls = PlayerControlsWidget()
        self.time_label = TimeLabelWidget()
        self.volume_widget = VolumeWidget()
        self.btn_playlist = PlaylistButtonWidget()

        # Widgets conteneurs pour un meilleur alignement
        self.left_container = QtWidgets.QWidget()
        self.right_container = QtWidgets.QWidget()

        # Layouts pour les conteneurs
        self.left_layout = QtWidgets.QHBoxLayout(self.left_container)
        self.right_layout = QtWidgets.QHBoxLayout(self.right_container)

        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(15)
        self.right_layout.setSpacing(15)

        # Set icon font for playlist button
        if self.player_controls.icon_font:
            self.btn_playlist.setFont(self.player_controls.icon_font)

    def setup_connections(self):
        self.volume_widget.slider.valueChanged.connect(self.volume_widget.volume_update)

        # Setup shortcuts
        QtGui.QShortcut(QtCore.Qt.Key.Key_VolumeMute, self.volume_widget, self.volume_widget.mute_on_off)

        shorcut_1 = QtGui.QShortcut(QtCore.Qt.Key.Key_Up, self.volume_widget,
                                    lambda: self.volume_widget.volume_up_and_down("+"))
        shorcut_2 = QtGui.QShortcut(QtCore.Qt.Key.Key_Down, self.volume_widget,
                                    lambda: self.volume_widget.volume_up_and_down("-"))

        QtGui.QShortcut(QtCore.Qt.Key.Key_Space, self.volume_widget,
                        self.player_controls.btn_play_pause.clicked.emit)
        QtGui.QShortcut(QtCore.Qt.Key.Key_VolumeMute, self.volume_widget,
                        self.volume_widget.btn.clicked.emit)

        # Connect player controls
        self.player_controls.btn_play_mode.clicked.connect(self.player_controls.player_mode_update)

    def add_widgets_to_toolbar(self):
        # Remplir le conteneur gauche
        self.left_layout.addWidget(self.player_controls)
        self.left_layout.addWidget(self.time_label)
        self.left_layout.addStretch()

        # Remplir le conteneur droit
        self.right_layout.addStretch()
        self.right_layout.addWidget(self.volume_widget)
        self.right_layout.addWidget(self.btn_playlist)

        # Ajouter les conteneurs à la toolbar
        self.addWidget(self.left_container)

        # Espace flexible au centre
        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        self.addWidget(self.right_container)

    def volume_update(self):
        if self.volume_widget.slider.value():
            self.volume_widget.volume_update()